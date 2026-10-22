package masterdata

// Summons whose title (game text gacha.title.<asset>) marks a special price.
// Prices, limits and guarantees are not in the client data; these follow the
// titles: a free summon is one free 10-pull a day, a "★★★★ guaranteed" summon
// a single 10-pull with a ★4 for 3000 gems, and "paid only" takes paid gems.
// Bonus and newcomer summons are left out.

type specialSummon uint8

const (
	specialFree specialSummon = 1 << iota
	specialPaid
	specialGuaranteed
)

var specialSummons = map[int32]specialSummon{
	43:      specialPaid,                     // Paid-Only Wind-Elemental Summons
	49:      specialGuaranteed,               // NieR Day: Half-Year Anniversary Eve ★★★★ Guaranteed Summons
	52:      specialPaid,                     // Paid Only: Dark-Elemental Summons
	60:      specialPaid,                     // Paid Only: Water-Elemental Summons
	64:      specialFree,                     // 15 Million Global Downloads Commemoration Free Summons
	66:      specialPaid | specialGuaranteed, // Paid Gems Exclusive: 15 Million Global Downloads Commemoration ★★★★ Guaranteed Summons
	70:      specialPaid,                     // Paid Only: Light-Elemental Featured Summons
	85:      specialPaid,                     // Paid Only: Fire-Elemental Summons
	160:     specialPaid | specialGuaranteed, // Paid Only: Abyss Tower Conquest Fire-Guaranteed Summons Ver. 1
	199:     specialFree,                     // Japanese 1.5-Year Anniversary 218+2 Free Summons
	410:     specialGuaranteed,               // Unacquired ★★★★ Character Guaranteed Summons
	416:     specialPaid,                     // Paid Only: Abstract Ruler Summons
	428:     specialPaid,                     // Paid Only: Yuletide Snowfall Summons
	430:     specialPaid,                     // Paid Only: Black Friday Awakening Summons Medal
	433:     specialGuaranteed,               // Unacquired ★★★★ Character Guaranteed Summons
	449:     specialPaid,                     // Paid Only: New Year Countdown Summons
	452:     specialFree,                     // New Year's Commemoration every day Free 10 Summons
	453:     specialPaid | specialGuaranteed, // Paid Only: Unacquired ★★★★ Character Guaranteed Summons
	468:     specialGuaranteed,               // Recollections of Dusk Conquest Barrier-Guaranteed Summons Vol. 1
	472:     specialPaid,                     // Paid Only: Abyssal Festival Summons
	493:     specialPaid | specialGuaranteed, // Paid-Only Attack Character Guaranteed
	501:     specialPaid,                     // The People and the World Release Commemoration Paid-Only Summons Vol.1
	503:     specialPaid | specialGuaranteed, // Paid Only: Fate Boards Conquest Support Character Guaranteed Summons
	510:     specialPaid | specialGuaranteed, // Paid-Only FFXIV Resurrected Crossover Celebration Unacquired ★★★★ Character Guaranteed Summons
	514:     specialPaid | specialGuaranteed, // Paid-Only Abyssal Guaranteed Summons
	515:     specialGuaranteed,               // Resurrected Summer Character Guaranteed Summons
	524:     specialPaid | specialGuaranteed, // Paid Only New Chapter Unacquired ★★★★ Assassin Guaranteed Summons
	545:     specialPaid | specialGuaranteed, // Paid-only RoD Resonant Character Guaranteed Frozen-Heart Revolutionary Conquest Summons
	547:     specialPaid | specialGuaranteed, // Paid-only RoD Resonant Character Guaranteed Frozen-Heart Princess Conquest Summons
	581:     specialFree,                     // Merry[in]carnation x10 free summon
	584:     specialPaid | specialGuaranteed, // Paid-Only New Chapter Commemoration Max Awakening ★★★★ Boor or Exile Guaranteed Summons
	593:     specialPaid | specialGuaranteed, // Paid-Only Winter Holiday Max Awakening Specific Powerful Debris Character Guaranteed Summons
	597:     specialPaid,                     // Paid-Only Re[in]carnation Year-End Appreciation Summons
	9000007: specialPaid,                     // Paid Only: Water-Elemental Summons
}
