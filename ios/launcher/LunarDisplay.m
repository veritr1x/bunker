// Frame rate and resolution chosen in Pod Programs, for the iPhone and iPad build.
//
// Android rewrites a few game instructions (android/app/src/main/cpp/display_patch.c).
// iOS does not let an app change its code, so this does the same with data and
// calls, through the game's IL2CPP API, once per frame on Unity's main thread:
//
// - Frame rate: Application.targetFrameRate becomes the chosen rate (capped at
//   the screen's maximum), and the performance presets (Config.LevelConfigs)
//   ask OnDemandRendering for it instead of 30. Power saving keeps 10.
// - Resolution: the presets with effects on (the start preset, Highest and
//   High) use the chosen RenderTargetSize; 540p and 640p go below the game's 720p.
//   (Texture size is Android only: Unity takes it on the command line.)
// - Field movement: characters move once per rendered frame while physics
//   keeps a 1/30 s step, so the physics step follows the frame time.
// - Battles advance one 30 Hz step per frame. BattleGame's simulation rate
//   keeps the game's value on frames where 1/30 s has built up and is -0.0 on
//   the frames between, which BattleGame.Update skips. Fractional steps crashed
//   the summon reveal, which runs on the battle code.
// - Story-event zones: an event that waited for the player to walk into a zone
//   and timed out waits on that zone again after a 1.5 s balloon fade, but only
//   notices a player who is still inside. A player who crossed it during the
//   fade is missed and the event stops (6-4: Levania walks off the map); above
//   30 fps the faster story text puts players in that gap. When that fallback
//   (EventTriggerOnStayCollision) starts on a zone the player was in during
//   the last 10 s, it gets the player's collider as if they were still there.
//   The zones are watched each frame by bounds, and the conductors' begin and
//   update are reached through their classes' method tables. This applies at
//   every frame rate, the game's own 30 included.
// - Special Gift Roulette: once the menu's roulette has created ironSource's
//   agent, its showRewardedVideo raises the video's "rewarded" and "closed"
//   events at once instead (roulette_ads.c, shared with Android). This one
//   applies with any settings too.
//
// The choices are read from tools/display.conf (android_display.py writes it).
// The outcome goes to tools/display.status, which Pod Programs shows.
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#include <dlfcn.h>
#include <string.h>

#include "roulette_ads.h"

typedef struct { void *pointer; } LTMethod;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    LTMethod *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void (*field_static_get_value)(void *field, void *value);
    void (*field_static_set_value)(void *field, void *value);
    void (*runtime_class_init)(void *klass);
    void *(*class_get_type)(void *klass);
    void *(*type_get_object)(void *type);
    uint32_t (*gchandle_new)(void *object, bool pinned);
    void (*gchandle_free)(uint32_t handle);
} il2cpp;

static int gFps, gSize;  // 0: the game's own.
static int gAds;  // roulette_ads_route_agent: 0 until the agent exists, then 1 (or -1).
static NSString *gStatusPath;
static CADisplayLink *gLink;

static struct {
    int (*frame_count)(void *);
    float (*unscaled_delta)(void *), (*fixed_delta)(void *);
    void (*set_fixed_delta)(float, void *);
    int (*target_frame_rate)(void *);
    void (*set_target_frame_rate)(int, void *);
    int (*render_interval)(void *);
    void (*set_render_interval)(int, void *);
    void *battle_counter;  // TurnbaseFrameCounterController._instance
    size_t battle_context, battle_game, simulation_rate;
} game;
typedef struct { float center[3], extents[3]; } LTBounds;
static struct {
    void *(*state_actor)(void *);
    size_t user_actor;  // StateActor._currentUserActor
    void *(*actor_collider)(void *game_object, void *);
    void *(*component)(void *game_object, void *type, BOOL inactive, void *);  // GetComponentInChildren(Type, bool)
    void *collider_type;  // System.Type of UnityEngine.Collider
    LTBounds (*bounds)(void *collider, void *);
    void (*zone_init)(void *zone, void *);
    void *(*zone_collider)(void *zone, void *);
    void (*on_stay)(void *self, void *collider, void *);
    size_t stay_zone, stay_invoked, enter_zone;
    void (*stay_begin)(void *, void *), (*stay_update)(void *, void *), (*enter_begin)(void *, void *);
} zones;
typedef struct { void *zone; double until, inside; uint32_t handle; } LTZone;  // The handle keeps the zone's memory.
static LTZone gZones[16];
typedef struct { void *conductor; double since; } LTFallback;
static LTFallback gFallbacks[8];
static int gLastFrame = -1;
static void *gLastBattle;
static float gBattleRate;
static uint32_t gWrittenRate;  // Compared as bits: the game's own 0 (paused) is not our -0.0.
static double gBattleTime;

