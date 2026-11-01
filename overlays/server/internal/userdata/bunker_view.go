package userdata

import (
	"regexp"
	"strconv"

	"lunar-tear/server/internal/gametime"
)

// datetimeField is one "...Datetime": <number> pair in projected JSON (the
// projections are json.Marshal output: compact, quoted keys, plain numbers).
var datetimeField = regexp.MustCompile(`"(\w*Datetime)":(-?\d+)`)

// viewJSON is a table's records as the game sees them in the original-dates
// view (gametime.ToView): every ...Datetime time moves back by the calendar's
// offset; latestVersion and other numbers stay. With the view off it is the
// input itself.
func viewJSON(records string) string {
	if gametime.ViewOffset() == 0 {
		return records
	}
	return datetimeField.ReplaceAllStringFunc(records, func(m string) string {
		sub := datetimeField.FindStringSubmatch(m)
		ms, err := strconv.ParseInt(sub[2], 10, 64)
		if err != nil {
			return m
		}
		return `"` + sub[1] + `":` + strconv.FormatInt(gametime.ToView(ms), 10)
	})
}
