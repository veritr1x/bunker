// Flying Mama (Exploration's second minigame) at the game's own pace above 30
// fps, for Android and iOS (the iOS launcher builds this file too).
//
// FlyingMomPresenter.Update runs the whole minigame once a frame, and nearly
// all of it counts frames: the stage scrolls by its speed each frame, Mama
// falls and jumps by a frame counter, birds and sprites animate per frame. Only
// the clock, the damage timer and the Emil-head timer use Time.deltaTime. At 60
// fps the stage and Mama ran twice as fast against the same 99 s clock (on the
// emulator Mama sank onto the walls with taps that kept her up at 30).
//
// Update now runs as 30 steps a second, as at the game's own 30 fps: on a frame
// once 1/30 s has built up, and on a frame where a touch began (a tap counts
// only on its "began" frame, which an in-between frame would lose; the next
// step waits longer instead). During a step Time.deltaTime gives the game time
// since the last step, so the clocks keep real time. Time.deltaTime is an
// internal call whose wrapper caches the engine's function in a pointer; that
// pointer, and Update's MethodInfo code pointer, are what change. Nothing else
// sees a different deltaTime.
#include "flying_mom.h"

#include <stddef.h>
#include <string.h>

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

// UnityEngine.Touch, as Input.GetTouch returns it.
typedef struct {
    int finger;
    float position[2], raw_position[2], position_delta[2], time_delta;
    int tap_count, phase, type;
    float pressure, maximum_pressure, radius, radius_variance, altitude, azimuth;
} Touch;
_Static_assert(sizeof(Touch) == 0x44, "UnityEngine.Touch is 0x44 bytes");
enum { TouchBegan = 0 };

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
} il2cpp;

static void (*report)(const char *message);
static int routed;
static void (*update)(void *self, void *method);
static float (*engine_delta)(void);  // UnityEngine.Time::get_deltaTime itself
static float (*unscaled_delta)(void *method);
static int (*touch_count)(void *method);
static Touch (*get_touch)(int index, void *method);
static FlyingMomClock clock;
static void *game;
static int in_step;

int flying_mom_clock_tick(FlyingMomClock *c, float unscaled, float delta, int touch_began) {
    c->time += delta;
    if (!c->started) {
        c->started = 1;
        c->due = 0;
    } else {
        c->due += 30.0 * unscaled;
        // A little under 1 still counts, so a display a hair over 60 Hz steps every other frame.
        if (c->due < 0.999 && !touch_began) return 0;
        c->due -= 1;
        if (c->due < -1) c->due = -1;  // taps in a row: the steps after them wait at most a step longer
        if (c->due >= 1) c->due = 0;   // at most one step per frame; a long frame doesn't build a backlog
    }
    c->step_time = c->time;
    c->time = 0;
    return 1;
}

uintptr_t flying_mom_icall_slot(const uint32_t *code, uintptr_t address) {
    for (int i = 0; i < 6; i++) {
        uint32_t op = code[i];
        if ((op & 0x9f000000u) != 0x90000000u) continue;  // adrp
        int64_t pages = (int64_t)((op >> 5) & 0x7ffff) << 2 | ((op >> 29) & 3);
        pages = (pages ^ 0x100000) - 0x100000;  // 21-bit signed
        uint32_t load = code[i + 1];
        // ldr x0, [xN, #offset]: the cached code pointer.
        if ((load & 0xffc0001fu) != 0xf9400000u || ((load >> 5) & 31) != (op & 31)) return 0;
        uintptr_t page = ((address + 4 * (uintptr_t)i) & ~(uintptr_t)0xfff) + (uintptr_t)(pages * 4096);
        return page + ((load >> 10) & 0xfff) * 8;
    }
    return 0;
}

static int touch_began(void) {
    int count = touch_count(NULL);
    for (int i = 0; i < count; i++)
        if (get_touch(i, NULL).phase == TouchBegan) return 1;
    return 0;
}

/** Time.deltaTime's engine function, as the game now calls it. */
static float delta_time(void) {
    return in_step ? clock.step_time : engine_delta();
}

/** FlyingMomPresenter.Update: the minigame, run as 30 Hz steps. */
static void step_update(void *self, void *method) {
    if (self != game) {  // a new game
        game = self;
        memset(&clock, 0, sizeof clock);
    }
    if (!flying_mom_clock_tick(&clock, unscaled_delta(NULL), engine_delta(), touch_began())) return;
    in_step = 1;
    update(self, method);
    in_step = 0;
}

int flying_mom_init(void *(*resolve)(const char *name), void (*log)(const char *message)) {
    report = log;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
#undef LOAD
    return 0;
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

static Method *find_method(void *klass, const char *name, int args) {
    Method *method = klass ? il2cpp.class_get_method_from_name(klass, name, args) : NULL;
    return method && method->pointer ? method : NULL;
}

int flying_mom_route(void) {
    if (routed) return routed;
    if (!il2cpp.domain_get || !il2cpp.domain_get()) return 0;
    void *time = find_class("UnityEngine", "Time"), *input = find_class("UnityEngine", "Input");
    Method *presenter_update = find_method(find_class("Subsystem.MiniGame.FlyingMom", "FlyingMomPresenter"), "Update", 0);
    Method *delta = find_method(time, "get_deltaTime", 0), *unscaled = find_method(time, "get_unscaledDeltaTime", 0);
    Method *count = find_method(input, "get_touchCount", 0), *touch = find_method(input, "GetTouch", 1);
    if (!presenter_update || !delta || !unscaled || !count || !touch) return routed = -2;
    ((float (*)(void *))delta->pointer)(NULL);  // the wrapper looks up and caches the engine function
    void **slot = (void **)flying_mom_icall_slot(delta->pointer, (uintptr_t)delta->pointer);
    if (!slot || !*slot) return routed = -3;
    engine_delta = (float (*)(void))*slot;
    unscaled_delta = (float (*)(void *))unscaled->pointer;
    touch_count = (int (*)(void *))count->pointer;
    get_touch = (Touch (*)(int, void *))touch->pointer;
    update = (void (*)(void *, void *))presenter_update->pointer;
    *slot = (void *)delta_time;
    presenter_update->pointer = (void *)step_update;
    if (report) report("Flying Mama: game logic at 30 steps a second");
    return routed = 1;
}
