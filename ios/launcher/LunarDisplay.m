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
//   High) use the chosen RenderTargetSize.
// - Field movement: characters move once per rendered frame while physics
//   keeps a 1/30 s step, so the physics step follows the frame time.
// - Battles advance one 30 Hz step per frame; BattleGame's simulation rate is
//   scaled by the part of a step each frame lasted.
//
// The choices are read from tools/display.conf (android_display.py writes it).
// The outcome goes to tools/display.status, which Pod Programs shows.
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#include <dlfcn.h>

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
} il2cpp;

static int gFps, gSize;  // 0: the game's own.
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
static int gLastFrame = -1;
static void *gLastBattle;
static float gBattleRate, gWrittenRate;

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

/** Scales the live battle's simulation rate; the game's own rate (1x or its fast mode) is kept as the base. */
static void ScaleBattle(float step) {
    uint8_t *counter = NULL;
    il2cpp.field_static_get_value(game.battle_counter, &counter);
    uint8_t *context = counter ? *(uint8_t **)(counter + game.battle_context) : NULL;
    uint8_t *battle = context ? *(uint8_t **)(context + game.battle_game) : NULL;
    if (!battle) return;
    float *rate = (float *)(battle + game.simulation_rate);
    if (battle != gLastBattle || *rate != gWrittenRate) { gLastBattle = battle; gBattleRate = *rate; }
    gWrittenRate = gBattleRate * step;
    *rate = gWrittenRate;
}

@interface LTDisplayTicker : NSObject
@end
@implementation LTDisplayTicker
- (void)tick:(CADisplayLink *)link {
    static BOOL ready;
    if (!ready) {
        if (!il2cpp.domain_get()) return;
        if (gFps && !Resolve()) return;
        if (!PatchPresets()) return;  // Config is in the game assembly; it loads with the others.
        ready = YES;
        WriteStatus(@"ok");
        if (!gFps) { [link invalidate]; gLink = nil; return; }  // Resolution only: done.
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
    ScaleBattle(fminf(30 * delta, 1));
    // Developer check only: launch with LUNAR_DISPLAY_LOG set to log the measured rate every 5 s.
    static double since; static int sinceFrame;
    if (getenv("LUNAR_DISPLAY_LOG") && CACurrentMediaTime() - since >= 5) {
        if (since > 0) NSLog(@"[LunarTear] display: %.1f frames/s, target %d, render interval %d, physics step %.4f",
            (frame - sinceFrame) / (CACurrentMediaTime() - since), game.target_frame_rate(NULL), game.render_interval(NULL), game.fixed_delta(NULL));
        since = CACurrentMediaTime(); sinceFrame = frame;
    }
}
@end

static int RenderTargetSize(NSString *name) {
    if ([name isEqual:@"1080"]) return 6;
    if ([name isEqual:@"1440"]) return 7;
    if ([name isEqual:@"native"]) return 8;
    return 0;
}

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
    if (!gFps && !gSize) {
        [NSFileManager.defaultManager removeItemAtPath:gStatusPath error:nil];
        return;
    }
#define LOAD(name) if (!(*(void **)&il2cpp.name = dlsym(RTLD_DEFAULT, "il2cpp_" #name))) { WriteStatus(@"error=The game's IL2CPP API is missing"); return; }
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(field_static_get_value) LOAD(field_static_set_value) LOAD(runtime_class_init)
#undef LOAD
    // IL2CPP starts while Unity finishes launching; the ticker begins once the app is active.
    __block id observer = [NSNotificationCenter.defaultCenter addObserverForName:UIApplicationDidBecomeActiveNotification object:nil
        queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            [NSNotificationCenter.defaultCenter removeObserver:observer];
            gLink = [CADisplayLink displayLinkWithTarget:[LTDisplayTicker new] selector:@selector(tick:)];
            if (@available(iOS 15.0, *)) gLink.preferredFrameRateRange = CAFrameRateRangeMake(30, (float)screen, (float)screen);
            else gLink.preferredFramesPerSecond = screen;
            [gLink addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
        }];
}