static void WriteStatus(NSString *text) {
    [text writeToFile:gStatusPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
}

static void *FindClass(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), ns, name);
        if (klass) return klass;
    }
    return NULL;
}

static void *Method(void *klass, const char *name, int args) {
    LTMethod *method = klass ? il2cpp.class_get_method_from_name(klass, name, args) : NULL;
    return method ? method->pointer : NULL;
}

static BOOL FieldOffset(void *klass, const char *name, size_t *offset) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *offset = il2cpp.field_get_offset(field);
    return field != NULL;
}

/** The presets: 30 frames become the chosen rate; the effect presets get the chosen size. */
static BOOL PatchPresets(void) {
    void *config = FindClass("Dark.Component.PerformanceSetting", "Config");
    void *levels = config ? il2cpp.class_get_field_from_name(config, "LevelConfigs") : NULL;
    void *unSave = config ? il2cpp.class_get_field_from_name(config, "UnSavePowerTargetRenderFrameRate") : NULL;
    if (!levels || !unSave) return NO;
    il2cpp.runtime_class_init(config);
    uint8_t *array = NULL;
    il2cpp.field_static_get_value(levels, &array);
    if (!array) return NO;
    size_t length = *(size_t *)(array + 0x18);
    for (size_t i = 0; i < length; i++) {
        int32_t *entry = (int32_t *)(array + 0x20 + i * 12);  // LevelConfig: frame rate, RenderTargetSize, four flags.
        if (gFps && entry[0] == 30) entry[0] = gFps;
        if (gSize && i <= 2) entry[1] = gSize;
    }
    if (gFps) {
        int32_t rate = gFps;
        il2cpp.field_static_set_value(unSave, &rate);
    }
    return YES;
}

static BOOL Resolve(void) {
    void *time = FindClass("UnityEngine", "Time"), *application = FindClass("UnityEngine", "Application");
    void *rendering = FindClass("UnityEngine.Rendering", "OnDemandRendering");
    void *counter = FindClass("Dark.Game.TurnBattle", "TurnbaseFrameCounterController");
    void *component = FindClass("Adam.Framework.GameKit.TurnBattle", "BattleComponent");
    void *context = FindClass("Adam.Framework.GameKit.TurnBattle", "BattleContext");
    void *battle = FindClass("Adam.Framework.GameKit.TurnBattle", "BattleGame");
    game.frame_count = Method(time, "get_frameCount", 0);
    game.unscaled_delta = Method(time, "get_unscaledDeltaTime", 0);
    game.fixed_delta = Method(time, "get_fixedDeltaTime", 0);
    game.set_fixed_delta = Method(time, "set_fixedDeltaTime", 1);
    game.target_frame_rate = Method(application, "get_targetFrameRate", 0);
    game.set_target_frame_rate = Method(application, "set_targetFrameRate", 1);
    game.render_interval = Method(rendering, "get_renderFrameInterval", 0);
    game.set_render_interval = Method(rendering, "set_renderFrameInterval", 1);
    game.battle_counter = counter ? il2cpp.class_get_field_from_name(counter, "_instance") : NULL;
    if (counter) il2cpp.runtime_class_init(counter);
    return game.frame_count && game.unscaled_delta && game.fixed_delta && game.set_fixed_delta && game.target_frame_rate
        && game.set_target_frame_rate && game.render_interval && game.set_render_interval && game.battle_counter
        && FieldOffset(component, "_battleContext", &game.battle_context) && FieldOffset(context, "_game", &game.battle_game)
        && FieldOffset(battle, "_simulationRate", &game.simulation_rate);
}

/** Gives the live battle one whole step each 1/30 s; the game's own rate (1x, fast or paused) is kept as the base. */
static void StepBattle(float delta) {
    uint8_t *counter = NULL;
    il2cpp.field_static_get_value(game.battle_counter, &counter);
    uint8_t *context = counter ? *(uint8_t **)(counter + game.battle_context) : NULL;
    uint8_t *battle = context ? *(uint8_t **)(context + game.battle_game) : NULL;
    if (!battle) return;
    float *rate = (float *)(battle + game.simulation_rate);
    uint32_t bits;
    memcpy(&bits, rate, sizeof bits);
    if (battle != gLastBattle || bits != gWrittenRate) { gLastBattle = battle; gBattleRate = *rate; }
    // At most one step per frame, as before; a long frame doesn't build a backlog.
    gBattleTime += 30.0 * delta;
    float written = -0.f;
    if (gBattleTime >= 1.0) { gBattleTime = gBattleTime >= 2.0 ? 0.0 : gBattleTime - 1.0; written = gBattleRate; }
    memcpy(&gWrittenRate, &written, sizeof written);
    *rate = written;
}

