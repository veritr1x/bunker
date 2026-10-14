package service

import (
	"context"
	"testing"

	pb "lunar-tear/server/gen/proto"
	"lunar-tear/server/internal/store"
)

func TestWeaponEvolveKeepsAbilityLevels(t *testing.T) {
	holder, users := harness(t)
	cat := holder.Get().Weapon
	var from, to int32
	for id, next := range cat.EvolutionNextWeaponId {
		w, ok := cat.Weapons[id]
		n, ok2 := cat.Weapons[next]
		if ok && ok2 && len(cat.AbilitySlots[w.WeaponAbilityGroupId]) > 0 && len(cat.AbilitySlots[n.WeaponAbilityGroupId]) > 0 {
			from, to = id, next
			break
		}
	}
	if from == 0 {
		t.Fatal("no evolvable weapon with abilities in the master data")
	}
	slots := cat.AbilitySlots[cat.Weapons[from].WeaponAbilityGroupId]
	users.user.Weapons["w1"] = store.WeaponState{UserWeaponUuid: "w1", WeaponId: from, Level: 90}
	abilities := []store.WeaponAbilityState{}
	for _, slot := range slots {
		abilities = append(abilities, store.WeaponAbilityState{UserWeaponUuid: "w1", SlotNumber: slot, Level: 7})
	}
	users.user.WeaponAbilities["w1"] = abilities

	if _, err := NewWeaponServiceServer(users, users, holder).Evolve(context.Background(), &pb.EvolveRequest{UserWeaponUuid: "w1"}); err != nil {
		t.Fatal(err)
	}
	if users.user.Weapons["w1"].WeaponId != to {
		t.Fatalf("weapon %d, want %d", users.user.Weapons["w1"].WeaponId, to)
	}
	kept := map[int32]bool{}
	for _, s := range slots {
		kept[s] = true
	}
	for _, a := range users.user.WeaponAbilities["w1"] {
		if kept[a.SlotNumber] && a.Level != 7 {
			t.Fatalf("slot %d level %d after evolving, want 7", a.SlotNumber, a.Level)
		}
		if !kept[a.SlotNumber] && a.Level != 1 {
			t.Fatalf("new slot %d level %d, want 1", a.SlotNumber, a.Level)
		}
	}
}
