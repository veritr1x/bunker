// A name for Subjugation schedules without a season, for Android and iOS (the
// iOS launcher builds this file too).
//
// The Subjugations screen heads the schedule "{0} On Now" with its season's
// name, the text "bighunt.season.name.{0:D3}" for its SeasonAssetId. The first
// five schedules (October 2021 to February 2022) came before seasons and have
// SeasonAssetId 0, which has no text, so the game shows "unknown On Now"; the
// Everything open content keeps the first of them open.
//
// The game's texts (Dark.Localization.LocalizeText, the instance in
// Singleton<LocalizeText>) get "bighunt.season.name.000" with the game's own
// Subjugations title ("ui.Outgame.BigHunt.Title", "Subjugation Battles"). The
// Results dialog names its seasons from the same text. No game code or data
// is changed, and an existing text is never replaced. The format is left
// alone: the game formats it with its own ArtStringBuilder, which takes no
// custom number formats.
#include "big_hunt_season.h"

#include <stdint.h>
#include <string.h>

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static const char kKey[] = "bighunt.season.name.000";
static const char kTitle[] = "ui.Outgame.BigHunt.Title";

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_parent)(void *klass);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void *(*class_get_type)(void *klass);
    void *(*type_get_object)(void *type);
    void *(*class_from_system_type)(void *type);
    Method *(*object_get_virtual_method)(void *object, Method *method);
    void *(*array_new)(void *klass, uintptr_t length);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
    void *(*string_new)(const char *text);
    int32_t (*string_length)(void *string);
    uint16_t *(*string_chars)(void *string);
} il2cpp;

static void (*report)(const char *message);
static int loaded, failed, named;
static Method *m_instance, *m_get_word, *m_set_item;
static size_t f_words;

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

// Whether an IL2CPP string holds text (ASCII).
static int same(void *string, const char *text) {
    size_t length = strlen(text);
    if (!string || il2cpp.string_length(string) != (int32_t)length) return 0;
    const uint16_t *chars = il2cpp.string_chars(string);
    for (size_t i = 0; i < length; i++) if (chars[i] != (uint8_t)text[i]) return 0;
    return 1;
}

// Singleton<LocalizeText>.get_Instance, its GetWord and Dictionary<string, string>.set_Item. 0 when found.
static int lookup(void) {
    void *texts = find_class("Dark.Localization", "LocalizeText"), *words = find_class("Dark.Localization", "WordDictionary");
    void *singleton = find_class("Adam.Framework.Core", "Singleton`1"), *type = find_class("System", "Type");
    void *field = texts ? il2cpp.class_get_field_from_name(texts, "_words") : NULL;
    Method *make = type ? il2cpp.class_get_method_from_name(type, "MakeGenericType", 1) : NULL;
    void *dictionary = words ? il2cpp.class_get_parent(words) : NULL;
    if (!field || !singleton || !make || !dictionary) return -1;
    f_words = il2cpp.field_get_offset(field);
    m_get_word = il2cpp.class_get_method_from_name(texts, "GetWord", 1);
    m_set_item = il2cpp.class_get_method_from_name(dictionary, "set_Item", 2);
    // Singleton<LocalizeText>, made the way C# reflection would: typeof(Singleton<>).MakeGenericType(typeof(LocalizeText)).
    void *definition = il2cpp.type_get_object(il2cpp.class_get_type(singleton));
    void *arguments = il2cpp.array_new(type, 1);
    if (!definition || !arguments) return -1;
    *(void **)((uint8_t *)arguments + 0x20) = il2cpp.type_get_object(il2cpp.class_get_type(texts));  // the array's first element
    Method *made = il2cpp.object_get_virtual_method(definition, make);
    void *closed = made ? call(made, definition, (void *[]){arguments}) : NULL;
    void *klass = closed ? il2cpp.class_from_system_type(closed) : NULL;
    m_instance = klass ? il2cpp.class_get_method_from_name(klass, "get_Instance", 0) : NULL;
    return m_instance && m_get_word && m_set_item ? 0 : -1;
}

void big_hunt_season_name(void) {
    if (!loaded || failed) return;
    if (!m_instance && lookup()) {
        failed = 1;
        return say("Subjugation seasons: unsupported game; early schedules show \"unknown\"");
    }
    // Again each time the top row starts: the game may load its texts again (another language).
    uint8_t *texts = call(m_instance, NULL, NULL);
    void *words = texts ? *(void **)(texts + f_words) : NULL;
    if (!words) return;
    void *key = il2cpp.string_new(kKey);
    void *word = call(m_get_word, texts, (void *[]){key});
    if (!word || !same(word, "unknown")) return;  // already there (or texts not loaded yet)
    void *title = call(m_get_word, texts, (void *[]){il2cpp.string_new(kTitle)});
    if (!title || same(title, "unknown")) return;
    call(m_set_item, words, (void *[]){key, title});
    if (!named) say("Subjugation seasons: early schedules are named Subjugation Battles");
    named = 1;
}

int big_hunt_season_init(void *(*resolve)(const char *name), void (*log)(const char *message)) {
    report = log;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_parent) LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(class_get_type) LOAD(type_get_object)
    LOAD(class_from_system_type) LOAD(object_get_virtual_method) LOAD(array_new) LOAD(runtime_invoke) LOAD(string_new)
    LOAD(string_length) LOAD(string_chars)
#undef LOAD
    loaded = 1;
    return 0;
}
