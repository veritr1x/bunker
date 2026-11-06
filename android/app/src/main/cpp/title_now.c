// Back to the title screen at once after a change in Pod Programs, for Android
// and iOS (the iOS launcher builds this file too).
//
// A change beside the running game asks Lunar Tear to send the game back to its
// title screen (interceptor.RequestTitle), which it does by failing the game's
// next call with the game's own "Returning to title screen." error. That waits
// for the player to do something that calls the server. Lunar Tear also writes
// a marker file then; this sees it (once a second, on Unity's main thread,
// while a header updates) and shows the same dialog straight away through the
// game's own handler: ErrorHandlingInterceptor.MoveTitleError, which the
// client's network error handling calls for that error (HandleNet
// .ShowMoveTitleError with message text 900000 and code 104000, the values
// bunker_title.go sends). It removes the marker once the dialog is shown, and
// Lunar Tear, finding it gone, no longer fails the next call.
//
// During a battle nothing happens: the marker stays until the battle is over,
// so a run is never cut short. For 30 s after the dialog a new marker waits,
// so a second change while it is open does not stack another one. If anything is missing or the game refuses the
// call, the marker stays and the next call does it, as before.
#include "title_now.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

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
    void *(*object_get_class)(void *object);
    void *(*string_new)(const char *text);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
} il2cpp;

static void (*report)(const char *message);
static char marker[1024];
static int state;  // 0 not looked up yet, 1 ready, -1 off
static void *move_title;  // ErrorHandlingInterceptor.MoveTitleError (static field)
static void *battle_counter;  // TurnbaseFrameCounterController._instance: the live battle, as render_pace.c finds it
static size_t battle_context, battle_game;
static double next_look, quiet_until;  // quiet: just shown, so a second change does not stack a second dialog

static void say(const char *message) { if (report) report(message); }

static double seconds(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (double)now.tv_sec + now.tv_nsec / 1e9;
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

static int offset(void *klass, const char *name, size_t *out) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *out = il2cpp.field_get_offset(field);
    return field != NULL;
}

static int look_up(void) {
    void *interceptor = find_class("Adam.Framework.Network.Interceptors", "ErrorHandlingInterceptor");
    void *counter = find_class("Dark.Game.TurnBattle", "TurnbaseFrameCounterController");
    void *component = find_class("Adam.Framework.GameKit.TurnBattle", "BattleComponent");
    void *context = find_class("Adam.Framework.GameKit.TurnBattle", "BattleContext");
    move_title = interceptor ? il2cpp.class_get_field_from_name(interceptor, "MoveTitleError") : NULL;
    battle_counter = counter ? il2cpp.class_get_field_from_name(counter, "_instance") : NULL;
    if (interceptor) il2cpp.runtime_class_init(interceptor);
    if (counter) il2cpp.runtime_class_init(counter);
    return move_title && battle_counter && offset(component, "_battleContext", &battle_context) && offset(context, "_game", &battle_game);
}

static int in_battle(void) {
    uint8_t *counter = NULL;
    il2cpp.field_static_get_value(battle_counter, &counter);
    uint8_t *context = counter ? *(uint8_t **)(counter + battle_context) : NULL;
    return context && *(uint8_t **)(context + battle_game);
}

// The game's own "Returning to title screen." dialog; 1 when it was shown.
static int show_title_dialog(void) {
    void *handler = NULL;
    il2cpp.field_static_get_value(move_title, &handler);
    Method *invoke = handler ? il2cpp.class_get_method_from_name(il2cpp.object_get_class(handler), "Invoke", 5) : NULL;
    if (!invoke) return 0;
    int64_t maintenance = 0;
    void *args[] = {il2cpp.string_new("900000"), il2cpp.string_new("104000"), il2cpp.string_new(""), il2cpp.string_new(""), &maintenance};
    void *exception = NULL;
    il2cpp.runtime_invoke(invoke, handler, args, &exception);
    return exception == NULL;
}

void title_now_tick(void) {
    if (!marker[0] || state < 0) return;
    double now = seconds();
    if (now < next_look || now < quiet_until) return;
    next_look = now + 1;
    if (access(marker, F_OK) != 0) return;
    if (state == 0) {
        state = look_up() ? 1 : -1;
        if (state < 0) { say("Title now: unsupported game; the next call returns to the title screen"); return; }
    }
    if (in_battle()) return;  // after the battle
    if (!show_title_dialog()) {
        state = -1;
        say("Title now: the game refused; the next call returns to the title screen");
        return;
    }
    unlink(marker);
    quiet_until = now + 30;  // a later change meanwhile: the next call returns to the title screen
    say("Title now: back to the title screen");
}

int title_now_init(void *(*resolve)(const char *name), void (*log)(const char *message), const char *path) {
    report = log;
    if (!path || strlen(path) >= sizeof marker) return -1;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(field_static_get_value) LOAD(runtime_class_init)
    LOAD(object_get_class) LOAD(string_new) LOAD(runtime_invoke)
#undef LOAD
    snprintf(marker, sizeof marker, "%s", path);
    return 0;
}
