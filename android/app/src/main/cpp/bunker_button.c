// The in-game Bunker button, for Android and iOS (the iOS launcher builds this
// file too).
//
// The game's top row (Dark.View.HeadUpDisplay.Header.HeaderButtons: Notices,
// Gift Box, Shop, Missions, Mission Pass, Friends, Help) gets a first button,
// "Bunker", that opens the Bunker launcher. It is a copy of the Notices button
// (always shown; its label is the style to match) with its badge hidden, its
// label set, its icon replaced by the Bunker emblem (bunker_icon.h) and its tap
// sent to the platform's open_bunker.
//
// Unity calls MonoBehaviour messages (Start, Update) through their IL2CPP
// MethodInfo, so HeaderButtons.Start and Update are taken over by replacing
// MethodInfo.methodPointer: the original runs first. No game code is changed
// (iOS cannot write code pages). Everything is looked up by name once IL2CPP
// has finished starting; if anything is missing the game runs as it was.
//
// The button locks with the row: it shows the same enabled state as Notices
// and opens the launcher only while the row has its tap events
// (bunker_tap_allowed). When the row is wider than its place on the screen
// (a 4:3 iPad, or the Mission Pass button shown), the gap between all the
// buttons narrows until it fits (bunker_row_gap).
//
// API notes from the 3.7.1 game (2019.4, IL2CPP stripped): non-generic
// Object.Instantiate(Object, Transform) and Sprite.Create are stripped, so the
// copy is Instantiate(Object) + Transform.SetParent, and the emblem is a
// RawImage with a Texture2D over the hidden icon image.
#include "bunker_button.h"
#include "arena_season.h"
#include "big_hunt_season.h"
#include "bunker_button_layout.h"
#include "bunker_icon.h"
#include "title_now.h"
#ifdef __ANDROID__
#include "game_region.h"
#endif

#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
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
    void *(*method_get_param)(Method *method, uint32_t index);
    char *(*type_get_name)(void *type);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void *(*class_get_type)(void *klass);
    void *(*type_get_object)(void *type);
    void *(*runtime_invoke)(Method *method, void *object, void **args, void **exception);
    void *(*object_new)(void *klass);
    void *(*string_new)(const char *text);
    void *(*array_new)(void *klass, uintptr_t length);
    int32_t (*string_length)(void *string);
    uint16_t *(*string_chars)(void *string);
    void *(*thread_attach)(void *domain);
    void *(*get_corlib)(void);
} il2cpp;

static void (*report)(const char *message);
static void (*open_bunker)(void);

static void *k_object, *k_component, *k_gameobject, *k_transform, *k_rect, *k_behaviour, *k_header, *k_button,
    *k_text, *k_image, *k_rawimage, *k_texture, *k_action, *k_byte, *k_layout, *k_counter, *k_vector3;
static Method *m_start, *m_update, *m_on_tap_help, *m_name, *m_set_name, *m_component_go, *m_component_tr, *m_go_tr,
    *m_parent, *m_child_count, *m_child, *m_set_parent, *m_sibling, *m_instantiate, *m_set_active, *m_active_self,
    *m_components, *m_get_component, *m_add_component, *m_go_ctor, *m_set_enabled, *m_set_text, *m_tex_ctor,
    *m_load_image, *m_set_texture, *m_anchor_min, *m_anchor_max, *m_offset_min, *m_offset_max, *m_register_tap,
    *m_is_enable, *m_set_is_enable, *m_rect, *m_get_spacing, *m_set_spacing, *m_root, *m_corners, *m_in_hierarchy;
static size_t f_notice, f_has_tap, f_method_ptr, f_target, f_method;
// The game's own buttons in the row. Each screen shows some of them
// (HeaderButtons.SetupHeaderButton sets each one's GameObject active); the
// copy shows while any does, and hides with them (the art viewer hides all).
static const char *const kRowButtons[] = {"_noticeButton", "_giftButton", "_shopButton", "_missionButton",
                                          "_friendButton", "_helpButton", "_missionPassButton"};
#define ROW_BUTTONS (sizeof kRowButtons / sizeof kRowButtons[0])
static size_t f_row[ROW_BUTTONS];
static void (*start_original)(void *self, Method *method);
static void (*update_original)(void *self, Method *method);

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

