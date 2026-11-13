// Arena battle mods: the MODS button and the BATTLE MODS popup, for Android
// and iOS (the iOS launcher builds this file too). The mods themselves are
// battle_mods.c, which calls hud_frame after each BattleSystemMenuPresenter
// Update.
//
// - The button is a copy of the fast-forward button (the HUD's
//   BattleHighSpeedView, with its view component switched off so the game
//   does not drive the copy), placed one button to the left of it each frame
//   (the row's BattleLayoutGroup places only the game's own), labelled MODS.
//   Its label takes the view's on look while any mod is on, and keeps its own
//   otherwise (the view's off look is made for the fast-forward icon). It
//   shows and locks with fast-forward. Its frame is drawn in the view's off
//   state and its label in the HUD's bright lettering, whatever the mods are
//   (the player's choice: no highlight).
// - The popup is the game's own message dialog (DialogManager.Instance
//   .ShowMessageWithoutLocalizeAsync), titled BATTLE MODS with CLOSE as its
//   button. Each row is a label in the dialog's own message text and, on the
//   right, a copy of its OK button reading ON or of its cancel button reading
//   OFF (one shown at a time); tapping it flips the mod. A row tap flips the mod
//   (battle_mods_set: applied from the next frame and saved).
// - The battle pauses while the popup is open (BattleGame._paused) and goes
//   on when it closes.
// The copies are made as bunker_button.c makes its own (Instantiate(Object)
// + SetParent, a System.Action whose method_ptr is a function here). If
// anything is missing there is no button; the mods keep their settings.
#include "battle_mods.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __ANDROID__
#include "game_region.h"
#endif

typedef struct { void *pointer; } Method;

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
    void (*field_static_get_value)(void *field, void *value);
    void (*runtime_class_init)(void *klass);
    uint32_t (*gchandle_new)(void *object, int pinned);
    void (*gchandle_free)(uint32_t handle);
    void *(*gchandle_get_target)(uint32_t handle);
} il2cpp;

static void (*report)(const char *message);
static int failed;  // the UI gave up for this run; the mods go on

static void *k_animator, *off_state, *k_component, *k_gameobject, *k_button, *k_text, *k_view, *k_action, *k_presenter, *k_context;
static Method *m_instantiate, *m_component_go, *m_component_tr, *m_go_tr, *m_set_active, *m_active_self,
    *m_components, *m_parent, *m_set_parent, *m_sibling_get, *m_sibling_set, *m_set_name, *m_set_enabled,
    *m_set_text, *m_register_tap, *m_is_enable, *m_set_is_enable, *m_anchored, *m_size, *m_show_dialog,
    *m_set_title, *m_find_object, *m_any_void, *m_dialogs, *m_anchored_get, *m_anchor_min, *m_anchor_max, *m_pivot, *m_set_size, *m_wrap, *m_alignment, *m_play, *m_material, *m_color;
static size_t f_on_material, f_auto_view, f_high_speed, f_speed_button, f_frame, f_view, f_ok_text, f_ok_button,
    f_cancel_button, f_content, f_message, f_is_close, f_game, f_paused, f_method_ptr, f_target, f_method;

static void say(const char *message) { if (report) report(message); }

#define FIELD(object, offset, type) (*(type *)((uint8_t *)(object) + (offset)))

static void *find_class(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), ns, name);
        if (klass) return klass;
    }
    return NULL;
}

static Method *find_method(void *klass, const char *name, int args, const char *first) {
    void *iter = NULL;
    Method *m;
    while (klass && (m = il2cpp.class_get_methods(klass, &iter))) {
        if (strcmp(il2cpp.method_get_name(m), name) || (int)il2cpp.method_get_param_count(m) != args) continue;
        if (!first) return m;
        char *type = il2cpp.type_get_name(il2cpp.method_get_param(m, 0));
        int same = type && !strcmp(type, first);
        free(type);
        if (same) return m;
    }
    return NULL;
}

