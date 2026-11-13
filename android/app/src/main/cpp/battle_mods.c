// Arena battle mods, for Android and iOS (the iOS launcher builds this file
// too): No death, One hit and Zero cooldown, applied live, each battle frame,
// in Arena battles only. The choices are in battle_mods.conf beside the saves
// (battle_mods_settings.c); the MODS button and popup are battle_mods_ui.c.
//
// The game works battles out on the device. Each frame, after the HUD's own
// BattleSystemMenuPresenter.Update (a Unity message, taken over through its
// MethodInfo.methodPointer as bunker_button.c does), the battle is walked the
// way the game walks it and changed only through its own field accessors
// (Dark.Game.TurnBattle.Field*): no game code is changed (iOS cannot write
// code pages).
//
// - The battle: UnityEngine.Object.FindObjectOfType(BattleContext), held by
//   a GC handle until Unity destroys it. Its _userdata is the battle's record.
//   (TurnbaseFrameCounterController._instance, which Display uses, is null in
//   the Arena.)
// - Arena only: KernelTurnBattle.IsCurrentStoryIsPvp(), once per battle.
// - Fighters: FieldBattle ListParameterTeam -> FieldTeam parties ->
//   FieldParty actors. The player's party is the one whose PartyHash is the
//   battle's CurrentPlayerDeckPartyHash. Filler slots (max HP 1,234,567,890)
//   and the defeated are left alone.
// - No death: the player's max and current HP (FieldActorStatus, on the
//   actor's status record) are raised to BATTLE_MODS_HUGE_HP, so no single
//   hit can defeat them; each character's own max is recorded first and
//   given back when No death is switched off.
// - One hit: opponents are held at 1 HP; the game's own damage defeats them.
// - Zero cooldown: the player's active skills' cooldowns (which count up to
//   their max, ready) are held at max.
// If anything is missing the game runs as it was; an exception from the game
// stops the mods for that battle. Every finding is one log line.
#include "battle_mods.h"

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_methods)(void *klass, void **iter);
    const char *(*method_get_name)(Method *method);
    uint32_t (*method_get_param_count)(Method *method);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void *(*class_get_type)(void *klass);
    void *(*type_get_object)(void *type);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
    uint32_t (*gchandle_new)(void *object, int pinned);
    void (*gchandle_free)(uint32_t handle);
    void *(*gchandle_get_target)(uint32_t handle);
    void *(*thread_attach)(void *domain);
    void *(*get_corlib)(void);
} il2cpp;

static struct {
    Method *update;                          // BattleSystemMenuPresenter.Update
    Method *find_object;                     // UnityEngine.Object.FindObjectOfType(Type)
    void *context_type;                      // System.Type of BattleContext
    size_t context_userdata;                 // BattleContext._userdata: the battle's record
    Method *is_pvp;                          // KernelTurnBattle.IsCurrentStoryIsPvp()
    Method *teams, *player_party_hash;       // FieldBattle
    Method *team_parties, *team_id;          // FieldTeam
    Method *party_actors, *party_hash;       // FieldParty
    Method *alive, *status, *skill;          // FieldActor
    Method *hp, *set_hp, *max_hp, *set_max;  // FieldActorStatus
    Method *active_skills;                   // FieldActorSkill
    Method *cooltime, *set_cooltime, *max_cooltime;  // FieldSkill
} game;

static void (*report)(const char *message);
static void (*update_original)(void *self, Method *method);
static void (*hud_hook)(void *presenter);
static char settings_path[1024];
static BattleMods mods;

static void say(const char *message) {
    if (report) report(message);
}

static void *find_class(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), ns, name);
        if (klass) return klass;
    }
    return NULL;
}

static int missing;  // what look_up could not find, for one log line

static Method *method(void *klass, const char *name, int args) {
    Method *m = klass ? il2cpp.class_get_method_from_name(klass, name, args) : NULL;
    if (!m && !missing) {
        char line[200];
        snprintf(line, sizeof line, "Battle mods: missing method %s/%d; no battle mods", name, args);
        say(line);
        missing = 1;
    }
    return m;
}

