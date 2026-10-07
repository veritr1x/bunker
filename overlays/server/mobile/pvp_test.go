package mobile

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	pb "lunar-tear/server/gen/proto"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/emptypb"
)

// The Arena against computer players through the real server and
// interceptors. Needs LUNAR_TEST_MASTER and LUNAR_TEST_SAVE like TestMissionsEndToEnd.
func TestArenaEndToEnd(t *testing.T) {
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
	SetPortOffset(20000)
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
	arena := pb.NewPvpServiceClient(conn)

	top, err := arena.GetTopData(ctx, &emptypb.Empty{})
	if err != nil {
		t.Fatal(err)
	}
	if top.CurrentSeasonId == 0 || top.Rank == 0 {
		t.Fatalf("top data: %+v", top)
	}
	if top.DiffUserData["IUserDeck"] == nil || top.DiffUserData["IUserPvpDefenseDeck"] == nil {
		t.Fatalf("first visit makes no Arena deck: %v", keys(top.DiffUserData))
	}
	if top.DiffUserData["IUserPvpStatus"] == nil {
		t.Fatalf("first visit sends no IUserPvpStatus: %v", keys(top.DiffUserData))
	}
	if _, err := pb.NewDeckServiceClient(conn).SetPvpDefenseDeck(ctx, &pb.SetPvpDefenseDeckRequest{UserDeckNumber: 1, DeckPower: &pb.DeckPower{Power: 1234}}); err != nil {
		t.Fatal(err)
	}
	list, err := arena.GetMatchingList(ctx, &emptypb.Empty{})
	if err != nil {
		t.Fatal(err)
	}
	if len(list.Matching) != 3 || list.Matching[0].Name == "" || list.Matching[0].DeckPower == 0 || len(list.Matching[0].DeckMainWeaponAttributeType) != 3 {
		t.Fatalf("matching list: %+v", list.Matching)
	}
	refreshed, err := arena.UpdateMatchingList(ctx, &emptypb.Empty{})
	if err != nil || len(refreshed.Matching) != 3 || refreshed.DiffUserData["IUserPvpStatus"] == nil {
		t.Fatalf("refresh: %v %+v %v", err, refreshed.GetMatching(), keys(refreshed.GetDiffUserData()))
	}
	opponent := refreshed.Matching[0]
	start, err := arena.StartBattle(ctx, &pb.StartBattleRequest{OpponentPlayerId: opponent.PlayerId, UseDeckNumber: 1})
	if err != nil {
		t.Fatal(err)
	}
	if len(start.OpponentDeckCharacter) != 3 || start.OpponentDeckCharacter[0].GetCostume().GetCostumeId() == 0 || start.OpponentDeckCharacter[0].GetMainWeapon().GetWeaponId() == 0 {
		t.Fatalf("opponent deck: %+v", start.OpponentDeckCharacter)
	}
	finish, err := arena.FinishBattle(ctx, &pb.FinishBattleRequest{OpponentPlayerId: opponent.PlayerId, IsVictory: true})
	if err != nil {
		t.Fatal(err)
	}
	if finish.AfterPvpPoint <= finish.BeforePvpPoint || finish.PvpGradeOneMatchRewardId == 0 || finish.PvpGradeGroupId == 0 {
		t.Fatalf("finish: %+v", finish)
	}
	t.Logf("beat %s: points %d -> %d, rank %d -> %d, reward %d", opponent.Name, finish.BeforePvpPoint, finish.AfterPvpPoint, finish.BeforeRank, finish.AfterRank, finish.PvpGradeOneMatchRewardId)
	if finish.DiffUserData["IUserConsumableItem"] == nil && finish.DiffUserData["IUserMaterial"] == nil {
		t.Fatalf("win reward not paid: %v", keys(finish.DiffUserData))
	}

	ranking, err := arena.GetRanking(ctx, &pb.GetRankingRequest{RankFrom: 1})
	if err != nil || len(ranking.RankingUser) == 0 || ranking.RankingUser[0].Rank != 1 || ranking.RankingPosition != finish.AfterRank {
		t.Fatalf("ranking: %v %+v", err, ranking)
	}
	around, err := arena.GetRanking(ctx, &pb.GetRankingRequest{RankFrom: ranking.RankingPosition - 2})
	if err != nil {
		t.Fatal(err)
	}
	foundSelf := false
	for _, r := range around.RankingUser {
		foundSelf = foundSelf || r.PvpPoint == finish.AfterPvpPoint && r.Rank == finish.AfterRank && r.PlayerId < 1_000_000
	}
	if !foundSelf {
		t.Fatalf("player not in the ranking around rank %d: %+v", ranking.RankingPosition, around.RankingUser[:3])
	}
	result, err := arena.GetSeasonResult(ctx, &emptypb.Empty{})
	if err != nil || result.AttackWinCount != 1 || result.AttackPvpPoint != finish.AfterPvpPoint-finish.BeforePvpPoint {
		t.Fatalf("season result: %v %+v", err, result)
	}
	attacks, err := arena.GetAttackLogList(ctx, &emptypb.Empty{})
	if err != nil || len(attacks.AttackLog) != 1 || !attacks.AttackLog[0].IsVictory || attacks.AttackLog[0].Name != opponent.Name || len(attacks.AttackLog[0].DeckCostumeId) != 3 {
		t.Fatalf("attack log: %v %+v", err, attacks.GetAttackLog())
	}
	if _, err := arena.GetDefenseLogList(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}
	if _, err := pb.NewRewardServiceClient(conn).ReceivePvpReward(ctx, &emptypb.Empty{}); err != nil {
		t.Fatal(err)
	}

	users := pb.NewUserServiceClient(conn)
	cpu, err := users.GetUserProfile(ctx, &pb.GetUserProfileRequest{PlayerId: opponent.PlayerId})
	if err != nil || cpu.Name != opponent.Name || len(cpu.LatestUsedDeck.GetDeckCharacter()) != 3 || cpu.PvpInfo.GetCurrentGradeId() == 0 {
		t.Fatalf("computer player profile: %v %+v", err, cpu)
	}
	me, err := users.GetUserProfile(ctx, &pb.GetUserProfileRequest{})
	if err != nil || me.PvpInfo.GetCurrentRank() != finish.AfterRank || me.PvpInfo.GetCurrentGradeId() == 0 {
		t.Fatalf("own profile Arena info: %v %+v", err, me.GetPvpInfo())
	}

	tables, err := pb.NewDataServiceClient(conn).GetUserData(ctx, &pb.UserDataGetRequest{TableName: []string{"IUserPvpStatus", "IUserPvpDefenseDeck", "IUserPvpWeeklyResult"}})
	if err != nil {
		t.Fatal(err)
	}
	for table, json := range tables.UserDataJson {
		t.Logf("%s: %.300s", table, json)
	}
	if !strings.Contains(tables.UserDataJson["IUserPvpStatus"], `"winStreakCount":1`) || !strings.Contains(tables.UserDataJson["IUserPvpDefenseDeck"], `"userDeckNumber":1`) {
		t.Fatal("Arena tables do not show the battle or the defense deck")
	}
}
