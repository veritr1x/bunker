// Graphics effects turned off in Pod Programs › Display, for Android and iOS
// (the iOS launcher builds this file too).
//
// The game's performance presets (Dark.Component.PerformanceSetting.Config,
// LevelConfigs: frame rate, RenderTargetSize, then shadow, reflection,
// vignette and bloom flags, 12 bytes each) turn its effects on. Shadows (a
// shadow map), reflections and bloom (full-screen passes) cost GPU time every
// frame, more so at high resolutions and frame rates. Each one chosen off is
// cleared in every preset, and the preset in use is applied again through the
// game's own Config.SetLevel(in LevelConfig), found through
// ContextApi.ActiveContext › Application › PerformanceConfig. Later preset
// changes (the game's own settings) keep them off. If anything is missing the
// game draws its effects as before.
#include "render_effects.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void render_effects_clear(uint8_t *entries, size_t count, int off) {
    for (size_t i = 0; i < count; i++) {
        uint8_t *flags = entries + i * 12 + 8;  // shadow, reflection, vignette, bloom
        if (off & RENDER_EFFECTS_SHADOWS) flags[0] = 0;
        if (off & RENDER_EFFECTS_REFLECTIONS) flags[1] = 0;
        if (off & RENDER_EFFECTS_BLOOM) flags[3] = 0;
    }
}

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    Method *(*class_get_methods)(void *klass, void **iter);
    const char *(*method_get_name)(Method *method);
    uint32_t (*method_get_param_count)(Method *method);
    void *(*method_get_param)(Method *method, uint32_t index);
    char *(*type_get_name)(void *type);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void (*field_static_get_value)(void *field, void *value);
    void (*runtime_class_init)(void *klass);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
} il2cpp;

static void (*report)(const char *message);
static int effects_off, finished;

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

static int offset(void *klass, const char *name, size_t *out) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *out = il2cpp.field_get_offset(field);
    return field != NULL;
}

// Config.SetLevel(in LevelConfig): the overload whose parameter isn't a PerformanceLevel.
static Method *set_level_entry(void *config) {
    void *iter = NULL;
    Method *method;
    while ((method = il2cpp.class_get_methods(config, &iter))) {
        if (strcmp(il2cpp.method_get_name(method), "SetLevel") || il2cpp.method_get_param_count(method) != 1) continue;
        char *type = il2cpp.type_get_name(il2cpp.method_get_param(method, 0));
        int entry = type && strstr(type, "LevelConfig");
        free(type);
        if (entry) return method;
    }
    return NULL;
}

static int done(int result, const char *message) {
    finished = result;
    say(message);
    return result;
}

int render_effects_apply(void) {
    if (finished) return finished;
    if (!effects_off) return finished = 1;
    void *config = find_class("Dark.Component.PerformanceSetting", "Config");
    void *api = find_class("Dark.Kernel", "ContextApi"), *context = find_class("Dark.Kernel", "Context");
    void *application = find_class("Dark.Kernel", "ApplicationContext");
    void *levels = config ? il2cpp.class_get_field_from_name(config, "LevelConfigs") : NULL;
    Method *active = api ? il2cpp.class_get_method_from_name(api, "get_ActiveContext", 0) : NULL;
    Method *set_level = config ? set_level_entry(config) : NULL;
    size_t f_application, f_performance, f_current;
    if (!levels || !active || !set_level || !offset(context, "<Application>k__BackingField", &f_application)
        || !offset(application, "<PerformanceConfig>k__BackingField", &f_performance) || !offset(config, "_currentLevel", &f_current)) {
        // On iOS this can run while the game's assemblies are still loading: wait for them a while (about a minute).
        static int tries;
        return ++tries < 3600 ? 0 : done(-1, "Graphics effects: unsupported game; its effects stay on");
    }
    // The game's context and performance settings exist once its title screen is up.
    uint8_t *ctx = ((void *(*)(void *))active->pointer)(NULL);
    uint8_t *app = ctx ? *(uint8_t **)(ctx + f_application) : NULL;
    uint8_t *performance = app ? *(uint8_t **)(app + f_performance) : NULL;
    if (!performance) return 0;
    il2cpp.runtime_class_init(config);
    uint8_t *array = NULL;
    il2cpp.field_static_get_value(levels, &array);
    if (!array) return 0;
    size_t length = *(size_t *)(array + 0x18);
    render_effects_clear(array + 0x20, length, effects_off);
    // The preset in use, or the start preset (0) before the game has chosen one; power saving (5) has none on.
    int32_t level = *(int32_t *)(performance + f_current);
    if (level == 5) return done(1, "Graphics effects: off in every preset (power saving now)");
    if (level < 0 || (size_t)level >= length) level = 0;
    void *exception = NULL, *args[] = {array + 0x20 + (size_t)level * 12};
    il2cpp.runtime_invoke(set_level, performance, args, &exception);
    if (exception) return done(-2, "Graphics effects: the game refused the preset; they are off from its next change");
    char message[96];
    snprintf(message, sizeof message, "Graphics effects: off (%s%s%s)", effects_off & RENDER_EFFECTS_SHADOWS ? "shadows " : "",
             effects_off & RENDER_EFFECTS_REFLECTIONS ? "reflections " : "", effects_off & RENDER_EFFECTS_BLOOM ? "bloom" : "");
    return done(1, message);
}

int render_effects_init(void *(*resolve)(const char *name), void (*log)(const char *message), int off) {
    report = log;
    effects_off = off;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_methods) LOAD(method_get_name) LOAD(method_get_param_count) LOAD(method_get_param) LOAD(type_get_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(field_static_get_value) LOAD(runtime_class_init) LOAD(runtime_invoke)
#undef LOAD
    return 0;
}
