package mobile

import (
	"context"
	"database/sql"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	pb "lunar-tear/server/gen/proto"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/emptypb"
	_ "modernc.org/sqlite"
)

// Bunker's mission tracking and added handlers through the real server and
// interceptors. Needs LUNAR_TEST_MASTER (patched master data) and
// LUNAR_TEST_SAVE (a game.db with a player); the save is copied.
func TestMissionsEndToEnd(t *testing.T) {
	master, save := os.Getenv("LUNAR_TEST_MASTER"), os.Getenv("LUNAR_TEST_SAVE")
	if master == "" || save == "" {
		t.Skip("set LUNAR_TEST_MASTER and LUNAR_TEST_SAVE")
	}
	root, data := t.TempDir(), t.TempDir()
	os.MkdirAll(filepath.Join(root, "assets/release"), 0700)
	os.MkdirAll(filepath.Join(root, "assets/revisions/0/android"), 0700)
	b, err := os.ReadFile(master)
	if err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(root, "assets/release", MasterName), b, 0600)
	os.WriteFile(filepath.Join(root, "assets/revisions/0/android/list.bin"), []byte{0x08, 0x01}, 0600)
	s, err := os.ReadFile(save)
	if err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(data, "game.db"), s, 0600)
	SetPortOffset(20000) // the desktop may use 3000 or 8080 already
	defer SetPortOffset(0)
	if err := Start(data, root); err != nil {
		t.Fatal(err)
	}
	defer Stop()

	conn, err := grpc.NewClient(local(8003), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	missions := pb.NewMissionServiceClient(conn)

	// Walking in the Cage counts for "Walk N km in The Cage"; the first request also backfills.
	upd, err := missions.UpdateMissionProgress(ctx, &pb.UpdateMissionProgressRequest{
		CageMeasurableValues: &pb.CageMeasurableValues{RunningDistanceMeters: 5000, MamaTappedCount: 50},
	})
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := upd.DiffUserData["IUserMission"]; !ok {
		t.Fatalf("no IUserMission in the diff: %v", keys(upd.DiffUserData))
	}

	db, err := sql.Open("sqlite", filepath.Join(data, "game.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	var cleared []int32
	rows, err := db.Query(`SELECT mission_id FROM user_missions WHERE mission_progress_status_type = 2`)
	if err != nil {
		t.Fatal(err)
	}
	for rows.Next() {
		var id int32
		rows.Scan(&id)
		cleared = append(cleared, id)
	}
	rows.Close()
	t.Logf("%d missions cleared after the first request", len(cleared))
	if len(cleared) == 0 {
		t.Fatal("nothing cleared")
	}

	got, err := missions.ReceiveMissionRewardsById(ctx, &pb.ReceiveMissionRewardsByIdRequest{MissionId: cleared})
	if err != nil {
		t.Fatal(err)
	}
	if len(got.ReceivedPossession) == 0 || got.DiffUserData["IUserMission"] == nil {
		t.Fatalf("rewards: %d, diff %v", len(got.ReceivedPossession), keys(got.DiffUserData))
	}
	t.Logf("received %d rewards; diff tables %v", len(got.ReceivedPossession), keys(got.DiffUserData))

	if _, err := missions.ReceiveMissionPassRewards(ctx, &pb.ReceiveMissionPassRewardsRequest{MissionPassId: 10012}); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewRewardServiceClient(conn).ReceiveMissionPassRemainingReward(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewRewardServiceClient(conn).ReceiveLabyrinthSeasonReward(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewIndividualPopServiceClient(conn).GetUnreadPop(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewPortalCageServiceClient(conn).GetDropItem(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}

	quest := pb.NewQuestServiceClient(conn)
	daily, err := quest.ReceiveDailyQuestGroupCompleteReward(ctx, &emptypb.Empty{})
	if err != nil {
		t.Fatal(err)
	}
	if daily.DiffUserData["IUserEventQuestDailyGroupCompleteReward"] == nil {
		t.Fatalf("daily set reward not recorded: %v", keys(daily.DiffUserData))
	}
	again, err := quest.ReceiveDailyQuestGroupCompleteReward(ctx, &emptypb.Empty{})
	if err != nil || again.DiffUserData["IUserEventQuestDailyGroupCompleteReward"] != nil {
		t.Fatalf("daily set reward paid twice in a day: %v %v", err, keys(again.DiffUserData))
	}

	var questId int32
	if err := db.QueryRow(`SELECT quest_id FROM user_quests WHERE clear_count > 0 ORDER BY quest_id LIMIT 1`).Scan(&questId); err != nil {
		t.Fatal(err)
	}
	skip, err := quest.SkipQuestBulk(ctx, &pb.SkipQuestBulkRequest{SkipQuestInfo: []*pb.SkipQuestInfo{{QuestId: questId, SkipCount: 2}}, UserDeckNumber: 1})
	if err != nil {
		t.Fatal(err)
	}
	if skip.DiffUserData["IUserQuest"] == nil {
		t.Fatalf("bulk skip changed no quest: %v", keys(skip.DiffUserData))
	}
	t.Logf("bulk skip of quest %d: diff tables %v", questId, keys(skip.DiffUserData))

	var costumeId int32
	if err := db.QueryRow(`SELECT costume_id FROM user_costumes LIMIT 1`).Scan(&costumeId); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewCostumeServiceClient(conn).RegisterLevelBonusConfirmed(ctx, &pb.RegisterLevelBonusConfirmedRequest{CostumeId: costumeId, Level: 99}); err != nil {
		t.Fatal(err)
	}
	if _, err := quest.SetQuestSceneChoice(ctx, &pb.SetQuestSceneChoiceRequest{QuestSceneId: 1113, ChoiceNumber: 2, QuestFlowType: 1}); err != nil {
		t.Fatal(err)
	}

	user, err := pb.NewDataServiceClient(conn).GetUserData(ctx, &pb.UserDataGetRequest{TableName: []string{
		"IUserMissionPassPoint", "IUserQuestSceneChoice", "IUserQuestSceneChoiceHistory", "IUserCostumeLevelBonusReleaseStatus", "IUserEventQuestDailyGroupCompleteReward",
	}})
	if err != nil {
		t.Fatal(err)
	}
	for table, json := range user.UserDataJson {
		t.Logf("%s: %.200s", table, json)
	}
	if user.UserDataJson["IUserQuestSceneChoice"] == "[]" || user.UserDataJson["IUserEventQuestDailyGroupCompleteReward"] == "[]" {
		t.Fatal("story choice or daily set reward missing from the user data")
	}
	// The game's Rates page shows the rates from Pod Programs > Summon rates.
	os.WriteFile(filepath.Join(data, "gacha_rates.json"), []byte(`{"fourStarPercent":12,"threeStarPercent":20,"fourStarCostumeShare":50,"threeStarCostumeShare":50,"featuredPercent":35,"stepUpBoost":true,"multiMinRarity":3}`), 0600)
	resp, err := http.Get("http://" + local(8080) + "/gacha-rate?gachaId=1&tab=Rate")
	if err != nil {
		t.Fatal(err)
	}
	page, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(string(page), "<td>★4 costume</td><td>6%</td>") {
		t.Fatalf("rates page does not show the saved rates: %.400s", page)
	}
}

func keys(m map[string]*pb.DiffData) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}
