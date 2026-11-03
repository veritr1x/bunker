package service

import (
	"testing"

	"lunar-tear/server/internal/masterdata"
	"lunar-tear/server/internal/utils"
)

// japaneseLaunchEnd is the end of Japan's launch login bonus (2021-03-31);
// Global's launch bonus, the same ID, opened in July 2021.
const japaneseLaunchEnd = int64(1617235200000)

// japaneseMaster reports whether the loaded master data is Japan's, whose
// summons, bonuses and events have their own dates. Call after the master
// is loaded.
func japaneseMaster(t *testing.T) bool {
	t.Helper()
	rows, err := utils.ReadTable[masterdata.EntityMLoginBonus]("m_login_bonus")
	if err != nil {
		t.Fatal(err)
	}
	for _, b := range rows {
		if b.LoginBonusId == 2 {
			return b.StartDatetime < japaneseLaunchEnd
		}
	}
	return false
}