static int offset(void *klass, const char *name, size_t *out) {
    void *field = klass ? il2cpp.class_get_field_from_name(klass, name) : NULL;
    if (field) *out = il2cpp.field_get_offset(field);
    return field ? 0 : -1;
}

static void *call(Method *m, void *object, void **args) {
    void *exception = NULL;
    void *result = il2cpp.runtime_invoke(m, object, args, &exception);
    if (exception && !failed) {
        char line[160];
        snprintf(line, sizeof line, "Battle mods: the game refused %s; no MODS button until the app restarts", il2cpp.method_get_name(m));
        say(line);
        failed = 1;
    }
    return exception ? NULL : result;
}

static void *type_of(void *klass) { return il2cpp.type_get_object(il2cpp.class_get_type(klass)); }
static int unboxed_bool(void *boxed) { return boxed ? FIELD(boxed, 16, uint8_t) : 0; }
static int unboxed_int(void *boxed) { return boxed ? FIELD(boxed, 16, int32_t) : 0; }
static int alive(void *object) { return object && FIELD(object, 16, void *) != NULL; }  // Unity object not destroyed
static void *array_item(void *array, size_t i) { return ((void **)((uint8_t *)array + 32))[i]; }
static size_t array_length(void *array) { return array ? FIELD(array, 24, size_t) : 0; }

static void *first_component(void *gameobject, void *klass) {
    uint8_t yes = 1, no = 0;
    void *all = call(m_components, gameobject, (void *[]){type_of(klass), &yes, &yes, &yes, &no, NULL});
    return array_length(all) ? array_item(all, 0) : NULL;
}

static void set_text(void *text, const char *value) { if (text) call(m_set_text, text, (void *[]){il2cpp.string_new(value)}); }

/** A System.Action that calls fn(target) when the game invokes it. */
static void *action_for(void (*fn)(void *target, Method *m), void *target) {
    void *action = il2cpp.object_new(k_action);
    if (!action) return NULL;
    FIELD(action, f_method_ptr, void *) = (void *)fn;
    FIELD(action, f_target, void *) = target;
    FIELD(action, f_method, void *) = m_any_void;  // any void() method: the delegate calls method_ptr
    return action;
}

// --- Text ----------------------------------------------------------------------

enum { T_MODS, T_TITLE, T_NO_DEATH, T_ONE_HIT, T_ZERO_COOLDOWN, T_ON, T_OFF, T_CLOSE };
static const char *const kEnglish[] = {"MODS", "BATTLE MODS", "No Death", "One Hit", "Zero Cooldown", "ON", "OFF", "CLOSE"};
static const char *const kJapanese[] = {"改造", "バトル改造", "不死", "一撃", "クールタイムなし", "ON", "OFF", "閉じる"};

static const char *text(int id) {
#ifdef __ANDROID__
    if (bunker_game_japanese) return kJapanese[id];
#endif
    (void)kJapanese;
    return kEnglish[id];
}

// --- The popup -------------------------------------------------------------------

enum { CLOSED, OPENING, OPEN };
static int popup = CLOSED;
static int opening_frames;
static uint32_t dialog;   // GC handle on the MessageDialogPresenter
static void *rows_on[3], *rows_off[3];  // each row's ON and OFF buttons (one shown; either is its tap target)
static void *paused_game; // the BattleGame paused while the popup is open

static int *mod_of(BattleMods *mods, int row) {
    return row == 0 ? &mods->no_death : row == 1 ? &mods->one_hit : &mods->zero_cooldown;
}

/** Shows the row's ON or OFF button, as its mod is. */
static void label_row(int row) {
    BattleMods mods = battle_mods_get();
    uint8_t on = (uint8_t)(*mod_of(&mods, row) != 0), off = (uint8_t)!on;
    if (rows_on[row]) call(m_set_active, rows_on[row], (void *[]){&on});
    if (rows_off[row]) call(m_set_active, rows_off[row], (void *[]){&off});
}