/** An instance method by name and parameter count, as Unity calls messages (class_get_method_from_name may give a base's). */
static Method *own_method(void *klass, const char *name, int args) {
    void *iter = NULL;
    Method *m;
    while (klass && (m = il2cpp.class_get_methods(klass, &iter)))
        if (!strcmp(il2cpp.method_get_name(m), name) && (int)il2cpp.method_get_param_count(m) == args) return m;
    return NULL;
}

static int look_up(void) {
    const char *tb = "Dark.Game.TurnBattle";
    void *presenter = find_class("Dark.View.HeadUpDisplay", "BattleSystemMenuPresenter");
    void *context = find_class("Adam.Framework.GameKit.TurnBattle", "BattleContext");
    void *object = find_class("UnityEngine", "Object");
    void *kernel = find_class(tb, "KernelTurnBattle");
    void *fbattle = find_class(tb, "FieldBattle"), *fteam = find_class(tb, "FieldTeam"), *fparty = find_class(tb, "FieldParty");
    void *factor = find_class(tb, "FieldActor"), *fstatus = find_class(tb, "FieldActorStatus");
    void *factorskill = find_class(tb, "FieldActorSkill"), *fskill = find_class(tb, "FieldSkill");
    if (!presenter || !context || !object || !kernel || !fbattle || !fteam || !fparty || !factor || !fstatus || !factorskill || !fskill) {
        char line[300];
        snprintf(line, sizeof line, "Battle mods: missing classes (presenter %d context %d kernel %d fields %d%d%d%d%d%d%d); no battle mods",
                 !!presenter, !!context, !!kernel, !!fbattle, !!fteam, !!fparty, !!factor, !!fstatus, !!factorskill, !!fskill);
        say(line);
        return -1;
    }
    void *userdata = il2cpp.class_get_field_from_name(context, "_userdata");
    if (!userdata) { say("Battle mods: missing BattleContext._userdata; no battle mods"); return -1; }
    game.context_userdata = il2cpp.field_get_offset(userdata);
    game.context_type = il2cpp.type_get_object(il2cpp.class_get_type(context));
    game.update = own_method(presenter, "Update", 0);
    if (!game.update || !game.context_type) { say("Battle mods: missing BattleSystemMenuPresenter.Update; no battle mods"); return -1; }
    game.find_object = method(object, "FindObjectOfType", 1);
    game.is_pvp = method(kernel, "IsCurrentStoryIsPvp", 0);
    game.teams = method(fbattle, "FieldTurnBattleBattleListParameterTeam", 1);
    game.player_party_hash = method(fbattle, "FieldTurnBattleCurrentPlayerDeckPartyHash", 1);
    game.team_parties = method(fteam, "FieldTurnBattleTeamOwnParameterParties", 1);
    game.team_id = method(fteam, "FieldTurnBattleTeamOwnTeamId", 1);
    game.party_actors = method(fparty, "FieldTurnBattlePartyActors", 1);
    game.party_hash = method(fparty, "FieldTurnBattlePartyPartyHash", 1);
    game.alive = method(factor, "FieldTurnBattleActorIsAlive", 1);
    game.status = method(factor, "FieldTurnBattleActorStatus", 1);
    game.skill = method(factor, "FieldTurnBattleActorSkill", 1);
    game.hp = method(fstatus, "FieldTurnBattleActorStatusDynamicCurrentHp", 1);
    game.set_hp = method(fstatus, "FieldTurnBattleActorStatusDynamicCurrentHp", 3);
    game.max_hp = method(fstatus, "FieldTurnBattleActorStatusDynamicHp", 1);
    game.set_max = method(fstatus, "FieldTurnBattleActorStatusDynamicHp", 3);
    game.active_skills = method(factorskill, "FieldTurnBattleActorSkillParameterActiveSkillContainer", 1);
    game.cooltime = method(fskill, "FieldTurnBattleSkillDynamicCurrentCooltime", 1);
    game.set_cooltime = method(fskill, "FieldTurnBattleSkillDynamicCurrentCooltime", 2);
    game.max_cooltime = method(fskill, "FieldTurnBattleSkillDynamicMaxCooltime", 1);
    return missing ? -1 : 0;
}