// A method by name, parameter count and (when given) its first parameter's type name.
static Method *find_method(void *klass, const char *name, int args, const char *first) {
    void *iter = NULL;
    Method *method;
    while (klass && (method = il2cpp.class_get_methods(klass, &iter))) {
        if (strcmp(il2cpp.method_get_name(method), name) || (int)il2cpp.method_get_param_count(method) != args) continue;
        if (!first) return method;
        char *type = il2cpp.type_get_name(il2cpp.method_get_param(method, 0));
        int same = type && !strcmp(type, first);
        free(type);
        if (same) return method;
    }
    return NULL;
}

static int find_offset(void *klass, const char *name, size_t *offset) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *offset = il2cpp.field_get_offset(field);
    return field ? 0 : -1;
}

static int failed;  // an exception from the game: stop changing the row

static void *call(Method *method, void *object, void **args) {
    void *exception = NULL;
    void *result = il2cpp.runtime_invoke(method, object, args, &exception);
    if (exception && !failed) {
        char message[128];
        snprintf(message, sizeof message, "Bunker button: the game refused %s; the row is left as it is", il2cpp.method_get_name(method));
        say(message);
        failed = 1;
    }
    return exception ? NULL : result;
}

#define FIELD(object, offset, type) (*(type *)((uint8_t *)(object) + (offset)))
static size_t array_length(void *array) { return array ? FIELD(array, 24, size_t) : 0; }
static void *array_item(void *array, size_t i) { return ((void **)((uint8_t *)array + 32))[i]; }
static int unboxed_bool(void *boxed) { return boxed ? FIELD(boxed, 16, uint8_t) : 0; }
static void *type_of(void *klass) { return il2cpp.type_get_object(il2cpp.class_get_type(klass)); }

static int named(void *object, const char *want) {
    void *name = object ? call(m_name, object, NULL) : NULL;
    if (!name) return 0;
    size_t length = (size_t)il2cpp.string_length(name), i = 0;
    uint16_t *chars = il2cpp.string_chars(name);
    if (length != strlen(want)) return 0;
    for (; i < length && chars[i] == (uint8_t)want[i]; i++) {}
    return i == length;
}

// Every component of a type under a GameObject, inactive ones included.
static void *components(void *gameobject, void *klass) {
    uint8_t yes = 1, no = 0;
    return call(m_components, gameobject, (void *[]){type_of(klass), &yes, &yes, &yes, &no, NULL});
}

static void *child_named(void *transform, const char *name) {
    void *count = call(m_child_count, transform, NULL);
    int n = count ? FIELD(count, 16, int) : 0;
    for (int i = 0; i < n; i++) {
        void *child = call(m_child, transform, (void *[]){&i});
        if (named(child, name)) return child;
    }
    return NULL;
}

static void tap(void *self, Method *method) {
    (void)method;
    void *notice = FIELD(self, f_notice, void *);
    int enabled = notice && unboxed_bool(call(m_is_enable, notice, NULL));
    if (bunker_tap_allowed(enabled, FIELD(self, f_has_tap, uint8_t)) && open_bunker) open_bunker();
}

// The Bunker emblem over the copy's hidden icon image, placed as the game's
// Notices icon is drawn (measured on a device: a little larger than its image
// and lower, its tip behind the label).
static void put_emblem(void *icon) {
    uint8_t no = 0;
    call(m_set_enabled, icon, (void *[]){&no});
    void *gameobject = il2cpp.object_new(k_gameobject);
    call(m_go_ctor, gameobject, (void *[]){il2cpp.string_new("bunker_icon")});
    void *raw = call(m_add_component, gameobject, (void *[]){type_of(k_rawimage)});
    void *rect = call(m_go_tr, gameobject, NULL);
    if (!raw || !rect) return;
    call(m_set_parent, rect, (void *[]){call(m_component_tr, icon, NULL), &no});
    float low[2] = {-0.003f, -0.027f}, high[2] = {1.003f, 0.977f}, zero[2] = {0, 0};
    call(m_anchor_min, rect, (void *[]){low});
    call(m_anchor_max, rect, (void *[]){high});
    call(m_offset_min, rect, (void *[]){zero});
    call(m_offset_max, rect, (void *[]){zero});
    void *texture = il2cpp.object_new(k_texture);
    int side = 2;
    call(m_tex_ctor, texture, (void *[]){&side, &side});
    void *bytes = il2cpp.array_new(k_byte, kBunkerIconPngSize);
    memcpy((uint8_t *)bytes + 32, kBunkerIconPng, kBunkerIconPngSize);
    if (unboxed_bool(call(m_load_image, NULL, (void *[]){texture, bytes, &no}))) call(m_set_texture, raw, (void *[]){texture});
}