static void row_tap(void *target, Method *m) {
    (void)m;
    for (int row = 0; row < 3; row++) {
        if (rows_on[row] != target && rows_off[row] != target) continue;
        BattleMods mods = battle_mods_get();
        int *mod = mod_of(&mods, row);
        *mod = !*mod;
        battle_mods_set(mods);
        label_row(row);
    }
}

static void pause_battle(void *presenter_context, int pause) {
    if (pause) {
        void *game = presenter_context ? FIELD(presenter_context, f_game, void *) : NULL;
        if (!game) return;
        FIELD(game, f_paused, uint8_t) = 1;
        paused_game = game;
    } else if (paused_game) {
        FIELD(paused_game, f_paused, uint8_t) = 0;
        paused_game = NULL;
    }
}

/** The battle's BattleContext, as battle_mods.c finds it. */
static void *battle_context(void) { return call(m_find_object, NULL, (void *[]){type_of(k_context)}); }

/** Turns the open message dialog into BATTLE MODS; 1 when done. */
/** A copy of a UI GameObject under parent, named and shown; its RectTransform, or NULL. */
static void *copy_into(void *original, void *parent, const char *name, void **made) {
    uint8_t yes = 1, no = 0;
    void *copy = original ? call(m_instantiate, NULL, (void *[]){original}) : NULL;
    void *transform = copy ? call(m_go_tr, copy, NULL) : NULL;
    if (!transform) return NULL;
    call(m_set_parent, transform, (void *[]){parent, &no});
    call(m_set_name, copy, (void *[]){il2cpp.string_new(name)});
    call(m_set_active, copy, (void *[]){&yes});
    *made = copy;
    return transform;
}

/** Anchors a RectTransform at (x, 0.5) of its parent, with the same pivot, at offset (dx, dy); size when w > 0. */
static void put(void *transform, float x, float dx, float dy, float w, float h) {
    float anchor[2] = {x, 0.5f}, at[2] = {dx, dy}, size[2] = {w, h};
    call(m_anchor_min, transform, (void *[]){anchor});
    call(m_anchor_max, transform, (void *[]){anchor});
    call(m_pivot, transform, (void *[]){anchor});
    if (w > 0) call(m_set_size, transform, (void *[]){size});
    call(m_anchored, transform, (void *[]){at});
}

/** The row's button: tapping either state's copy flips the mod. */
static int tappable(void *copy) {
    void *button = first_component(copy, k_button);
    void *action = button ? action_for(row_tap, copy) : NULL;
    if (!action) return 0;
    call(m_register_tap, button, (void *[]){action});
    return 1;
}

/** Turns the open message dialog into BATTLE MODS: per row, a label in the dialog's own text on the left and an
 * ON button (OK's look) or OFF button (cancel's look) on the right. 1 when done. */
static int dress_dialog(void *presenter) {
    void *frame = FIELD(presenter, f_frame, void *);
    void *view = FIELD(presenter, f_view, void *);
    void *content = view ? FIELD(view, f_content, void *) : NULL;
    void *ok = frame ? FIELD(frame, f_ok_button, void *) : NULL;
    void *message = view ? FIELD(view, f_message, void *) : NULL;
    if (!frame || !content || !ok || !message) return 0;
    call(m_set_title, frame, (void *[]){il2cpp.string_new(text(T_TITLE))});
    set_text(FIELD(frame, f_ok_text, void *), text(T_CLOSE));
    set_text(message, "");
    void *cancel = FIELD(frame, f_cancel_button, void *);
    void *ok_object = call(m_component_go, ok, NULL);
    void *cancel_object = cancel ? call(m_component_go, cancel, NULL) : NULL;
    void *message_object = call(m_component_go, message, NULL);
    uint8_t no = 0;
    void *size = call(m_size, call(m_component_tr, ok, NULL), NULL);
    float height = size ? FIELD(size, 20, float) : 0;  // Vector2 boxed: x at 16, y at 20
    if (height <= 0) height = 80;
    for (int row = 0; row < 3 && !failed; row++) {
        float y = (1 - row) * height * 1.5f, margin = height * 0.75f;
        void *label = NULL;
        void *label_tr = copy_into(message_object, content, "battle_mods_label", &label);
        if (!label_tr) return 0;
        put(label_tr, 0, margin, y, height * 6, height);
        void *label_text = first_component(label, k_text);
        int left = 4097;  // TextAlignmentOptions.MidlineLeft
        if (label_text) {
            call(m_alignment, label_text, (void *[]){&left});
            call(m_wrap, label_text, (void *[]){&no});
            set_text(label_text, text(T_NO_DEATH + row));
        }
        void *on_tr = copy_into(ok_object, content, "battle_mods_on", &rows_on[row]);
        // The OFF look is the dialog's cancel button; OK's again if this dialog has none.
        void *off_tr = copy_into(cancel_object ? cancel_object : ok_object, content, "battle_mods_off", &rows_off[row]);
        if (!on_tr || !off_tr) return 0;
        put(on_tr, 1, -margin, y, 0, 0);
        put(off_tr, 1, -margin, y, 0, 0);
        set_text(first_component(rows_on[row], k_text), text(T_ON));
        set_text(first_component(rows_off[row], k_text), text(T_OFF));
        if (!tappable(rows_on[row]) || !tappable(rows_off[row])) return 0;
        label_row(row);
    }
    // The dialog's own cancel button stays hidden (no cancel was asked for); hide it after copying in case it showed.
    if (cancel_object) call(m_set_active, cancel_object, (void *[]){&no});
    return !failed;
}