// --- The live battle ---------------------------------------------------------

static int refused;  // the game threw: no mods until the next battle

static void *call(Method *m, void **args) {
    void *exception = NULL;
    void *result = il2cpp.runtime_invoke(m, NULL, args, &exception);
    if (exception) {
        if (!refused) {
            char line[200];
            snprintf(line, sizeof line, "Battle mods: the game refused %s; no mods until the next battle", il2cpp.method_get_name(m));
            say(line);
        }
        refused = 1;
        return NULL;
    }
    return result;
}

/** A boxed int's or bool's value (the object header is two pointers); fallback when absent. */
static int32_t unbox(void *boxed, int32_t fallback) { return boxed ? *(int32_t *)((uint8_t *)boxed + 16) : fallback; }
/** A reference-type id's int (PartyHash._hash, at the first field). */
static int32_t id_of(void *object, int32_t fallback) { return object ? *(int32_t *)((uint8_t *)object + 16) : fallback; }

/** List<T> items (an array: elements from +32) and size; 0 when absent. */
static int list_items(uint8_t *list, uint8_t **items) {
    if (!list) return 0;
    *items = *(uint8_t **)(list + 16);
    return *items ? *(int32_t *)(list + 24) : 0;
}
/** The List<DataStructure> a ListParameter* object holds in its first field. */
static int wrapped_list(void *wrapper, uint8_t **items) { return list_items(wrapper ? *(uint8_t **)((uint8_t *)wrapper + 16) : NULL, items); }
static void *item(uint8_t *items, int i) { return *(void **)(items + 32 + 8 * i); }

static uint32_t held;           // GC handle on the BattleContext
static void *battle;            // its record, for this battle
static int arena = -1;          // -1 not known yet
static int sides_known;      // the player's party is found (or the fallback taken) for this battle
static int32_t player_hash;  // the battle's CurrentPlayerDeckPartyHash
static int player_team;      // the fallback: the team whose id is 1 (the player's in every battle seen)
static int hash_matched;     // a party had the player's hash
static int frames_since_look;

#define MAX_ACTORS 32
static struct { void *actor; int32_t real_max; } recorded[MAX_ACTORS];

static void new_battle(void *record) {
    battle = record;
    arena = -1;
    refused = 0;
    sides_known = 0;
    memset(recorded, 0, sizeof recorded);
}

/** The character's own max HP, recorded the first time it is seen; 0 when there is no room. */
static int32_t real_max_of(void *actor, int32_t max) {
    for (int i = 0; i < MAX_ACTORS; i++) {
        if (recorded[i].actor == actor) return recorded[i].real_max;
        if (!recorded[i].actor) {
            recorded[i].actor = actor;
            recorded[i].real_max = max;
            return max;
        }
    }
    return 0;
}

/** The live battle's record, or NULL; looked up at most every 30 frames while there is none. */
static void *current_battle(void) {
    uint8_t *context = held ? il2cpp.gchandle_get_target(held) : NULL;
    if (context && !*(void **)(context + 16)) context = NULL;  // destroyed by Unity: m_CachedPtr cleared
    if (!context) {
        if (held) { il2cpp.gchandle_free(held); held = 0; }
        if (battle) new_battle(NULL);
        if (frames_since_look++ % 30) return NULL;
        void *args[] = {game.context_type};
        context = call(game.find_object, args);
        refused = 0;  // a refusal here is not the battle's
        if (!context) return NULL;
        held = il2cpp.gchandle_new(context, 0);
    }
    void *record = *(void **)(context + game.context_userdata);
    if (record != battle) new_battle(record);
    return record;
}

static void apply_player(void *actor, void *status) {
    void *args[] = {status};
    int32_t hp = unbox(call(game.hp, args), -1), max = unbox(call(game.max_hp, args), -1);
    if (hp < 0 || max <= 0 || battle_mods_is_filler(max)) return;
    // The own max is the one seen first, before No death raises it.
    int32_t real = real_max_of(actor, max);
    if (real <= 0) return;
    int32_t want_max = battle_mods_player_max(mods.no_death, real);
    if (want_max != max) { void *a[] = {status, actor, &want_max}; call(game.set_max, a); }
    int32_t want_hp = battle_mods_player_hp(mods.no_death, hp, real);
    if (want_hp != hp) { void *a[] = {status, actor, &want_hp}; call(game.set_hp, a); }
}