static void add_button(void *self) {
    void *notice = FIELD(self, f_notice, void *);
    void *row = notice ? call(m_parent, call(m_component_tr, notice, NULL), NULL) : NULL;
    if (!row || child_named(row, "bunker_button")) return;
    uint8_t yes = 1, no = 0;
    void *copy = call(m_instantiate, NULL, (void *[]){call(m_component_go, notice, NULL)});
    void *transform = copy ? call(m_go_tr, copy, NULL) : NULL;
    if (!transform) return;
    call(m_set_parent, transform, (void *[]){row, &no});
    int first = 0;
    call(m_sibling, transform, (void *[]){&first});
    call(m_set_name, copy, (void *[]){il2cpp.string_new("bunker_button")});
    call(m_set_active, copy, (void *[]){&yes});
    void *all = components(copy, k_component);
    for (size_t i = 0; i < array_length(all); i++) {
        void *gameobject = call(m_component_go, array_item(all, i), NULL);
        if (named(gameobject, "badge_middle")) { call(m_set_active, gameobject, (void *[]){&no}); break; }
    }
    void *texts = components(copy, k_text);
    const char *title = "Bunker";
#ifdef __ANDROID__
    if (bunker_game_japanese) title = "バンカー";
#endif
    for (size_t i = 0; i < array_length(texts); i++)
        if (named(call(m_component_go, array_item(texts, i), NULL), "button_title"))
            call(m_set_text, array_item(texts, i), (void *[]){il2cpp.string_new(title)});
    void *images = components(copy, k_image);
    for (size_t i = 0; i < array_length(images); i++)
        if (named(call(m_component_go, array_item(images, i), NULL), "image")) { put_emblem(array_item(images, i)); break; }
    void *button = call(m_get_component, copy, (void *[]){type_of(k_button)});
    void *action = button ? il2cpp.object_new(k_action) : NULL;
    if (!action) return;
    FIELD(action, f_method_ptr, void *) = (void *)tap;
    FIELD(action, f_target, void *) = self;
    FIELD(action, f_method, void *) = m_on_tap_help;  // any of HeaderButtons' void() methods: the delegate calls method_ptr
    call(m_register_tap, button, (void *[]){action});
}

static void start_hook(void *self, Method *method) {
    start_original(self, method);
    big_hunt_season_name();  // the top row is up before any Subjugations screen
    arena_season_dates();    // and before the Arena
    if (!failed) add_button(self);
}

// Per row: the copy's button, and the row's own gap (to narrow from).
typedef struct { void *self, *notice, *button, *copy, *row, *layout, *scope, *own[ROW_BUTTONS]; float gap; int enabled, shown, frames; } Row;
// The game has two headers, in-game and out-game, and Unity updates both every
// frame. Each keeps its own Row: with one shared Row, every frame looked the
// row up again and searched the whole interface for the counters, which held a
// 120 fps iPad near 80 on busy screens such as Quests and Summons.
static Row rows[2];
// A header is known by its address and its Notices button: a new header made
// where a destroyed one was has a new button, so it is set up again instead of
// using the destroyed one's objects.
static Row *row_for(void *self) {
    static size_t last;
    void *notice = FIELD(self, f_notice, void *);
    for (size_t i = 0; i < 2; i++)
        if (rows[i].self == self) {
            if (rows[i].notice != notice) rows[i].self = NULL;  // set up again below
            return &rows[last = i];
        }
    for (size_t i = 0; i < 2; i++)
        if (!rows[i].self) return &rows[last = i];
    return &rows[last = !last];  // a header that went away: reuse the other slot
}

// A RectTransform's corners on screen: left, bottom, right, top. 0 on success.
static int corners(void *transform, float out[4]) {
    void *array = transform ? il2cpp.array_new(k_vector3, 4) : NULL;
    if (!array) return -1;
    call(m_corners, transform, (void *[]){array});  // returns nothing; fills the array
    if (failed) return -1;
    float *v = (float *)((uint8_t *)array + 32);  // 4 x (x, y, z): bottom-left, top-left, top-right, bottom-right
    out[0] = v[0]; out[1] = v[1]; out[2] = v[6]; out[3] = v[4];
    return 0;
}