/** Whether a Unity object still exists: destroyed ones (a scene unloading) clear m_CachedPtr. */
static BOOL Alive(void *object) {
    return object && *(void **)((uint8_t *)object + 0x10);
}

static void Unwatch(LTZone *zone) {
    if (zone->handle) il2cpp.gchandle_free(zone->handle);
    *zone = (LTZone){0};
}

/** EventTriggerOnEnterCollision.OnStateBegin: the event starts waiting on a zone; watch it for a minute. */
static void ZoneEnterBegin(void *self, void *method) {
    zones.enter_begin(self, method);
    void *zone = *(void **)((uint8_t *)self + zones.enter_zone);
    if (!zone) return;
    int slot = 0;
    for (int i = 0; i < 16; i++) {
        if (gZones[i].zone == zone) { slot = i; break; }
        if (gZones[i].until < gZones[slot].until) slot = i;
    }
    if (gZones[slot].zone != zone) {
        Unwatch(&gZones[slot]);
        gZones[slot] = (LTZone){zone, 0, -1e9, il2cpp.gchandle_new(zone, false)};
    }
    gZones[slot].until = CACurrentMediaTime() + 60;
}

/** EventTriggerOnStayCollision.OnStateBegin: a fallback starts on a zone the player may have just crossed. */
static void ZoneStayBegin(void *self, void *method) {
    zones.stay_begin(self, method);
    int slot = 0;
    for (int i = 0; i < 8; i++) if (gFallbacks[i].conductor == self || !gFallbacks[i].conductor) { slot = i; break; }
    gFallbacks[slot] = (LTFallback){self, CACurrentMediaTime()};
}

/** The player's collider (what OnStay compares with), or NULL. */
static void *PlayerCollider(void) {
    uint8_t *actor = zones.state_actor(NULL);
    void *body = actor ? *(void **)(actor + zones.user_actor) : NULL;
    void *object = Alive(body) ? zones.actor_collider(body, NULL) : NULL;
    void *collider = Alive(object) ? zones.component(object, zones.collider_type, NO, NULL) : NULL;
    return Alive(collider) ? collider : NULL;
}

/** EventTriggerOnStayCollision.OnStateUpdate (the empty one it inherits): continues a fallback the player crossed. */
static void ZoneStayUpdate(void *self, void *method) {
    zones.stay_update(self, method);
    for (int i = 0; i < 8; i++) {
        if (gFallbacks[i].conductor != self) continue;
        double since = gFallbacks[i].since;
        gFallbacks[i].conductor = NULL;
        void *zone = *(void **)((uint8_t *)self + zones.stay_zone);
        for (int z = 0; zone && z < 16; z++) {
            if (gZones[z].zone != zone || gZones[z].inside < since - 10) continue;
            void *collider = PlayerCollider();
            if (collider && !*((uint8_t *)self + zones.stay_invoked)) zones.on_stay(self, collider, NULL);
            if (*((uint8_t *)self + zones.stay_invoked))
                NSLog(@"[LunarTear] Story event continued: the player passed its zone %.1f s ago", since - gZones[z].inside);
        }
    }
}

static BOOL Overlaps(LTBounds a, LTBounds b) {
    for (int i = 0; i < 3; i++)
        if (fabsf(a.center[i] - b.center[i]) > a.extents[i] + b.extents[i]) return NO;
    return YES;
}

/** Notes when the player is inside a watched zone. */
static void WatchZones(void) {
    double now = CACurrentMediaTime();
    void *player = NULL;
    for (int i = 0; i < 16; i++) {
        if (!gZones[i].zone) continue;
        if (gZones[i].until < now || !Alive(gZones[i].zone)) { Unwatch(&gZones[i]); continue; }
        if (!player && !(player = PlayerCollider())) return;
        zones.zone_init(gZones[i].zone, NULL);
        void *collider = zones.zone_collider(gZones[i].zone, NULL);
        if (Alive(collider) && Overlaps(zones.bounds(player, NULL), zones.bounds(collider, NULL))) gZones[i].inside = now;
    }
}