static void open_popup(void *target, Method *m) {
    (void)target, (void)m;
    if (popup != CLOSED || !battle_mods_in_arena()) return;
    void *dialogs = call(m_dialogs, NULL, NULL);
    if (!dialogs) return;
    int size = 1;  // DialogSize.Medium
    uint8_t outside = 0;
    call(m_show_dialog, dialogs, (void *[]){&size, il2cpp.string_new(text(T_TITLE)), il2cpp.string_new(" "),
                                           il2cpp.string_new(text(T_CLOSE)), NULL, &outside});  // opens over the next frames
    if (failed) return;
    popup = OPENING;
    opening_frames = 0;
    pause_battle(battle_context(), 1);
}

static void watch_popup(void) {
    if (popup == OPENING) {
        void *presenter = call(m_find_object, NULL, (void *[]){type_of(k_presenter)});
        if (presenter && FIELD(presenter, f_frame, void *) && dress_dialog(presenter)) {
            dialog = il2cpp.gchandle_new(presenter, 0);
            popup = OPEN;
        } else if (++opening_frames > 300 || failed) {  // 10 s at 30 fps: give up, the battle goes on
            say("Battle mods: the popup did not open");
            popup = CLOSED;
            pause_battle(NULL, 0);
        }
        return;
    }
    if (popup == OPEN) {
        void *presenter = il2cpp.gchandle_get_target(dialog);
        if (alive(presenter) && !FIELD(presenter, f_is_close, uint8_t)) return;
        il2cpp.gchandle_free(dialog);
        dialog = 0;
        memset(rows_on, 0, sizeof rows_on);
        memset(rows_off, 0, sizeof rows_off);
        popup = CLOSED;
        pause_battle(NULL, 0);
    }
}

// --- The button ------------------------------------------------------------------

static uint32_t hud;     // GC handle on the presenter the button was made for
static int frames_since_added;  // since the copy was made (settle_look)
static void *button_animator, *on_material, *button_object, *button, *button_text, *auto_object, *speed_object, *speed_button;

