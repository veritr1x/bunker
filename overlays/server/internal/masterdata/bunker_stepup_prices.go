package masterdata

import (
	"fmt"
	"strings"

	"lunar-tear/server/internal/model"
)

// stepUpPrice is one step of a multi-step summon: its 10x price, and whether
// only paid gems count. A free step is {0, false}.
type stepUpPrice struct {
	Gems int32
	Paid bool
}

// stepUpPrices are the prices on each multi-step summon's step pages in the
// game files (ui/gacha/en/step_up_<group>001/appeal/000n, "Required Gems"),
// by the group in its banner asset name. Read by eye from every page and
// checked against text recognition of the same pages. Group 511 shows no
// prices and 576's overview and step pages disagree; neither is offered.
var stepUpPrices = map[int32][]stepUpPrice{
	501: {{1500, true}, {2000, true}, {3000, true}, {3000, true}, {3000, true}},
	503: {{1500, true}, {1500, true}, {2000, true}, {2500, true}, {3000, true}},
	505: {{3000, true}, {0, false}, {2000, true}, {0, false}, {5000, true}},
	507: {{3000, false}, {3000, false}, {3000, false}, {3000, false}, {3000, false}},
	509: {{3000, true}, {0, false}, {2000, true}, {0, false}, {5000, true}},
	510: {{3000, false}, {1500, false}, {3000, false}, {1500, false}, {3000, false}},
	512: {{3000, true}, {3000, true}, {3000, true}, {3000, true}, {3000, true}},
	513: {{3000, true}, {3000, true}, {3000, true}, {3000, true}, {3000, true}},
	514: {{3000, false}, {3000, false}, {3000, false}, {3000, false}},
	515: {{3000, true}, {3000, true}, {3000, true}, {3000, true}, {3000, true}},
	516: {{1500, false}, {3000, false}, {3000, false}, {3000, false}, {3000, false}},
	517: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	519: {{3000, true}, {3000, true}, {3000, true}},
	522: {{3000, true}, {3000, true}, {3000, true}},
	523: {{3000, true}, {3000, true}, {3000, true}, {3000, true}, {3000, true}},
	524: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
	525: {{3000, false}, {3000, false}, {3000, false}, {3000, false}},
	527: {{3000, true}, {3000, true}, {3000, true}},
	530: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
	531: {{3000, false}, {1500, false}, {3000, false}, {1500, false}, {3000, false}},
	532: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	533: {{3000, true}, {3000, true}, {3000, true}},
	534: {{3000, true}, {3000, true}, {3000, true}},
	535: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	536: {{3000, true}, {3000, true}, {3000, true}},
	537: {{3000, true}, {3000, true}, {3000, true}},
	538: {{3000, true}, {3000, true}, {3000, true}},
	539: {{3000, true}, {3000, true}, {3000, true}, {3000, true}, {3000, true}},
	540: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	550: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
	551: {{3000, true}, {3000, true}, {3000, true}},
	552: {{3000, false}, {3000, false}, {3000, false}},
	553: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	554: {{3000, false}, {1500, false}, {3000, false}, {1500, false}, {3000, false}},
	555: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	556: {{3000, false}, {1500, false}, {3000, false}, {1500, false}, {3000, false}},
	557: {{3000, true}, {3000, true}, {3000, true}},
	558: {{3000, true}, {3000, true}, {3000, true}},
	559: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
	560: {{3000, true}, {3000, true}, {3000, true}},
	561: {{2000, true}, {3000, true}, {5000, true}},
	562: {{0, false}, {1500, false}, {3000, false}, {3000, false}, {3000, false}},
	563: {{3000, true}, {3000, true}, {3000, true}},
	565: {{1500, true}, {3000, true}, {3000, true}, {3000, true}},
	566: {{3000, true}, {3000, true}, {3000, true}},
	567: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	568: {{500, true}, {1500, true}, {3000, true}},
	569: {{1500, true}, {3000, true}, {3000, true}, {3000, true}},
	570: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	571: {{500, true}, {1500, true}, {3000, true}},
	572: {{2000, true}, {3000, true}, {5000, true}},
	573: {{3000, true}, {3000, true}, {3000, true}},
	574: {{3000, true}, {3000, true}, {3000, true}},
	575: {{3000, true}, {3000, true}, {3000, true}},
	577: {{3000, true}, {3000, true}, {3000, true}},
	578: {{3000, true}, {3000, true}, {3000, true}},
	579: {{1500, true}, {3000, true}, {3000, true}, {3000, true}},
	580: {{3000, true}, {3000, true}, {3000, true}},
	581: {{3000, true}, {3000, true}, {3000, true}},
	582: {{3000, true}, {3000, true}, {3000, true}},
	583: {{3000, true}, {3000, true}, {3000, true}},
	584: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	585: {{2000, true}, {3000, true}, {5000, true}},
	586: {{3000, true}, {3000, true}, {3000, true}},
	587: {{3000, true}, {3000, true}, {3000, true}},
	588: {{3000, true}, {3000, true}, {3000, true}},
	589: {{3000, true}, {3000, true}, {3000, true}},
	590: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	600: {{2000, true}, {3000, true}, {5000, true}},
	601: {{1500, true}, {3000, true}, {3000, true}, {3000, true}},
	602: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	603: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	604: {{3000, true}, {3000, true}, {3000, true}},
	605: {{3000, true}, {3000, true}, {3000, true}},
	606: {{3000, true}, {3000, true}, {3000, true}},
	607: {{3000, true}, {3000, true}, {3000, true}},
	608: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	609: {{3000, true}, {3000, true}, {3000, true}, {3000, true}},
	610: {{3000, true}, {3000, true}, {3000, true}},
	611: {{2000, true}, {3000, true}, {5000, true}},
	612: {{2000, true}, {0, false}, {3000, true}, {0, false}, {5000, true}},
	613: {{1500, true}, {3000, true}, {3000, true}, {3000, true}},
}

// stepUpGroup is the group in a step-up banner asset name (step_up_<group><step>), or 0.
func stepUpGroup(banner string) int32 {
	var group int32
	if _, err := fmt.Sscanf(strings.TrimPrefix(banner, model.BannerPrefixStepUp), "%3d", &group); err != nil {
		return 0
	}
	return group
}