/** Replaces the method-table entry (code pointer) that holds `from`; the entry after must hold `next`. */
static BOOL Reroute(void *klass, void *from, void *to, void *next, void *nextTo) {
    uintptr_t *words = klass;
    for (int i = 0; i < 0x200; i++) {
        if (words[i] != (uintptr_t)from) continue;
        if (next && words[i + 2] != (uintptr_t)next) return NO;
        words[i] = (uintptr_t)to;
        if (next) words[i + 2] = (uintptr_t)nextTo;
        return YES;
    }
    return NO;
}

/** The event-zone fix: finds the classes and points their begin and update entries at the functions above. */
static BOOL ResolveZones(void) {
    void *stay = FindClass("Dark.Conductor", "EventTriggerOnStayCollision");
    void *enter = FindClass("Dark.Conductor", "EventTriggerOnEnterCollision");
    void *conductor = FindClass("Adam.Framework.Gameplay.Paradigm.Core", "StateConductor");
    void *zone = FindClass("Adam.Framework.Physication", "ColliderBase");
    void *kernel = FindClass("Dark", "KernelState"), *actor = FindClass("Dark.Variable", "StateActor");
    void *animation = FindClass("Dark.Calculator", "AnimationActor");
    void *object = FindClass("UnityEngine", "GameObject"), *collider = FindClass("UnityEngine", "Collider");
    if (!stay || !enter || !conductor || !zone || !kernel || !actor || !animation || !object || !collider) return NO;
    zones.state_actor = Method(kernel, "get_StateActor", 0);
    zones.actor_collider = Method(animation, "GetCollider", 1);
    zones.component = Method(object, "GetComponentInChildren", 2);
    zones.collider_type = il2cpp.type_get_object(il2cpp.class_get_type(collider));
    zones.bounds = Method(collider, "get_bounds", 0);
    zones.zone_init = Method(zone, "IfNeedInitialize", 0);
    zones.zone_collider = Method(zone, "get_Collider", 0);
    zones.on_stay = Method(stay, "OnStay", 1);
    zones.stay_begin = Method(stay, "OnStateBegin", 0);
    zones.enter_begin = Method(enter, "OnStateBegin", 0);
    zones.stay_update = Method(conductor, "OnStateUpdate", 0);
    if (!zones.state_actor || !zones.actor_collider || !zones.component || !zones.collider_type || !zones.bounds
        || !zones.zone_init || !zones.zone_collider || !zones.on_stay || !zones.stay_begin || !zones.enter_begin || !zones.stay_update
        || !FieldOffset(actor, "_currentUserActor", &zones.user_actor) || !FieldOffset(stay, "_colliderBase", &zones.stay_zone)
        || !FieldOffset(stay, "_hasInvoked", &zones.stay_invoked) || !FieldOffset(enter, "_colliderBase", &zones.enter_zone)) return NO;
    il2cpp.runtime_class_init(stay);
    il2cpp.runtime_class_init(enter);
    // OnStateUpdate is the slot after OnStateBegin (StateConductor slots 11 and 12).
    return Reroute(stay, zones.stay_begin, ZoneStayBegin, zones.stay_update, ZoneStayUpdate)
        && Reroute(enter, zones.enter_begin, ZoneEnterBegin, NULL, NULL);
}

@interface LTDisplayTicker : NSObject
@end
@implementation LTDisplayTicker
- (void)tick:(CADisplayLink *)link {
    static BOOL ready;
    if (!ready) {
        if (!il2cpp.domain_get()) return;
        if (gFps && !Resolve()) return;
        if ((gFps || gSize) && !PatchPresets()) return;  // Config is in the game assembly; it loads with the others.
        if (!ResolveZones()) NSLog(@"[LunarTear] display: story-event zone fix not available in this game build");
        ready = YES;
        if (gFps || gSize) WriteStatus(@"ok");
    }
    if (!gAds && (gAds = roulette_ads_route_agent()))
        NSLog(@"[LunarTear] Special Gift Roulette: %@", gAds > 0 ? @"video ad skipped" : [NSString stringWithFormat:@"not available (%d)", gAds]);
    if (!zones.stay_update && !gFps && gAds) { [link invalidate]; gLink = nil; return; }  // Nothing more to watch.
    if (!gFps) {  // The game's own 30 fps: only the story-event zones.
        if (zones.stay_update) WatchZones();
        return;
    }
    int frame = game.frame_count(NULL);
    if (frame == gLastFrame) return;
    gLastFrame = frame;
    if (game.target_frame_rate(NULL) != gFps) game.set_target_frame_rate(gFps, NULL);
    // A preset applied before the table changed asked for every (gFps / 30)th frame.
    if (game.render_interval(NULL) == gFps / 30) game.set_render_interval(1, NULL);
    float delta = game.unscaled_delta(NULL);
    float physics = fminf(fmaxf(delta, 1 / 240.f), 1 / 30.f);
    if (game.fixed_delta(NULL) != physics) game.set_fixed_delta(physics, NULL);
    StepBattle(delta);
    if (zones.stay_update) WatchZones();
    // Developer check only: launch with LUNAR_DISPLAY_LOG set to log the measured rate every 5 s.
    static double since; static int sinceFrame;
    if (getenv("LUNAR_DISPLAY_LOG") && CACurrentMediaTime() - since >= 5) {
        if (since > 0) NSLog(@"[LunarTear] display: %.1f frames/s, target %d, render interval %d, physics step %.4f",
            (frame - sinceFrame) / (CACurrentMediaTime() - since), game.target_frame_rate(NULL), game.render_interval(NULL), game.fixed_delta(NULL));
        since = CACurrentMediaTime(); sinceFrame = frame;
    }
}
@end

