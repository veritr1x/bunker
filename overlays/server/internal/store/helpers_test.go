package store

import (
	"testing"

	"lunar-tear/server/internal/model"
)

func testGranter() *PossessionGranter {
	return &PossessionGranter{
		CostumeDuplicateExchange: map[int32][]DuplicateExchange{
			21000: {{PossessionType: model.PossessionTypeMaterial, PossessionId: 311053, Count: 10}},
		},
		CompanionDuplicateExchange: map[int32][]DuplicateExchange{
			1: {{PossessionType: model.PossessionTypeConsumableItem, PossessionId: 2, Count: 100}},
		},
		CostumeEnhancedById:   map[int32]CostumeEnhancedRef{31017: {CostumeId: 31017, Level: 1, ActiveSkillLevel: 1, AwakenCount: 5}, 10108: {CostumeId: 10108, Level: 50, ActiveSkillLevel: 1}},
		CompanionEnhancedById: map[int32]CompanionEnhancedRef{49: {CompanionId: 49, Level: 50}},
		CostumeExpForLevel:    func(_, level int32) int32 { return level * 100 },
		GoldConsumableItemId:  1,
		Limits:                PossessionLimits{Weapon: 2, Material: 99999, ConsumableItem: 99999, Money: 999999999},
	}
}

func TestGrantFullConvertsDuplicates(t *testing.T) {
	g := testGranter()
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantFull(user, model.PossessionTypeCostume, 21000, 1, 0)
	g.GrantFull(user, model.PossessionTypeCostume, 21000, 1, 0)
	if n := countCostumes(user, 21000); n != 1 || user.Materials[311053] != 10 {
		t.Fatalf("costume copies %d, exchange material %d", n, user.Materials[311053])
	}
	g.GrantFull(user, model.PossessionTypeCompanion, 1, 1, 0)
	g.GrantFull(user, model.PossessionTypeCompanion, 1, 1, 0)
	if len(user.Companions) != 1 || user.ConsumableItems[2] != 100 {
		t.Fatalf("companions %d, medals %d", len(user.Companions), user.ConsumableItems[2])
	}
	// GrantCostume itself never converts: summons convert on their own.
	if g.GrantCostume(user, 21000, 0) || user.Materials[311053] != 10 {
		t.Fatal("GrantCostume converted a duplicate")
	}
}

func TestGrantFullEnhanced(t *testing.T) {
	g := testGranter()
	var steps []int32
	g.ApplyCostumeAwaken = func(_ *UserState, _ string, _ int32, step int32, _ int64) { steps = append(steps, step) }
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	g.GrantFull(user, model.PossessionTypeCompanionEnhanced, 49, 1, 0)
	for _, c := range user.Companions {
		if c.CompanionId != 49 || c.Level != 50 {
			t.Fatalf("enhanced companion %+v", c)
		}
	}
	g.GrantFull(user, model.PossessionTypeCostumeEnhanced, 10108, 1, 0)
	g.GrantFull(user, model.PossessionTypeCostumeEnhanced, 31017, 1, 0)
	for _, c := range user.Costumes {
		switch c.CostumeId {
		case 10108:
			if c.Level != 50 || c.Exp != 5000 {
				t.Fatalf("enhanced costume %+v", c)
			}
		case 31017:
			if c.AwakenCount != 5 || len(steps) != 5 {
				t.Fatalf("awakened costume %+v, steps %v", c, steps)
			}
		}
	}
}

func TestWouldOverflow(t *testing.T) {
	g := testGranter()
	user := SeedUserState(1, "u", 0, model.DefaultPlatform)
	user.Materials[100001] = 99990
	user.ConsumableItems[1] = 999999990
	if !g.WouldOverflow(user, model.PossessionTypeMaterial, 100001, 10) || g.WouldOverflow(user, model.PossessionTypeMaterial, 100001, 9) {
		t.Fatal("material limit 99999")
	}
	if g.WouldOverflow(user, model.PossessionTypeConsumableItem, 1, 9) || !g.WouldOverflow(user, model.PossessionTypeConsumableItem, 1, 10) {
		t.Fatal("gold uses the money limit")
	}
	g.GrantFull(user, model.PossessionTypeWeapon, 101001, 2, 0)
	if len(user.Weapons) != 2 || !g.WouldOverflow(user, model.PossessionTypeWeapon, 101001, 1) {
		t.Fatalf("weapons %d, limit 2", len(user.Weapons))
	}
}

func countCostumes(user *UserState, costumeId int32) int {
	n := 0
	for _, c := range user.Costumes {
		if c.CostumeId == costumeId {
			n++
		}
	}
	return n
}