static void add_button(void *presenter) {
    void *view = FIELD(presenter, f_high_speed, void *);
    speed_button = view ? FIELD(view, f_speed_button, void *) : NULL;
    if (!speed_button) return;
    void *original = call(m_component_go, view, NULL);
    speed_object = original;
    void *auto_view = FIELD(presenter, f_auto_view, void *);
    auto_object = auto_view ? call(m_component_go, auto_view, NULL) : NULL;
    on_material = FIELD(view, f_on_material, void *);
    void *original_tr = original ? call(m_go_tr, original, NULL) : NULL;
    void *row = original_tr ? call(m_parent, original_tr, NULL) : NULL;
    uint8_t yes = 1, no = 0;
    void *copy = row ? call(m_instantiate, NULL, (void *[]){original}) : NULL;
    void *transform = copy ? call(m_go_tr, copy, NULL) : NULL;
    if (!transform) return;
    call(m_set_parent, transform, (void *[]){row, &no});
    int at = unboxed_int(call(m_sibling_get, original_tr, NULL)) + 1;
    call(m_sibling_set, transform, (void *[]){&at});
    call(m_set_name, copy, (void *[]){il2cpp.string_new("battle_mods_button")});
    void *copied_view = first_component(copy, k_view);  // the game must not drive the copy
    if (copied_view) call(m_set_enabled, copied_view, (void *[]){&no});
    call(m_set_active, copy, (void *[]){&yes});
    // Drawn as fast-forward is when off: the copy's animator would keep the look fast-forward had.
    void *animator = button_animator = first_component(copy, k_animator);
    frames_since_added = 0;
    int layer = -1;
    float start = 0;
    if (animator && off_state) call(m_play, animator, (void *[]){off_state, &layer, &start});
    button_object = copy;
    button_text = first_component(copy, k_text);
    set_text(button_text, text(T_MODS));
    button = first_component(copy, k_button);
    void *action = button ? action_for(open_popup, copy) : NULL;
    if (!action) return;
    call(m_register_tap, button, (void *[]){action});
    hud = il2cpp.gchandle_new(presenter, 0);
    say("Battle mods: MODS button added");
}

static int position_of(void *gameobject, float out[2]) {
    void *transform = alive(gameobject) ? call(m_go_tr, gameobject, NULL) : NULL;
    void *boxed = transform ? call(m_anchored_get, transform, NULL) : NULL;
    if (!boxed) return -1;
    memcpy(out, (uint8_t *)boxed + 16, sizeof(float) * 2);
    return 0;
}

/** One button to the left of fast-forward, as far as AUTO is to its right. */
static void place(void) {
    float speed[2], other[2], at[2];
    if (position_of(speed_object, speed) || position_of(auto_object, other) || position_of(button_object, at)) return;
    float step = other[0] - speed[0];
    if (step == 0) step = 160;
    float want[2] = {speed[0] - step, speed[1]};
    if (want[0] != at[0] || want[1] != at[1]) call(m_anchored, call(m_go_tr, button_object, NULL), (void *[]){want});
}

/** The copy follows fast-forward: shown, and tappable, with it. */
/** Once the off state has been drawn: the copy's animator stops (the off look is made for the fast-forward icon and
 * dims a word), and the label takes the HUD's bright lettering: the view's on material and a cream colour, as AUTO
 * reads when lit, whatever the mods are. */
static void settle_look(void) {
    if (frames_since_added++ != 5) return;
    uint8_t no = 0;
    if (alive(button_animator)) call(m_set_enabled, button_animator, (void *[]){&no});
    if (!button_text) return;
    if (on_material) call(m_material, button_text, (void *[]){on_material});
    // The off state also darkens the label's colour; the HUD's cream lettering instead (as AUTO reads when lit).
    float cream[4] = {0.93f, 0.91f, 0.84f, 1};
    call(m_color, button_text, (void *[]){cream});
}

static void follow(void) {
    int shown = alive(speed_object) && unboxed_bool(call(m_active_self, speed_object, NULL));
    if (unboxed_bool(call(m_active_self, button_object, NULL)) != shown) {
        uint8_t v = (uint8_t)shown;
        call(m_set_active, button_object, (void *[]){&v});
    }
    int enabled = unboxed_bool(call(m_is_enable, speed_button, NULL));
    if (unboxed_bool(call(m_is_enable, button, NULL)) != enabled) {
        uint8_t v = (uint8_t)enabled;
        call(m_set_is_enable, button, (void *[]){&v});
    }
    place();
    settle_look();
}