// RenderTargetSize, from the game's metadata: H540 3, H640 4, HD 5 (its own), FullHD 6, WQHD 7, DeviceMax 8.
static int RenderTargetSize(NSString *name) {
    if ([name isEqual:@"540"]) return 3;
    if ([name isEqual:@"640"]) return 4;
    if ([name isEqual:@"1080"]) return 6;
    if ([name isEqual:@"1440"]) return 7;
    if ([name isEqual:@"native"]) return 8;
    return 0;
}

static void *IL2CPPSymbol(const char *name) { return dlsym(RTLD_DEFAULT, name); }
static void RouletteLog(const char *message) { NSLog(@"[LunarTear] %s", message); }

void LTDisplayStart(NSString *toolsRoot) {
    gStatusPath = [toolsRoot stringByAppendingPathComponent:@"display.status"];
    NSString *conf = [NSString stringWithContentsOfFile:[toolsRoot stringByAppendingPathComponent:@"display.conf"] encoding:NSUTF8StringEncoding error:nil];
    NSInteger screen = UIScreen.mainScreen.maximumFramesPerSecond;
    for (NSString *line in [conf componentsSeparatedByString:@"\n"]) {
        NSArray *pair = [line componentsSeparatedByString:@"="];
        if (pair.count != 2) continue;
        NSString *key = [pair[0] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
        NSString *value = [pair[1] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
        if ([key isEqual:@"fps"]) {
            NSInteger rate = [value isEqual:@"max"] ? screen : MIN(value.integerValue, screen);
            gFps = rate > 30 ? (int)MIN(rate, 240) : 0;
        }
        if ([key isEqual:@"resolution"]) gSize = RenderTargetSize(value);
    }
    // The story-event zone fix runs with the game's own settings too; display.status reports chosen settings only.
    BOOL chosen = gFps || gSize;
    if (!chosen) [NSFileManager.defaultManager removeItemAtPath:gStatusPath error:nil];
#define LOAD(name) if (!(*(void **)&il2cpp.name = dlsym(RTLD_DEFAULT, "il2cpp_" #name))) { if (chosen) WriteStatus(@"error=The game's IL2CPP API is missing"); return; }
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(field_static_get_value) LOAD(field_static_set_value) LOAD(runtime_class_init)
    LOAD(class_get_type) LOAD(type_get_object) LOAD(gchandle_new) LOAD(gchandle_free)
#undef LOAD
    if (roulette_ads_init(IL2CPPSymbol, RouletteLog, dlsym(RTLD_DEFAULT, "UnitySendMessage"))) {
        gAds = -1;
        NSLog(@"[LunarTear] Special Gift Roulette: the game's IL2CPP API is missing");
    }
    // IL2CPP starts while Unity finishes launching; the ticker begins once the app is active.
    __block id observer = [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil
        queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            [NSNotificationCenter.defaultCenter removeObserver:observer];
            gLink = [CADisplayLink displayLinkWithTarget:[LTDisplayTicker new] selector:@selector(tick:)];
            float rate = gFps ? (float)screen : 30;  // At the game's own 30, don't ask the screen for more.
            if (@available(iOS 15.0, *)) gLink.preferredFrameRateRange = CAFrameRateRangeMake(30, rate, rate);
            else gLink.preferredFramesPerSecond = (NSInteger)rate;
            [gLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
        }];
}