static void apply_cooldowns(void *actor) {
    void *args[] = {actor};
    void *record = call(game.skill, args);
    void *rargs[] = {record};
    uint8_t *container = record ? call(game.active_skills, rargs) : NULL;
    uint8_t *dict = container ? *(uint8_t **)(container + 16) : NULL;  // ListParameterSkill.skills
    if (!dict) return;
    uint8_t *entries = *(uint8_t **)(dict + 24);                      // Dictionary.entries
    int count = *(int32_t *)(dict + 32);                              // Dictionary.count
    for (int e = 0; entries && e < count && !refused; e++) {
        uint8_t *entry = entries + 32 + 24 * e;  // hashCode, next, key, value
        void *skill = *(int32_t *)entry >= 0 ? *(void **)(entry + 16) : NULL;
        if (!skill) continue;
        void *sargs[] = {skill};
        int32_t cur = unbox(call(game.cooltime, sargs), -1), max = unbox(call(game.max_cooltime, sargs), -1);
        int32_t want = battle_mods_cooltime(1, cur, max);
        if (cur >= 0 && want != cur) { void *a[] = {skill, &want}; call(game.set_cooltime, a); }
    }
}

static void apply_opponent(void *actor, void *status) {
    void *args[] = {status};
    int32_t hp = unbox(call(game.hp, args), -1), max = unbox(call(game.max_hp, args), -1);
    if (hp < 0 || battle_mods_is_filler(max)) return;
    int32_t want = battle_mods_opponent_hp(1, hp);
    if (want != hp) { void *a[] = {status, actor, &want}; call(game.set_hp, a); }
}

/** Which party is the player's: the one with the battle's CurrentPlayerDeckPartyHash, else (one log line)
 * the team whose id is 1. Logs each team and party once per battle. -1 while the battle is not set up yet. */
static int find_sides(void *record) {
    void *bargs[] = {record};
    player_hash = id_of(call(game.player_party_hash, bargs), -1);
    uint8_t *teams;
    int team_count = wrapped_list(call(game.teams, bargs), &teams);
    if (refused || team_count < 2) return -1;
    char line[400];
    int used = snprintf(line, sizeof line, "Battle mods: player party hash %d;", player_hash);
    hash_matched = 0;
    for (int t = 0; t < team_count && !refused; t++) {
        void *targs[] = {item(teams, t)};
        if (!targs[0]) continue;
        int32_t team = id_of(call(game.team_id, targs), -1);
        uint8_t *parties;
        int party_count = wrapped_list(call(game.team_parties, targs), &parties);
        for (int p = 0; p < party_count && !refused; p++) {
            void *pargs[] = {item(parties, p)};
            int32_t hash = pargs[0] ? id_of(call(game.party_hash, pargs), -1) : -1;
            if (hash == player_hash) hash_matched = 1;
            if (used < (int)sizeof line) used += snprintf(line + used, sizeof line - used, " team %d party %d", team, hash);
        }
    }
    if (refused) return -1;
    player_team = 1;
    say(line);
    if (!hash_matched) say("Battle mods: no party has the player's hash; team 1 is taken as the player's");
    sides_known = 1;
    return 0;
}

static int any_recorded(void) { return recorded[0].actor != NULL; }

