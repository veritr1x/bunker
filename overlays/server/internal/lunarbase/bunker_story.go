package lunarbase

import (
	"errors"
	"fmt"
	"time"

	"lunar-tear/server/internal/campaign"
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/masterdata/memorydb"
	"lunar-tear/server/internal/questflow"
	"lunar-tear/server/internal/store"
)

// Bunker: Pod Programs › Story Jump (android_story.py). "story_jump" brings a
// save forward to the start of a main-story quest (questflow.JumpMainStory),
// or with dry_run works out what that would clear and give without writing.
// It loads the master data, so like every edit it runs with the server
// stopped; the page reads where a save is from the save itself.

type storySpec struct {
	QuestID      int32 `json:"quest_id"`
	Season2Route int32 `json:"season2_route"`
	DryRun       bool  `json:"dry_run"`
}

type storyGrant struct {
	PossessionType int32 `json:"possession_type"`
	PossessionID   int32 `json:"possession_id"`
	Count          int32 `json:"count"`
}

// storyHandler builds the quest handler the way the server does at start
// (runtime/build.go), for the master data at path.
func storyHandler(path string) (*questflow.QuestHandler, *masterdata.StoryPath, error) {
	if path == "" {
		return nil, nil, errors.New("master_data_path required")
	}
	if err := memorydb.Init(path); err != nil {
		return nil, nil, fmt.Errorf("init master data: %w", err)
	}
	gameConfig, err := masterdata.LoadGameConfig()
	if err != nil {
		return nil, nil, fmt.Errorf("load game config: %w", err)
	}
	parts, err := masterdata.LoadPartsCatalog()
	if err != nil {
		return nil, nil, fmt.Errorf("load parts catalog: %w", err)
	}
	quests, err := masterdata.LoadQuestCatalog(parts)
	if err != nil {
		return nil, nil, fmt.Errorf("load quest catalog: %w", err)
	}
	campaigns, err := campaign.Load()
	if err != nil {
		return nil, nil, fmt.Errorf("load campaign catalog: %w", err)
	}
	rebirth, err := masterdata.LoadCharacterRebirthCatalog()
	if err != nil {
		return nil, nil, fmt.Errorf("load character rebirth catalog: %w", err)
	}
	p, err := masterdata.LoadStoryPath()
	if err != nil {
		return nil, nil, err
	}
	return questflow.NewQuestHandler(quests, gameConfig, masterdata.LoadSideStoryCatalog(), campaigns, rebirth), p, nil
}

func runStoryJump(req *request) (int, error) {
	if req.Story == nil || req.Story.QuestID == 0 {
		return 0, errors.New("story.quest_id required")
	}
	h, p, err := storyHandler(req.MasterDataPath)
	if err != nil {
		return 0, err
	}
	db, st, err := openDB(req.DBPath)
	if err != nil {
		return 0, err
	}
	defer db.Close()
	target := questflow.StoryTarget{QuestId: req.Story.QuestID, Season2Route: req.Story.Season2Route}
	now := time.Now().UnixMilli()
	var res questflow.JumpResult
	if req.Story.DryRun {
		user, err := st.LoadUser(req.UserID)
		if err != nil {
			return 0, fmt.Errorf("load user: %w", err)
		}
		copy := store.CloneUserState(user)
		res, err = h.JumpMainStory(&copy, p, target, now)
		if err != nil {
			return 0, err
		}
	} else {
		var jumpErr error
		_, err = st.UpdateUser(req.UserID, func(u *store.UserState) {
			res, jumpErr = h.JumpMainStory(u, p, target, now)
			if jumpErr != nil {
				// Leave the save as it was: JumpMainStory refuses before changing anything.
				return
			}
		})
		if jumpErr != nil {
			return 0, jumpErr
		}
		if err != nil {
			return 0, fmt.Errorf("story jump: %w", err)
		}
	}
	grants := []storyGrant{}
	for _, g := range res.Grants {
		grants = append(grants, storyGrant{PossessionType: int32(g.PossessionType), PossessionID: g.PossessionId, Count: g.Count})
	}
	cleared := res.Cleared
	if cleared == nil {
		cleared = []int32{}
	}
	readData = map[string]any{"cleared": cleared, "grants": grants, "gems": res.Gems, "dry_run": req.Story.DryRun}
	return len(res.Cleared), nil
}
