// Arena season dates for the season turns, for Android and iOS (the iOS
// launcher builds this file too).
//
// Bunker's content patcher keeps every Arena season open (to 2099), and the
// server then gives the seasons that share the latest season's grades and
// reward tables four-week turns (pvp.Catalog.Season). The game reads a
// season's dates from its master data (EntityMPvpSeason), so the Arena's
// Period line showed 2099 and the game never saw a season end. Here the
// game's loaded master data gets each such season's turn: the one in force
// has its current four weeks, the others their last turn (or the next one,
// before their first). The server's rule is followed exactly, with the
// game's own clock (CalculatorDateTime.UnixTimeNow), which is the server's.
//
// With the game's own dates (the Original calendar, at any speed) at most
// one season is open at a time and nothing is changed. The dates are worked
// out from the master data as loaded each time, so a calendar change or a
// new loop's data is followed. Other tables keep their dates: the season gets
// new MPDateTime objects rather than having shared ones changed.
#include "arena_season.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

#define SEASON_WEEKS 4
static const int64_t kWeek = 7LL * 24 * 3600 * 1000;
// 1970-01-05 00:00 GMT-8, a Monday at the Arena's weekly reset (the game's time zone has no daylight saving).
static const int64_t kMonday = 4LL * 24 * 3600 * 1000 + 8LL * 3600 * 1000;
#define MAX_SEASONS 256

static int64_t week_of(int64_t millis) {
    int64_t since = millis - kMonday;
    int64_t weeks = since >= 0 ? since / kWeek : -((-since + kWeek - 1) / kWeek);
    return kMonday + weeks * kWeek;
}

static int64_t mod(int64_t a, int64_t n) { return ((a % n) + n) % n; }

int arena_season_turns(const ArenaSeasonRow *rows, int count, int64_t now, int64_t *start, int64_t *end) {
    int open[MAX_SEASONS], n = 0;
    for (int i = 0; i < count; i++) {
        start[i] = rows[i].start, end[i] = rows[i].end;
        if (n < MAX_SEASONS && !rows[i].invalid && rows[i].start <= now && now < rows[i].end) open[n++] = i;
    }
    if (n <= 1) return 0;
    // Oldest first, ties in table order (the server's stable sort).
    for (int i = 1; i < n; i++)
        for (int j = i; j > 0 && rows[open[j - 1]].start > rows[open[j]].start; j--) {
            int t = open[j]; open[j] = open[j - 1]; open[j - 1] = t;
        }
    const ArenaSeasonRow *latest = &rows[open[n - 1]];
    int turns[MAX_SEASONS], k = 0;
    for (int i = 0; i < n; i++) {
        const ArenaSeasonRow *s = &rows[open[i]];
        if (s->grade == latest->grade && s->season_rank == latest->season_rank && s->weekly_rank == latest->weekly_rank) turns[k++] = open[i];
    }
    const int64_t first = week_of(latest->start), length = SEASON_WEEKS * kWeek;
    int64_t turn = (week_of(now) - first) / length;
    if (turn < 0) turn = 0;
    int changed = 0;
    for (int p = 0; p < k; p++) {
        // Turn t goes to turns[(k-1+t) % k], so this season's turns are t = p+1 (mod k): its latest one up to now.
        int64_t t = turn - mod(turn - (p + 1), k);
        if (t < 0) t += k;  // not had a turn yet: its first
        int i = turns[p];
        start[i] = first + t * length, end[i] = start[i] + length;
        changed += start[i] != rows[i].start || end[i] != rows[i].end;
    }
    return changed;
}

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void *(*object_new)(void *klass);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
} il2cpp;

#define FIELD(object, offset, type) (*(type *)((uint8_t *)(object) + (offset)))

static void (*report)(const char *message);
static int loaded, failed;
static void *k_date;
static Method *m_master, *m_table, *m_now, *m_set_start, *m_set_end;
static size_t f_data, f_id, f_start, f_end, f_invalid, f_weekly_rank, f_season_rank, f_grade, f_unix;

// The master data as the game loaded it: its season rows and their own dates.
static void *seen_rows;
static ArenaSeasonRow original[MAX_SEASONS];
static int64_t applied_week = -1;  // the week the dates were last set for

static void say(const char *message) { if (report) report(message); }

static void *find_class(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), ns, name);
        if (klass) return klass;
    }
    return NULL;
}

static void *call(Method *method, void *object, void **args) {
    void *exception = NULL;
    void *result = il2cpp.runtime_invoke(method, object, args, &exception);
    return exception ? NULL : result;
}

static int offset(void *klass, const char *name, size_t *out) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (!field) return -1;
    *out = il2cpp.field_get_offset(field);
    return 0;
}