static float rect_width(void *transform) {
    void *rect = transform ? call(m_rect, transform, NULL) : NULL;
    return rect ? ((float *)((uint8_t *)rect + 16))[2] : 0;  // Rect: x, y, width, height
}

static void update_hook(void *self, Method *method) {
    update_original(self, method);
    title_now_tick();  // a change in Pod Programs: back to the title screen now
    if (failed) return;
    Row *seen = row_for(self);
    if (seen->self != self) {
        void *notice = FIELD(self, f_notice, void *);
        void *row = notice ? call(m_parent, call(m_component_tr, notice, NULL), NULL) : NULL;
        void *copy = row ? child_named(row, "bunker_button") : NULL;
        if (!copy) return;  // Start has not added it (yet)
        seen->self = self;
        seen->notice = notice;
        seen->row = row;
        seen->copy = call(m_component_go, copy, NULL);
        seen->button = call(m_get_component, seen->copy, (void *[]){type_of(k_button)});
        for (size_t i = 0; i < ROW_BUTTONS; i++) {
            void *own = FIELD(self, f_row[i], void *);
            seen->own[i] = own ? call(m_component_go, own, NULL) : NULL;
        }
        seen->shown = -1;
        seen->layout = call(m_get_component, call(m_component_go, row, NULL), (void *[]){type_of(k_layout)});
        void *gap = seen->layout ? call(m_get_spacing, seen->layout, NULL) : NULL;
        seen->gap = gap ? FIELD(gap, 16, float) : 0;
        seen->enabled = -1;
        seen->frames = 0;
        // Where the counters are looked for: the top-level object holding the
        // row (the heads-up display, with both headers' counters), not the
        // whole interface under the root (1.3 ms a search against 0.2).
        void *scope = row, *root = call(m_root, row, NULL);
        for (void *up; scope && (up = call(m_parent, scope, NULL)) && up != root;) scope = up;
        seen->scope = scope ? call(m_component_go, scope, NULL) : NULL;
    }
    int visible = 0;
    for (size_t i = 0; i < ROW_BUTTONS && !visible; i++)
        visible = seen->own[i] && unboxed_bool(call(m_active_self, seen->own[i], NULL));
    if (seen->copy && visible != seen->shown) {
        uint8_t value = (uint8_t)visible;
        call(m_set_active, seen->copy, (void *[]){&value});
        seen->shown = visible;
    }
    void *notice = FIELD(self, f_notice, void *);
    int enabled = notice && unboxed_bool(call(m_is_enable, notice, NULL));
    if (seen->button && enabled != seen->enabled) {
        uint8_t value = (uint8_t)enabled;
        call(m_set_is_enable, seen->button, (void *[]){&value});
        seen->enabled = enabled;
    }
    // Fit the row twice a second: it grows to the left, and must stay clear of
    // the counters on the same line (gems, medals, stamina: HeaderParameterBase).
    if (!seen->layout || seen->frames++ % 30) return;
    float row[4], limit = -1e9f;
    if (corners(seen->row, row)) return;
    void *counters = seen->scope ? components(seen->scope, k_counter) : NULL;
    for (size_t i = 0; i < array_length(counters); i++) {
        float box[4];
        void *counter = array_item(counters, i);
        if (!unboxed_bool(call(m_in_hierarchy, call(m_component_go, counter, NULL), NULL))) continue;
        if (corners(call(m_component_tr, counter, NULL), box)) continue;
        if (box[3] > row[1] && box[1] < row[3] && box[2] < row[2] && box[2] > limit) limit = box[2];  // on the row's line, left of it
    }
    float width = rect_width(seen->row);
    if (limit < -1e8f || width <= 0 || row[2] <= row[0]) return;
    float scale = (row[2] - row[0]) / width;  // world units per row unit
    float margin = 6 * scale;
    void *count = call(m_child_count, seen->row, NULL);
    int shown = 0, n = count ? FIELD(count, 16, int) : 0;
    for (int i = 0; i < n; i++)
        shown += unboxed_bool(call(m_active_self, call(m_component_go, call(m_child, seen->row, (void *[]){&i}), NULL), NULL));
    void *now = call(m_get_spacing, seen->layout, NULL);
    float gap = now ? FIELD(now, 16, float) : seen->gap;
    if (shown < 2) return;
    float available = width + (row[0] - limit - margin) / scale;
    float button = (width - gap * (float)(shown - 1)) / (float)shown;
    float want = bunker_row_gap(available, button, shown, seen->gap, 0);
    if (want != gap) {
        call(m_set_spacing, seen->layout, (void *[]){&want});
        char message[96];
        snprintf(message, sizeof message, "Bunker button: row gap %.1f -> %.1f (room %.0f of %.0f)", gap, want, available, width);
        say(message);
    }
}

