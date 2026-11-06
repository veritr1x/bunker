package runtime

import (
	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/model"
)

// ModRewrite is the granter's Rewrite for the mods' conversions (modRewrite),
// for a granter built outside the server: Pod Programs › Gift checks a gift as
// what will arrive when it is claimed.
func ModRewrite(items []masterdata.EntityMConsumableItem, goldItemId int32) func(model.PossessionType, int32, int32) (model.PossessionType, int32, int32) {
	return modRewrite(items, goldItemId)
}