// DatabaseDefine.get_Master, its season table, the season's fields and setters, and the game's clock. 0 when found.
static int lookup(void) {
    void *define = find_class("Dark", "DatabaseDefine"), *master = find_class("Dark", "DarkMasterMemoryDatabase");
    void *table = find_class("Dark.Tables", "EntityMPvpSeasonTable"), *season = find_class("Dark", "EntityMPvpSeason");
    void *clock = find_class("Subsystem.Calculator.Outgame", "CalculatorDateTime");
    k_date = find_class("MessagePack", "MPDateTime");
    if (!define || !master || !table || !season || !clock || !k_date) return -1;
    m_master = il2cpp.class_get_method_from_name(define, "get_Master", 0);
    m_table = il2cpp.class_get_method_from_name(master, "get_EntityMPvpSeasonTable", 0);
    m_now = il2cpp.class_get_method_from_name(clock, "UnixTimeNow", 0);
    m_set_start = il2cpp.class_get_method_from_name(season, "set_SeasonStartDatetime", 1);
    m_set_end = il2cpp.class_get_method_from_name(season, "set_SeasonEndDatetime", 1);
    if (!m_master || !m_table || !m_now || !m_set_start || !m_set_end) return -1;
    if (offset(table, "data", &f_data)) f_data = 0x10;  // TableBase<T>.data, its first field
    return offset(season, "<PvpSeasonId>k__BackingField", &f_id) || offset(season, "<SeasonStartDatetime>k__BackingField", &f_start) ||
           offset(season, "<SeasonEndDatetime>k__BackingField", &f_end) || offset(season, "<IsInvalid>k__BackingField", &f_invalid) ||
           offset(season, "<PvpWeeklyRankRewardRankGroupId>k__BackingField", &f_weekly_rank) ||
           offset(season, "<PvpSeasonRankRewardRankGroupId>k__BackingField", &f_season_rank) ||
           offset(season, "<PvpGradeGroupId>k__BackingField", &f_grade) || offset(k_date, "<UnixTime>k__BackingField", &f_unix);
}

static int64_t date(void *entity, size_t field) {
    void *value = FIELD(entity, field, void *);
    return value ? FIELD(value, f_unix, int64_t) : 0;
}

static int put(void *entity, Method *setter, int64_t millis) {
    void *value = il2cpp.object_new(k_date);
    if (!value) return -1;
    FIELD(value, f_unix, int64_t) = millis;
    void *exception = NULL;
    il2cpp.runtime_invoke(setter, entity, (void *[]){value}, &exception);
    return exception ? -1 : 0;
}

void arena_season_dates(void) {
    if (!loaded || failed) return;
    if (!m_master && lookup()) {
        failed = 1;
        return say("Arena seasons: unsupported game; the Period line keeps the master data's dates");
    }
    void *master = call(m_master, NULL, NULL);
    void *table = master ? call(m_table, master, NULL) : NULL;
    void *rows = table ? FIELD(table, f_data, void *) : NULL;
    if (!rows) return;  // master data not loaded yet
    int count = (int)FIELD(rows, 24, size_t);
    if (count <= 0 || count > MAX_SEASONS) return;
    void **items = (void **)((uint8_t *)rows + 32);
    if (rows != seen_rows) {
        // New master data (first start, a calendar change, the next loop): its own dates.
        for (int i = 0; i < count; i++) {
            void *s = items[i];
            original[i] = (ArenaSeasonRow){FIELD(s, f_id, int32_t), date(s, f_start), date(s, f_end), FIELD(s, f_grade, int32_t),
                                           FIELD(s, f_season_rank, int32_t), FIELD(s, f_weekly_rank, int32_t), FIELD(s, f_invalid, uint8_t)};
        }
        seen_rows = rows;
        applied_week = -1;
    }
    void *boxed = call(m_now, NULL, NULL);
    if (!boxed) return;
    int64_t now = FIELD(boxed, 0x10, int64_t);  // a boxed long
    if (week_of(now) == applied_week) return;  // turns change only at a weekly reset
    int64_t start[MAX_SEASONS], end[MAX_SEASONS];
    int changed = arena_season_turns(original, count, now, start, end), current = 0;
    for (int i = 0; i < count; i++) {
        void *s = items[i];
        if (date(s, f_start) != start[i] && put(s, m_set_start, start[i])) return;
        if (date(s, f_end) != end[i] && put(s, m_set_end, end[i])) return;
        if ((start[i] != original[i].start || end[i] != original[i].end) && start[i] <= now && now < end[i]) current = original[i].id;
    }
    if (applied_week == -1 || changed) {
        char line[160];
        if (current) snprintf(line, sizeof line, "Arena seasons: %d season dates set to their four-week turns; season %d in force", changed, current);
        else snprintf(line, sizeof line, "Arena seasons: the game's own dates (no turns)");
        say(line);
    }
    applied_week = week_of(now);
}

int arena_season_init(void *(*resolve)(const char *name), void (*log)(const char *message)) {
    report = log;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(object_new) LOAD(runtime_invoke)
#undef LOAD
    loaded = 1;
    return 0;
}