static void tick(void) {
    void *record = current_battle();
    if (!record || refused) return;
    if (arena < 0) {
        arena = unbox(call(game.is_pvp, NULL), 0) & 0xff;
        say(arena ? "Battle mods: Arena battle" : "Battle mods: not an Arena battle; left as it is");
    }
    // Nothing on and nothing to give back: leave the battle alone.
    if (!arena || refused || (!mods.no_death && !mods.one_hit && !mods.zero_cooldown && !any_recorded())) return;
    void *bargs[] = {record};
    if (!sides_known && find_sides(record)) return;
    uint8_t *teams;
    int team_count = wrapped_list(call(game.teams, bargs), &teams);
    for (int t = 0; t < team_count && !refused; t++) {
        void *targs[] = {item(teams, t)};
        uint8_t *parties;
        int party_count = targs[0] ? wrapped_list(call(game.team_parties, targs), &parties) : 0;
        for (int p = 0; p < party_count && !refused; p++) {
            void *pargs[] = {item(parties, p)};
            if (!pargs[0]) continue;
            int mine = hash_matched ? id_of(call(game.party_hash, pargs), -1) == player_hash
                                    : id_of(call(game.team_id, targs), -1) == player_team;
            uint8_t *actors;
            int actor_count = wrapped_list(call(game.party_actors, pargs), &actors);
            for (int a = 0; a < actor_count && !refused; a++) {
                void *actor = item(actors, a);
                void *aargs[] = {actor};
                if (!actor || !(unbox(call(game.alive, aargs), 0) & 0xff)) continue;
                void *status = call(game.status, aargs);
                if (!status) continue;
                if (mine) {
                    apply_player(actor, status);
                    if (mods.zero_cooldown) apply_cooldowns(actor);
                } else if (mods.one_hit) {
                    apply_opponent(actor, status);
                }
            }
        }
    }
}

int battle_mods_in_arena(void) { return battle && arena == 1 && !refused; }

static void update_hook(void *self, Method *m) {
    update_original(self, m);
    tick();
    if (hud_hook) hud_hook(self);
}

// --- Settings and start-up ---------------------------------------------------

BattleMods battle_mods_get(void) { return mods; }

void battle_mods_set(BattleMods next) {
    mods = next;
    if (battle_mods_save(settings_path, &mods)) say("Battle mods: the settings could not be saved");
}

void battle_mods_set_hud_hook(void (*hud)(void *presenter)) { hud_hook = hud; }

// Waits for IL2CPP to finish loading the game's assemblies, as bunker_button.c does
// (asking il2cpp_domain_get too early on iOS kept the game on a black screen).
static void *install(void *unused) {
    (void)unused;
    for (int i = 0; !il2cpp.get_corlib(); i++) {
        if (i > 1200) { say("Battle mods: the game did not start; no battle mods"); return NULL; }
        usleep(100000);
    }
    size_t last = 0;
    for (int i = 0, steady = 0; steady < 20; i++) {
        if (i > 1200) { say("Battle mods: the game did not start; no battle mods"); return NULL; }
        size_t count = 0;
        if (il2cpp.domain_get()) il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
        steady = count && count == last ? steady + 1 : 0;
        last = count;
        usleep(100000);
    }
    il2cpp.thread_attach(il2cpp.domain_get());
    if (look_up()) return NULL;
    update_original = (void (*)(void *, Method *))game.update->pointer;
    game.update->pointer = (void *)update_hook;
    char line[160];
    snprintf(line, sizeof line, "Battle mods: ready (no death %s, one hit %s, zero cooldown %s)",
             mods.no_death ? "on" : "off", mods.one_hit ? "on" : "off", mods.zero_cooldown ? "on" : "off");
    say(line);
    return NULL;
}

int battle_mods_init(void *(*resolve)(const char *name), void (*log)(const char *message), const char *path) {
    report = log;
    if (!path || strlen(path) >= sizeof settings_path) return -1;
    snprintf(settings_path, sizeof settings_path, "%s", path);
    battle_mods_load(settings_path, &mods);
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_methods)
    LOAD(method_get_name) LOAD(method_get_param_count) LOAD(class_get_method_from_name) LOAD(class_get_field_from_name)
    LOAD(field_get_offset) LOAD(class_get_type) LOAD(type_get_object) LOAD(runtime_invoke) LOAD(gchandle_new)
    LOAD(gchandle_free) LOAD(gchandle_get_target) LOAD(thread_attach) LOAD(get_corlib)
#undef LOAD
    pthread_t thread;
    if (pthread_create(&thread, NULL, install, NULL)) return -1;
    pthread_detach(thread);
    return 0;
}
