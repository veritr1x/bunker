#include "controller_actions.h"
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#ifdef __ANDROID__
#include <jni.h>
#endif

typedef struct { void *pointer; } Method;
static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *, size_t *);
    void *(*assembly_get_image)(void *);
    void *(*class_from_name)(void *, const char *, const char *);
    Method *(*class_get_method_from_name)(void *, const char *, int);
    void *(*class_get_field_from_name)(void *, const char *);
    void (*field_get_value)(void *, void *, void *);
    void *(*class_get_type)(void *);
    void *(*type_get_object)(void *);
    void *(*object_get_class)(void *);
    void *(*object_new)(void *);
    void *(*object_unbox)(void *);
    void *(*runtime_invoke)(Method *, void *, void **, void **);
    uintptr_t (*array_length)(void *);
    uint32_t (*array_object_header_size)(void);
} api;
static void (*original_update)(void *, Method *);
static int prepared;
static atomic_uint_fast64_t pending;
static atomic_bool ready;

static uint64_t milliseconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000;
}
void bunker_pad_request(int action) {
    if (!action || atomic_load(&ready))
        atomic_store(&pending, action ? (milliseconds() << 2) | (unsigned)action : 0);
}
#ifdef __ANDROID__
JNIEXPORT void JNICALL Java_org_veritr1x_bunker_PadInput_gameAction(JNIEnv *env, jclass cls, jint action) {
    (void)env; (void)cls;
    bunker_pad_request(action);
}
#endif
static void *klass(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = api.domain_get_assemblies(api.domain_get(), &count);
    for (size_t i = 0; i < count; ++i) {
        void *k = api.class_from_name(api.assembly_get_image(assemblies[i]), ns, name);
        if (k) return k;
    }
    return NULL;
}
static void *as_type(void *k) { return k ? api.type_get_object(api.class_get_type(k)) : NULL; }
static int invoke(void *k, void *obj, const char *name, int count, void **args, void **out) {
    Method *method = k ? api.class_get_method_from_name(k, name, count) : NULL;
    if (!method) return 0;
    void *error = NULL, *result = api.runtime_invoke(method, obj, args, &error);
    if (out) *out = error ? NULL : result;
    return !error;
}
static void *get(void *obj, const char *name, int count, void **args) {
    void *result = NULL;
    if (obj) invoke(api.object_get_class(obj), obj, name, count, args, &result);
    return result;
}
static void *field(void *obj, const char *name) {
    void *f = obj ? api.class_get_field_from_name(api.object_get_class(obj), name) : NULL, *value = NULL;
    if (f) api.field_get_value(obj, f, &value);
    return value;
}
static int unbox(void *box, void *out, size_t size) {
    if (!box) return 0;
    memcpy(out, api.object_unbox(box), size);
    return 1;
}
static int enabled(void *obj, const char *name) {
    uint8_t yes = 0;
    return unbox(get(obj, name, 0, NULL), &yes, sizeof yes) && yes;
}
static void *instances(const char *ns, const char *name) {
    void *result = NULL, *type = as_type(klass(ns, name));
    if (type) invoke(klass("UnityEngine","Object"), NULL, "FindObjectsOfType", 1, (void *[]){type}, &result);
    return result;
}
static void *item(void *array, uintptr_t i) {
    return ((void **)((uint8_t *)array + api.array_object_header_size()))[i];
}
static void go_back(void) {
    const char *names[] = {"OutGameAndroidBackKey", "InGameAndroidBackKey"};
    for (size_t i = 0; i < 2; i++) {
        void *found = instances("Dark.View.UserInterface", names[i]);
        for (uintptr_t j = 0; found && j < api.array_length(found); ++j) {
            void *obj = item(found, j);
            if (enabled(obj,"get_isActiveAndEnabled") &&
                invoke(api.object_get_class(obj), obj, "OnBackKeyClicked", 0, NULL, NULL)) return;
        }
    }
}
// Check the frontmost UGUI raycast hit before touching a Skip button behind a dialog.
static int hit(void *button, void *system, void *pointer, void *results, float pos[2]) {
    if (!enabled(button, "get_isActiveAndEnabled")) return 0;
    void *transform = get(button, "get_transform", 0, NULL);
    float rect[4], world[3];
    if (!unbox(get(transform, "get_rect", 0, NULL), rect, sizeof rect)) return 0;
    float center[] = {rect[0] + .5f * rect[2], rect[1] + .5f * rect[3], 0};
    if (!unbox(get(transform, "TransformPoint", 1, (void *[]){center}), world, sizeof world)) return 0;
    void *casterType = as_type(klass("UnityEngine.UI","GraphicRaycaster"));
    void *caster = casterType ? get(button, "GetComponentInParent", 1, (void *[]){casterType}) : NULL;
    void *box = NULL;
    if (!caster || !invoke(klass("UnityEngine","RectTransformUtility"), NULL, "WorldToScreenPoint", 2,
                            (void *[]){get(caster, "get_eventCamera", 0, NULL), world}, &box) ||
        !unbox(box, pos, 2 * sizeof(float))) return 0;
    if (!invoke(api.object_get_class(pointer), pointer, "set_position", 1, (void *[]){pos}, NULL) ||
        !invoke(api.object_get_class(system), system, "RaycastAll", 2, (void *[]){pointer, results}, NULL)) return 0;
    int count = 0, first = 0;
    void *front = NULL;
    if (!unbox(get(results, "get_Count", 0, NULL), &count, sizeof count) || !count ||
        !unbox(get(results, "get_Item", 1, (void *[]){&first}), &front, sizeof front)) return 0;
    uint8_t descendant = 0;
    return unbox(get(get(front, "get_transform", 0, NULL), "IsChildOf", 1, (void *[]){transform}), &descendant, 1) && descendant;
}
static void skip(void *system) {
    static const struct { const char *ns, *owner, *field; } bindings[] = {
        {"Dark.View.MoviePlay","MoviePlayer","_closeButtonForCage"},
        {"Dark.View.MoviePlay","MoviePlayer","_closeButton"},
        {"Dark.View.HeadUpDisplay.Menu","ReplaySkipButtonAction","_skipButton"},
        {"Dark.View.HeadUpDisplay.MomPromotion","MomPromotionContentPlayer","_skipButton"},
        {"Dark.View.HeadUpDisplay.LoginBonus","LoginBonusPresenter","_skipButton"},
        {"Dark.View.HeadUpDisplay.Omikuji","OmikujiAction","_skipButton"},
        {"Dark.View.UserInterface","GachaProductionScreenView","_skipButton"},
        {"Dark.View.HeadUpDisplay.StorySkip","StorySkipAction","_storySkipToggle"},
        {"Dark.View.HeadUpDisplay.StorySkip","StorySkipAction","_battleSkipToggle"},
        {"Dark.View.MoviePlay","MoviePlayer","_tapScreenButton"},
        {"Dark.View.Movie","PreTitleMovie","tapScreenButton"},
        {"Dark.View.Title","SplashScreen","_splashNoteTap"},
        {"Dark.View.Title","SplashScreen","_splashTap"},
        {"Dark.View.Title","SplashScreen","_splashSoundTextTap"}
    };
    void *cache = field(get(system,"get_currentInputModule",0,NULL), "m_RaycastResultCache");
    void *pk = klass("UnityEngine.EventSystems","PointerEventData");
    if (!cache || !pk) return;
    void *pointer = api.object_new(pk), *rk = api.object_get_class(cache), *results = api.object_new(rk);
    if (!pointer || !results || !invoke(pk, pointer, ".ctor", 1, (void *[]){system}, NULL) ||
        !invoke(rk, results, ".ctor", 0, NULL, NULL)) return;
    for (size_t i = 0; i < sizeof bindings / sizeof *bindings; i++) {
        void *found = instances(bindings[i].ns, bindings[i].owner);
        for (uintptr_t j = 0; found && j < api.array_length(found); ++j) {
            void *owner = item(found, j), *button = field(owner, bindings[i].field);
            float pos[2];
            if (!button || !hit(button, system, pointer, results, pos)) continue;
            if (!strcmp(bindings[i].owner,"SplashScreen")) {
                if (invoke(api.object_get_class(owner), owner, "OnTap", 1, (void *[]){pos}, NULL)) return;
            } else if (enabled(button,"get_IsEnable")) {
                if (invoke(api.object_get_class(button), button, "OnTap", 1, (void *[]){pos}, NULL)) return;
            } else if (enabled(button,"IsInteractable") &&
                       invoke(api.object_get_class(button), button, "OnPointerClick", 1, (void *[]){pointer}, NULL)) return;
        }
    }
}
static void update(void *self, Method *method) {
    original_update(self, method);
    uint64_t command = atomic_exchange(&pending, 0);
    if (!command || milliseconds() - (command >> 2) > 500) return;
    if ((command & 3) == BUNKER_PAD_SKIP) skip(self);
    if ((command & 3) == BUNKER_PAD_BACK) go_back();
}
void bunker_pad_prepare(void *(*resolve)(const char *)) {
#define LOAD(name) if (!(*(void **)&api.name = resolve("il2cpp_" #name))) return;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name)
    LOAD(class_get_method_from_name) LOAD(class_get_field_from_name) LOAD(field_get_value)
    LOAD(class_get_type) LOAD(type_get_object) LOAD(object_get_class) LOAD(object_new)
    LOAD(object_unbox) LOAD(runtime_invoke) LOAD(array_length) LOAD(array_object_header_size)
#undef LOAD
    prepared = 1;
}
void bunker_pad_install(void) {
    if (!prepared) return;
    void *k = klass("UnityEngine.EventSystems","EventSystem");
    Method *frame = k ? api.class_get_method_from_name(k,"Update",0) : NULL;
    if (!frame || !frame->pointer) return;
    original_update = (void (*)(void *, Method *))frame->pointer;
    frame->pointer = (void *)update;
    atomic_store(&ready, 1);
}
