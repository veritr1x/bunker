package userdata

// IUserCharacterViewerField: the character viewer fields the player was told
// were unlocked (store.ExtState.CharacterViewerFields). The client entity has
// exactly userId, characterViewerFieldId, releaseDatetime and latestVersion.

import (
	"lunar-tear/server/internal/store"
	"lunar-tear/server/internal/utils"
)

func init() {
	register("IUserCharacterViewerField", func(user store.UserState) string {
		s, _ := utils.EncodeJSONMaps(characterViewerFieldRecords(user)...)
		return s
	})
}

func characterViewerFieldRecords(user store.UserState) []map[string]any {
	ids := sortedKeys(user.Ext.CharacterViewerFields)
	rows := make([]map[string]any, 0, len(ids))
	for _, id := range ids {
		at := user.Ext.CharacterViewerFields[id]
		rows = append(rows, map[string]any{
			"userId":                 user.UserId,
			"characterViewerFieldId": id,
			"releaseDatetime":        at,
			"latestVersion":          at,
		})
	}
	return rows
}

func viewerChangedTables(before, after *store.UserState) []string {
	if !mapsEqualSimple(before.Ext.CharacterViewerFields, after.Ext.CharacterViewerFields) {
		return []string{"IUserCharacterViewerField"}
	}
	return nil
}

func viewerKeyFields(table string) []string {
	if table == "IUserCharacterViewerField" {
		return []string{"userId", "characterViewerFieldId"}
	}
	return nil
}
