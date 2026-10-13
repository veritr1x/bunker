package questflow

import (
	"fmt"
	"slices"

	"github.com/google/uuid"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
	"lunar-tear/server/internal/store"
)

// Recollections of Dusk (event quest limit content): each difficulty of a
// chapter is three quests in a row, and a costume (or weapon, if the
// chapter's m_event_quest_limit_content_deck_restriction says so) used to win
// one of them is locked for the others. The client greys locked items out
// from IUserDeckLimitContentRestricted (CalculatorLimitContent.
// IsRestrictedCostumeByLevel matches rows by chapter, possession type and
// uuid).

// deckLimitTargets lists the deck's lockable possessions for a chapter now.
func (h *QuestHandler) deckLimitTargets(user *store.UserState, chapterId int32, deck store.DeckState, nowMillis int64) []store.LimitContentRestricted {
	if h.LimitContent == nil {
		return nil
	}
	types := h.LimitContent.RestrictionTypes(chapterId, nowMillis)
	if len(types) == 0 {
		return nil
	}
	var out []store.LimitContentRestricted
	for _, dcUuid := range deckCharacterUuids(deck) {
		dc, ok := user.DeckCharacters[dcUuid]
		if !ok {
			continue
		}
		if slices.Contains(types, masterdata.LimitContentDeckRestrictionCostume) && dc.UserCostumeUuid != "" {
			out = append(out, store.LimitContentRestricted{PossessionType: int32(model.PossessionTypeCostume), TargetUuid: dc.UserCostumeUuid})
		}
		if slices.Contains(types, masterdata.LimitContentDeckRestrictionWeapon) {
			for _, w := range append([]string{dc.MainUserWeaponUuid}, user.DeckSubWeapons[dcUuid]...) {
				if w != "" {
					out = append(out, store.LimitContentRestricted{PossessionType: int32(model.PossessionTypeWeapon), TargetUuid: w})
				}
			}
		}
	}
	return out
}

// CheckLimitContentDeck refuses a deck that reuses a costume or weapon locked
// by another quest of the chapter's run.
func (h *QuestHandler) CheckLimitContentDeck(user *store.UserState, chapterId, questId, deckNumber int32, nowMillis int64) error {
	var deck store.DeckState
	for _, dt := range []model.DeckType{model.DeckTypeRestrictedLimitContentQuest, model.DeckTypeQuest} {
		if d, ok := user.Decks[store.DeckKey{DeckType: dt, UserDeckNumber: deckNumber}]; ok {
			deck = d
			break
		}
	}
	for _, t := range h.deckLimitTargets(user, chapterId, deck, nowMillis) {
		for _, r := range user.Ext.Quest.LimitContentRestricted {
			if r.EventQuestChapterId == chapterId && r.QuestId != questId &&
				r.PossessionType == t.PossessionType && r.TargetUuid == t.TargetUuid {
				return fmt.Errorf("possession %s (type %d) was used in quest %d of chapter %d", t.TargetUuid, t.PossessionType, r.QuestId, chapterId)
			}
		}
	}
	return nil
}

// recordLimitContentWin locks the winning deck's costumes/weapons for the rest
// of the difficulty run; winning the run's last quest ends it and frees them.
func (h *QuestHandler) recordLimitContentWin(user *store.UserState, chapterId, questId int32, nowMillis int64) {
	if h.LimitContent == nil {
		return
	}
	seq, ok := h.LimitContent.SequenceByQuestId[questId]
	if !ok || seq.EventQuestChapterId != chapterId {
		return
	}
	if seq.QuestIds[len(seq.QuestIds)-1] == questId {
		clearLimitContentLocks(user, chapterId)
		return
	}
	deck, ok := battleDeck(user, questId)
	if !ok {
		return
	}
	rows := withoutLocks(user.Ext.Quest.LimitContentRestricted, func(r store.LimitContentRestricted) bool {
		return r.EventQuestChapterId == chapterId && r.QuestId == questId
	})
	for _, t := range h.deckLimitTargets(user, chapterId, deck, nowMillis) {
		t.EventQuestChapterId = chapterId
		t.QuestId = questId
		t.DeckRestrictedUuid = uuid.New().String()
		t.LatestVersion = nowMillis
		rows = append(rows, t)
	}
	user.Ext.Quest.LimitContentRestricted = rows
}

func clearLimitContentLocks(user *store.UserState, chapterId int32) {
	user.Ext.Quest.LimitContentRestricted = withoutLocks(user.Ext.Quest.LimitContentRestricted, func(r store.LimitContentRestricted) bool {
		return r.EventQuestChapterId == chapterId
	})
}

// withoutLocks copies rows minus the dropped ones (nil when none are left), so
// a save snapshot sharing the old slice is not changed.
func withoutLocks(rows []store.LimitContentRestricted, drop func(store.LimitContentRestricted) bool) []store.LimitContentRestricted {
	var out []store.LimitContentRestricted
	for _, r := range rows {
		if !drop(r) {
			out = append(out, r)
		}
	}
	return out
}

// LimitContentRunQuests lists the quests of questId's difficulty run in a
// chapter, or just questId when it is not in one.
func (h *QuestHandler) LimitContentRunQuests(chapterId, questId int32) []int32 {
	if h.LimitContent != nil {
		if seq, ok := h.LimitContent.SequenceByQuestId[questId]; ok && seq.EventQuestChapterId == chapterId {
			return seq.QuestIds
		}
	}
	return []int32{questId}
}

// ResetLimitContentRun starts a chapter's difficulty run over
// (ResetLimitContentQuestProgress): the run's quests lose their limit-content
// clear status and the chapter's deck locks go.
func (h *QuestHandler) ResetLimitContentRun(user *store.UserState, chapterId int32, quests []int32) {
	for _, q := range quests {
		delete(user.QuestLimitContentStatus, q)
	}
	clearLimitContentLocks(user, chapterId)
}