static int look_up(void) {
#define CLASS(var, ns, name) if (!(var = find_class(ns, name))) { say("Bunker button: missing class " ns "." name); return -1; }
#define METHOD(var, klass, name, args, first) if (!(var = find_method(klass, name, args, first))) { say("Bunker button: missing method " #klass "." name); return -1; }
    CLASS(k_header, "Dark.View.HeadUpDisplay.Header", "HeaderButtons")
    CLASS(k_button, "Dark.View.UserInterface.Parts", "DarkButton")
    CLASS(k_text, "Dark.View.UserInterface.Parts", "DarkTextMeshPro")
    CLASS(k_image, "Dark.View.UserInterface.Parts", "DarkImage")
    CLASS(k_object, "UnityEngine", "Object") CLASS(k_component, "UnityEngine", "Component")
    CLASS(k_gameobject, "UnityEngine", "GameObject") CLASS(k_transform, "UnityEngine", "Transform")
    CLASS(k_rect, "UnityEngine", "RectTransform") CLASS(k_behaviour, "UnityEngine", "Behaviour")
    CLASS(k_texture, "UnityEngine", "Texture2D") CLASS(k_rawimage, "UnityEngine.UI", "RawImage")
    CLASS(k_layout, "UnityEngine.UI", "HorizontalOrVerticalLayoutGroup")
    CLASS(k_action, "System", "Action") CLASS(k_byte, "System", "Byte")
    CLASS(k_counter, "Dark.View.HeadUpDisplay.Header", "HeaderParameterBase") CLASS(k_vector3, "UnityEngine", "Vector3")
    void *conversion, *delegate;
    CLASS(conversion, "UnityEngine", "ImageConversion") CLASS(delegate, "System", "Delegate")
    METHOD(m_start, k_header, "Start", 0, NULL) METHOD(m_update, k_header, "Update", 0, NULL)
    METHOD(m_on_tap_help, k_header, "OnTapHelpButton", 0, NULL)
    METHOD(m_name, k_object, "get_name", 0, NULL) METHOD(m_set_name, k_object, "set_name", 1, NULL)
    METHOD(m_instantiate, k_object, "Instantiate", 1, "UnityEngine.Object")
    METHOD(m_component_go, k_component, "get_gameObject", 0, NULL) METHOD(m_component_tr, k_component, "get_transform", 0, NULL)
    METHOD(m_go_tr, k_gameobject, "get_transform", 0, NULL) METHOD(m_set_active, k_gameobject, "SetActive", 1, NULL)
    METHOD(m_active_self, k_gameobject, "get_activeSelf", 0, NULL)
    METHOD(m_components, k_gameobject, "GetComponentsInternal", 6, NULL)
    METHOD(m_get_component, k_gameobject, "GetComponent", 1, "System.Type")
    METHOD(m_add_component, k_gameobject, "AddComponent", 1, "System.Type")
    METHOD(m_go_ctor, k_gameobject, ".ctor", 1, "System.String")
    METHOD(m_parent, k_transform, "get_parent", 0, NULL) METHOD(m_child_count, k_transform, "get_childCount", 0, NULL)
    METHOD(m_child, k_transform, "GetChild", 1, NULL) METHOD(m_sibling, k_transform, "SetSiblingIndex", 1, NULL)
    METHOD(m_set_parent, k_transform, "SetParent", 2, "UnityEngine.Transform")
    METHOD(m_rect, k_rect, "get_rect", 0, NULL) METHOD(m_corners, k_rect, "GetWorldCorners", 1, NULL)
    METHOD(m_root, k_transform, "get_root", 0, NULL) METHOD(m_in_hierarchy, k_gameobject, "get_activeInHierarchy", 0, NULL)
    METHOD(m_anchor_min, k_rect, "set_anchorMin", 1, NULL) METHOD(m_anchor_max, k_rect, "set_anchorMax", 1, NULL)
    METHOD(m_offset_min, k_rect, "set_offsetMin", 1, NULL) METHOD(m_offset_max, k_rect, "set_offsetMax", 1, NULL)
    METHOD(m_set_enabled, k_behaviour, "set_enabled", 1, NULL)
    METHOD(m_set_text, k_text, "SetText", 1, "System.String")
    METHOD(m_tex_ctor, k_texture, ".ctor", 2, "System.Int32")
    // The two-argument wrapper is stripped from Japanese 3.7.1; both games
    // retain the native overload. Keep its texture readable, like the wrapper.
    METHOD(m_load_image, conversion, "LoadImage", 3, NULL)
    METHOD(m_set_texture, k_rawimage, "set_texture", 1, NULL)
    METHOD(m_register_tap, k_button, "RegisterTapEvent", 1, NULL)
    METHOD(m_is_enable, k_button, "get_IsEnable", 0, NULL) METHOD(m_set_is_enable, k_button, "set_IsEnable", 1, NULL)
    METHOD(m_get_spacing, k_layout, "get_spacing", 0, NULL) METHOD(m_set_spacing, k_layout, "set_spacing", 1, NULL)
    if (find_offset(k_header, "_noticeButton", &f_notice) || find_offset(k_header, "_hasTapEvent", &f_has_tap)) return -1;
    for (size_t i = 0; i < ROW_BUTTONS; i++)
        if (find_offset(k_header, kRowButtons[i], &f_row[i])) return -1;
    if (find_offset(delegate, "method_ptr", &f_method_ptr) || find_offset(delegate, "m_target", &f_target) ||
        find_offset(delegate, "method", &f_method)) return -1;
#undef CLASS
#undef METHOD
    return 0;
}

