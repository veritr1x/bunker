// The Special Gift Roulette without its video ad, for Android and iOS (the iOS
// launcher builds this file too).
//
// The menu's roulette button asks ironSource for a rewarded video
// (IronSource.showRewardedVideo, which passes it on to the platform agent).
// When the video was watched ironSource raised "ad rewarded" with the
// placement and then "ad closed"; RewardRoulettePlayer then asked the server
// for the spin (GachaService.RewardDraw) and played the wheel. No video can be
// shown any more, so showing one now raises "ad rewarded" straight away
// (IronSourceEvents' onRewardedVideoAdRewardedEvent, with the placement the game
// expects) and "ad closed" (onRewardedVideoAdClosedEvent) on a later frame, as
// the SDK did: raised at once, the close ran inside the roulette's own start and
// left the menu's buttons locked. Android's SDK queues events through
// IronSourceEventsDispatcher; iOS's sends them to the IronSourceEvents object
// with UnitySendMessage (the dispatcher doesn't run there), and so does this.
#include "roulette_ads.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    void (*field_static_get_value)(void *field, void *value);
    void (*field_get_value)(void *object, void *field, void *value);
    void (*runtime_class_init)(void *klass);
    void *(*object_new)(void *klass);
    void *(*object_get_class)(void *object);
    void *(*string_new)(const char *text);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
} il2cpp;

static void (*report)(const char *message);
static void (*send_message)(const char *object, const char *method, const char *argument);
static void *events_class, *placement_class, *ironsource_class;
static Method *execute_action;  // IronSourceEventsDispatcher.executeAction(Action): runs it on the next frame.

static void say(const char *message) { if (report) report(message); }

int roulette_ads_init(void *(*resolve)(const char *name), void (*log)(const char *message),
                      void (*unity_send_message)(const char *object, const char *method, const char *argument)) {
    report = log;
    send_message = unity_send_message;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_static_get_value) LOAD(field_get_value) LOAD(runtime_class_init) LOAD(object_new)
    LOAD(object_get_class) LOAD(string_new) LOAD(runtime_invoke)
#undef LOAD
    return 0;
}

static void *find_class(const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), "", name);
        if (klass) return klass;
    }
    return NULL;
}

static int resolve_classes(void) {
    if (events_class) return 1;
    if (!il2cpp.domain_get || !il2cpp.domain_get()) return 0;
    void *events = find_class("IronSourceEvents"), *placement = find_class("IronSourcePlacement"), *ironsource = find_class("IronSource");
    void *dispatcher = find_class("IronSourceEventsDispatcher");
    if (!events || !placement || !ironsource || !dispatcher) return 0;
    if (!(execute_action = il2cpp.class_get_method_from_name(dispatcher, "executeAction", 1))) return 0;
    il2cpp.runtime_class_init(dispatcher);
    il2cpp.runtime_class_init(events);
    il2cpp.runtime_class_init(ironsource);
    placement_class = placement;
    ironsource_class = ironsource;
    events_class = events;
    return 1;
}

/**
 * The delegate behind IronSourceEvents' event name, or NULL if nothing listens.
 * The iOS SDK keeps it in a field named with a leading underscore; Android's in
 * one named like the event.
 */
static void *listeners(const char *name) {
    char hidden[64] = "_";
    strncat(hidden, name, sizeof hidden - 2);
    void *field = il2cpp.class_get_field_from_name(events_class, hidden), *handler = NULL;
    if (!field) field = il2cpp.class_get_field_from_name(events_class, name);
    if (field) il2cpp.field_static_get_value(field, &handler);
    return handler;
}

void roulette_ads_show(void *self, void *method) {
    (void)self, (void)method;
    say("Special Gift Roulette: video requested");
    if (!resolve_classes()) { say("Special Gift Roulette: ironSource classes not found"); return; }
    void *placement = il2cpp.object_new(placement_class);
    Method *init = il2cpp.class_get_method_from_name(placement_class, ".ctor", 3);
    if (!placement || !init) { say("Special Gift Roulette: no IronSourcePlacement"); return; }
    int amount = 1;
    void *exception = NULL, *args[3] = {il2cpp.string_new("DefaultRewardedVideo"), il2cpp.string_new("Gems"), &amount};
    il2cpp.runtime_invoke(init, placement, args, &exception);
    if (exception) { say("Special Gift Roulette: IronSourcePlacement failed"); return; }
    void *rewarded = listeners("onRewardedVideoAdRewardedEvent"), *closed = listeners("onRewardedVideoAdClosedEvent");
    Method *invoke = rewarded ? il2cpp.class_get_method_from_name(il2cpp.object_get_class(rewarded), "Invoke", 1) : NULL;
    if (invoke) {
        void *reward[1] = {placement};
        il2cpp.runtime_invoke(invoke, rewarded, reward, &exception);
        say(exception ? "Special Gift Roulette: rewarded event threw" : "Special Gift Roulette: rewarded");
    } else say("Special Gift Roulette: nothing listens for rewarded");
    if (send_message) {
        send_message("IronSourceEvents", "onRewardedVideoAdClosed", "");
        say("Special Gift Roulette: closed sent");
    } else if (closed) {
        void *close[1] = {closed};
        exception = NULL;
        il2cpp.runtime_invoke(execute_action, NULL, close, &exception);
        say(exception ? "Special Gift Roulette: queueing closed threw" : "Special Gift Roulette: closed queued");
    } else say("Special Gift Roulette: nothing listens for closed");
}

int roulette_ads_route_agent(void) {
    if (!resolve_classes()) return 0;
    void *instance_field = il2cpp.class_get_field_from_name(ironsource_class, "_instance");
    void *agent_field = il2cpp.class_get_field_from_name(ironsource_class, "_platformAgent");
    void *instance = NULL, *agent = NULL;
    if (!instance_field || !agent_field) return -2;
    il2cpp.field_static_get_value(instance_field, &instance);
    if (!instance) return 0;  // Created when the roulette button is first tapped.
    il2cpp.field_get_value(instance, agent_field, &agent);
    if (!agent) return 0;
    void *klass = il2cpp.object_get_class(agent);
    Method *show = il2cpp.class_get_method_from_name(klass, "showRewardedVideo", 0);
    if (!show || !show->pointer) return -3;
    // The agent is called through IronSourceIAgent: point its entry in the class's method table here.
    uintptr_t *words = klass;
    for (int i = 0; i < 0x200; i++) {
        if (words[i] == (uintptr_t)roulette_ads_show) return 1;
        if (words[i] != (uintptr_t)show->pointer) continue;
        words[i] = (uintptr_t)roulette_ads_show;
        return 1;
    }
    return -4;
}
