// How often the game draws above its own 30 fps, for Android and iOS (the iOS
// launcher builds this file too).
//
// At 60 or 120 fps the game draws every frame, still menus and the home field
// included, and the GPU stays busy: an iPad at 120 fps and its own resolution
// reached its "serious" heat state. Unity can keep running every frame while
// drawing only every Nth (OnDemandRendering.renderFrameInterval), so:
//
// - Idle: after RENDER_PACE_IDLE_SECONDS without a touch, outside battles, it
//   draws 30 times a second (the game's own rate). A touch draws every frame
//   again from that frame on. Battles keep the chosen rate.
// - Heat: when the system says the device is hot, it draws 60 a second
//   (serious) or 30 (critical) until it cools down.
//
// The game's own slower rate (power saving, 10 a second) is kept. Unity calls
// EventSystem.Update every frame on every screen (the game's interface is uGUI),
// so that is taken over through its IL2CPP MethodInfo, as bunker_button.c does;
// the original runs first. If anything is missing the game draws as it did.
#include "render_pace.h"

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

int render_pace_decide(RenderPace *pace, int fps, int current, float delta, int touching, int battle, int thermal, int idle, int heat) {
    if (current != pace->last_set) {
        // The game set it: power saving, or a preset from before the frame-rate table was
        // changed, which asked for the game's own 30 a second (every fps / 30th frame).
        pace->game = current > 0 ? current : 1;
        if (fps > 30 && pace->game == fps / 30) pace->game = 1;
    }
    pace->idle = touching || battle ? 0 : pace->idle + delta;
    int target = fps;
    if (idle && pace->idle >= RENDER_PACE_IDLE_SECONDS && target > 30) target = 30;
    if (heat && thermal >= 3 && target > 30) target = 30;
    else if (heat && thermal >= 2 && target > 60) target = 60;
    int interval = (fps + target - 1) / target;
    if (interval < pace->game) interval = pace->game;
    pace->last_set = interval;
    return interval;
}

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void (*field_static_get_value)(void *field, void *value);
    void (*runtime_class_init)(void *klass);
    void *(*thread_attach)(void *domain);
    void *(*get_corlib)(void);
} il2cpp;

static void (*report)(const char *message);
static int chosen_fps, idle_on, heat_on, pacing;
static void (*each_frame)(void);
static volatile int thermal;
static RenderPace pace;
static int last_frame = -1;

static int (*get_interval)(void *method);
static void (*set_interval)(int value, void *method);
static int (*touch_count)(void *method);
static float (*unscaled_delta)(void *method);
static int (*frame_count)(void *method);
static void *battle_counter;  // TurnbaseFrameCounterController._instance: the live battle, as LunarDisplay.m finds it
static size_t battle_context, battle_game;
static Method *update;
static void (*update_original)(void *self, Method *method);

static void say(const char *message) { if (report) report(message); }

void render_pace_set_thermal(int level) { thermal = level; }

static volatile int active;
int render_pace_active(void) { return active; }

static int in_battle(void) {
    uint8_t *counter = NULL;
    il2cpp.field_static_get_value(battle_counter, &counter);
    uint8_t *context = counter ? *(uint8_t **)(counter + battle_context) : NULL;
    return context && *(uint8_t **)(context + battle_game);
}

static void update_hook(void *self, Method *method) {
    update_original(self, method);
    int frame = frame_count(NULL);
    if (frame == last_frame) return;  // one decision a frame, however many event systems
    last_frame = frame;
    if (each_frame) each_frame();
    if (!pacing) return;
    int current = get_interval(NULL);
    int next = render_pace_decide(&pace, chosen_fps, current, unscaled_delta(NULL), touch_count(NULL) > 0, in_battle(), thermal, idle_on, heat_on);
    if (next != current) set_interval(next, NULL);
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

static void *code(void *klass, const char *name, int args) {
    Method *method = klass ? il2cpp.class_get_method_from_name(klass, name, args) : NULL;
    return method ? method->pointer : NULL;
}

static int offset(void *klass, const char *name, size_t *out) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *out = il2cpp.field_get_offset(field);
    return field != NULL;
}

static int look_up(void) {
    void *rendering = find_class("UnityEngine.Rendering", "OnDemandRendering"), *input = find_class("UnityEngine", "Input");
    void *time = find_class("UnityEngine", "Time"), *events = find_class("UnityEngine.EventSystems", "EventSystem");
    void *counter = find_class("Dark.Game.TurnBattle", "TurnbaseFrameCounterController");
    void *component = find_class("Adam.Framework.GameKit.TurnBattle", "BattleComponent");
    void *context = find_class("Adam.Framework.GameKit.TurnBattle", "BattleContext");
    *(void **)&get_interval = code(rendering, "get_renderFrameInterval", 0);
    *(void **)&set_interval = code(rendering, "set_renderFrameInterval", 1);
    *(void **)&touch_count = code(input, "get_touchCount", 0);
    *(void **)&unscaled_delta = code(time, "get_unscaledDeltaTime", 0);
    *(void **)&frame_count = code(time, "get_frameCount", 0);
    update = events ? il2cpp.class_get_method_from_name(events, "Update", 0) : NULL;
    battle_counter = counter ? il2cpp.class_get_field_from_name(counter, "_instance") : NULL;
    if (counter) il2cpp.runtime_class_init(counter);
    return get_interval && set_interval && touch_count && unscaled_delta && frame_count && update && update->pointer && battle_counter
        && offset(component, "_battleContext", &battle_context) && offset(context, "_game", &battle_game);
}

// Classes are looked up only once IL2CPP has finished starting, as in bunker_button.c
// (its core library exists, then its assembly list has not changed for 2 s).
static void *install(void *unused) {
    (void)unused;
    for (int i = 0; !il2cpp.get_corlib(); i++) {
        if (i > 1200) { say("Frame pacing: the game did not start"); return NULL; }
        usleep(100000);
    }
    size_t last = 0;
    for (int i = 0, steady = 0; steady < 20; i++) {
        if (i > 1200) { say("Frame pacing: the game did not start"); return NULL; }
        size_t count = 0;
        if (il2cpp.domain_get()) il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
        steady = count && count == last ? steady + 1 : 0;
        last = count;
        usleep(100000);
    }
    il2cpp.thread_attach(il2cpp.domain_get());
    if (!look_up()) { say("Frame pacing: unsupported game; it draws every frame"); return NULL; }
    update_original = (void (*)(void *, Method *))update->pointer;
    update->pointer = (void *)update_hook;
    active = pacing;
    say("Frame pacing: ready");
    return NULL;
}

int render_pace_init(void *(*resolve)(const char *name), void (*log)(const char *message), int fps, int idle, int heat,
                     void (*frame)(void)) {
    report = log;
    chosen_fps = fps, idle_on = idle, heat_on = heat, each_frame = frame;
    pacing = fps > 30 && (idle || heat);
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(field_static_get_value) LOAD(runtime_class_init)
    LOAD(thread_attach) LOAD(get_corlib)
#undef LOAD
    if (!pacing && !each_frame) return 0;  // nothing to do
    pthread_t thread;
    if (pthread_create(&thread, NULL, install, NULL)) return -1;
    pthread_detach(thread);
    return 0;
}
