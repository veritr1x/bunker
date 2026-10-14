package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
)

// The game's fortune result screens: omikuji_result_<n> for each draw's art
// set (the draw's asset id in m_omikuji).
var omikujiResultScreens = map[int32][2]int32{
	1: {101, 105}, 2: {201, 217}, 3: {301, 305}, 4: {401, 421},
	5: {501, 521}, 6: {601, 605}, 7: {701, 722},
}

func TestOmikujiDrawShowsARealFortune(t *testing.T) {
	holder, users := harness(t)
	srv := NewOmikujiServiceServer(users, users, holder)
	for id, r := range omikujiResultScreens {
		seen := map[int32]bool{}
		for range 2000 {
			resp, err := srv.OmikujiDraw(context.Background(), &pb.OmikujiDrawRequest{OmikujiId: id})
			if err != nil {
				t.Fatal(err)
			}
			got := resp.OmikujiResultAssetId
			if got < r[0] || got > r[1] {
				t.Fatalf("draw %d: fortune %d has no result screen (want %d-%d)", id, got, r[0], r[1])
			}
			seen[got] = true
		}
		if want := int(r[1] - r[0] + 1); len(seen) != want {
			t.Errorf("draw %d: %d of %d fortunes came up", id, len(seen), want)
		}
		if _, ok := users.user.DrawnOmikuji[id]; !ok {
			t.Errorf("draw %d not recorded", id)
		}
	}
}