static void hud_frame(void *presenter) {
    if (failed) return;
    void *made_for = hud ? il2cpp.gchandle_get_target(hud) : NULL;
    if (made_for != presenter || !alive(button_object)) {
        if (hud) { il2cpp.gchandle_free(hud); hud = 0; }
        button_object = NULL;
        if (!battle_mods_in_arena()) return;  // not yet known, or not the Arena: no button
        add_button(presenter);
        if (!button_object || failed) return;
    }
    follow();
    watch_popup();
}

// --- Start-up ----------------------------------------------------------------------

static int look_up(void) {
#define CLASS(var, ns, name) if (!(var = find_class(ns, name))) { say("Battle mods: missing class " name "; no MODS button"); return -1; }
#define METHOD(var, klass, name, args, first) if (!(var = find_method(klass, name, args, first))) { say("Battle mods: missing method " name "; no MODS button"); return -1; }
#define OFFSET(var, klass, name) if (offset(klass, name, &var)) { say("Battle mods: missing field " name "; no MODS button"); return -1; }
    void *object, *transform, *rect, *behaviour, *tmp, *frame, *dialog_presenter, *view, *game, *delegate;
    CLASS(object, "UnityEngine", "Object") CLASS(k_component, "UnityEngine", "Component")
    CLASS(k_gameobject, "UnityEngine", "GameObject") CLASS(transform, "UnityEngine", "Transform")
    CLASS(rect, "UnityEngine", "RectTransform") CLASS(behaviour, "UnityEngine", "Behaviour") CLASS(tmp, "TMPro", "TMP_Text")
    CLASS(k_button, "Dark.View.UserInterface.Parts", "DarkButton") CLASS(k_text, "Dark.View.UserInterface.Parts", "DarkTextMeshPro")
    CLASS(k_view, "Dark.View.HeadUpDisplay", "BattleHighSpeedView") CLASS(k_animator, "UnityEngine", "Animator")
    METHOD(m_play, k_animator, "Play", 3, "System.String")
    METHOD(m_material, tmp, "set_fontSharedMaterial", 1, NULL) METHOD(m_color, tmp, "set_color", 1, NULL)
    OFFSET(f_on_material, k_view, "_onMaterial")
    // The view's "off" animation state, by its own name (BattleHighSpeedView.kOffState).
    void *off_field = il2cpp.class_get_field_from_name(k_view, "kOffState");
    if (!off_field) { say("Battle mods: missing field kOffState; no MODS button"); return -1; }
    il2cpp.runtime_class_init(k_view);
    il2cpp.field_static_get_value(off_field, &off_state);
    CLASS(k_presenter, "Dark.View.UserInterface.Dialog", "MessageDialogPresenter")
    CLASS(dialog_presenter, "Dark.View.UserInterface.Dialog", "DialogPresenter")
    CLASS(view, "Dark.View.UserInterface.Dialog", "MessageDialogView") CLASS(frame, "Dark.View.UserInterface.Dialog", "DialogFrame")
    CLASS(k_context, "Adam.Framework.GameKit.TurnBattle", "BattleContext") CLASS(game, "Adam.Framework.GameKit.TurnBattle", "BattleGame")
    CLASS(k_action, "System", "Action") CLASS(delegate, "System", "Delegate")
    void *menu;
    CLASS(menu, "Dark.View.HeadUpDisplay", "BattleSystemMenuPresenter")
    METHOD(m_instantiate, object, "Instantiate", 1, "UnityEngine.Object")
    METHOD(m_set_name, object, "set_name", 1, NULL) METHOD(m_find_object, object, "FindObjectOfType", 1, "System.Type")
    METHOD(m_component_go, k_component, "get_gameObject", 0, NULL) METHOD(m_component_tr, k_component, "get_transform", 0, NULL)
    METHOD(m_go_tr, k_gameobject, "get_transform", 0, NULL) METHOD(m_set_active, k_gameobject, "SetActive", 1, NULL)
    METHOD(m_active_self, k_gameobject, "get_activeSelf", 0, NULL)
    METHOD(m_components, k_gameobject, "GetComponentsInternal", 6, NULL)
    METHOD(m_parent, transform, "get_parent", 0, NULL) METHOD(m_set_parent, transform, "SetParent", 2, "UnityEngine.Transform")
    METHOD(m_sibling_get, transform, "GetSiblingIndex", 0, NULL) METHOD(m_sibling_set, transform, "SetSiblingIndex", 1, NULL)
    METHOD(m_anchored, rect, "set_anchoredPosition", 1, NULL) METHOD(m_size, rect, "get_sizeDelta", 0, NULL)
    METHOD(m_set_enabled, behaviour, "set_enabled", 1, NULL)
    METHOD(m_set_text, k_text, "SetText", 1, "System.String")
    METHOD(m_wrap, tmp, "set_enableWordWrapping", 1, NULL) METHOD(m_alignment, tmp, "set_alignment", 1, NULL)
    METHOD(m_register_tap, k_button, "RegisterTapEvent", 1, NULL)
    METHOD(m_is_enable, k_button, "get_IsEnable", 0, NULL) METHOD(m_set_is_enable, k_button, "set_IsEnable", 1, NULL)
    void *manager;
    CLASS(manager, "Dark.View.UserInterface.Dialog", "DialogManager")
    METHOD(m_dialogs, manager, "get_Instance", 0, NULL)
    METHOD(m_show_dialog, manager, "ShowMessageWithoutLocalizeAsync", 6, NULL)
    METHOD(m_anchored_get, rect, "get_anchoredPosition", 0, NULL)
    METHOD(m_anchor_min, rect, "set_anchorMin", 1, NULL) METHOD(m_anchor_max, rect, "set_anchorMax", 1, NULL)
    METHOD(m_pivot, rect, "set_pivot", 1, NULL) METHOD(m_set_size, rect, "set_sizeDelta", 1, NULL)
    METHOD(m_set_title, frame, "SetTitle", 1, NULL)
    METHOD(m_any_void, menu, "Show", 0, NULL)
    OFFSET(f_high_speed, menu, "_highSpeedView") OFFSET(f_auto_view, menu, "_autoView") OFFSET(f_speed_button, k_view, "_doubleSpeedButton")
    OFFSET(f_frame, dialog_presenter, "_frame") OFFSET(f_view, k_presenter, "_view")
    OFFSET(f_ok_button, frame, "_okButton") OFFSET(f_ok_text, frame, "_okButtonText") OFFSET(f_cancel_button, frame, "_cancelButton")
    OFFSET(f_content, view, "_dialogContent") OFFSET(f_message, view, "_message")
    OFFSET(f_game, k_context, "_game") OFFSET(f_paused, game, "_paused")
    OFFSET(f_method_ptr, delegate, "method_ptr") OFFSET(f_target, delegate, "m_target") OFFSET(f_method, delegate, "method")
    void *base;
    CLASS(base, "Dark.View.UserInterface.Dialog", "DialogPresenterBase")
    OFFSET(f_is_close, base, "<IsClose>k__BackingField")
#undef CLASS
#undef METHOD
#undef OFFSET
    return 0;
}

static int looked_up;  // 0 not yet, 1 ready, -1 missing

static void first_frame(void *presenter) {
    if (!looked_up) {
        looked_up = look_up() ? -1 : 1;
        if (looked_up < 0) return;
    }
    if (looked_up > 0) hud_frame(presenter);
}

int battle_mods_ui_init(void *(*resolve)(const char *name), void (*log)(const char *message)) {
    report = log;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_methods)
    LOAD(method_get_name) LOAD(method_get_param_count) LOAD(method_get_param) LOAD(type_get_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(class_get_type) LOAD(type_get_object) LOAD(runtime_invoke)
    LOAD(object_new) LOAD(string_new) LOAD(field_static_get_value) LOAD(runtime_class_init) LOAD(gchandle_new) LOAD(gchandle_free) LOAD(gchandle_get_target)
#undef LOAD
    // The classes are looked up on the first battle frame (Unity's thread, IL2CPP fully up).
    battle_mods_set_hud_hook(first_frame);
    return 0;
}