// IL2CPP starts on Unity's thread while this library is already loaded; its
// classes are looked up only once it has finished (its assembly list has not
// changed for 2 s): touching them earlier crashes the game. Until its core
// library exists, only il2cpp_get_corlib is asked (it changes nothing):
// il2cpp_domain_get would create the domain IL2CPP is still setting up (on iOS
// this library starts before Unity, and the game stayed on a black screen).
static void *install(void *unused) {
    (void)unused;
    for (int i = 0; !il2cpp.get_corlib(); i++) {
        if (i > 1200) { say("Bunker button: the game did not start; no button"); return NULL; }
        usleep(100000);
    }
    size_t last = 0;
    for (int i = 0, steady = 0; steady < 20; i++) {
        if (i > 1200) { say("Bunker button: the game did not start; no button"); return NULL; }
        size_t count = 0;
        if (il2cpp.domain_get()) il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
        steady = count && count == last ? steady + 1 : 0;
        last = count;
        usleep(100000);
    }
    il2cpp.thread_attach(il2cpp.domain_get());
    if (look_up()) { say("Bunker button: unsupported game; no button"); return NULL; }
    start_original = (void (*)(void *, Method *))m_start->pointer;
    update_original = (void (*)(void *, Method *))m_update->pointer;
    m_start->pointer = (void *)start_hook;
    m_update->pointer = (void *)update_hook;
    say("Bunker button: ready");
    return NULL;
}

int bunker_button_init(void *(*resolve)(const char *name), void (*log)(const char *message), void (*open)(void)) {
    report = log;
    open_bunker = open;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_methods)
    LOAD(method_get_name) LOAD(method_get_param_count) LOAD(method_get_param) LOAD(type_get_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(class_get_type) LOAD(type_get_object) LOAD(runtime_invoke)
    LOAD(object_new) LOAD(string_new) LOAD(array_new) LOAD(string_length) LOAD(string_chars) LOAD(thread_attach) LOAD(get_corlib)
#undef LOAD
    big_hunt_season_init(resolve, log);
    arena_season_init(resolve, log);
    pthread_t thread;
    if (pthread_create(&thread, NULL, install, NULL)) return -1;
    pthread_detach(thread);
    return 0;
}
