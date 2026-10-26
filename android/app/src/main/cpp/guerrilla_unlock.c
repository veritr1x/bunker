// The guerrilla quests' Force Unlock button shows only while an unlock exists.
//
// Outside their hours the guerrilla quests show their timetable and a Force
// Unlock button (EventQuestView.SetVisibleTimeTable). The game data lists when
// that unlock exists (m_event_quest_guerrilla_free_open; September 2021 in the
// live service). The 3.7.1 game shows the button even before that: with the
// Original calendar, early in every loop, the button offers an unlock "for 0m"
// and nothing opens. Now, each time the timetable is shown, the button is
// hidden unless CalculatorGuerrillaQuest.TryGetGuerrillaFreeOpen finds an
// unlock valid now, the game's own check.
//
// SetVisibleTimeTable ends with "ldp x29, x30, [sp, #0x20]; ldp x20, x19,
// [sp, #0x10]; ldr d8, [sp], #0x30; ret", which nothing branches into. Those four
// words jump to timetable_shown_hook, which restores the same registers and calls
// timetable_shown(view) in the method's place; it returns to the game's caller.
//
// RVAs from the 3.7.1 ARM64 game's IL2CPP metadata. Every word is checked first.
#include "guerrilla_unlock.h"

#include <stdbool.h>
#include <stddef.h>

static const uint32_t kEpilogue[4] = {0xa9427bfdu, 0xa9414ff4u, 0xfc4307e8u, 0xd65f03c0u};
enum {
    kTimetableEnd = 0x2B01F88,           // EventQuestView.SetVisibleTimeTable, its epilogue
    kTryGetFreeOpen = 0x29420E8,         // CalculatorGuerrillaQuest.TryGetGuerrillaFreeOpen(out entity)
    kGetGameObject = 0x4918DE8,          // Component.get_gameObject
    kSetActive = 0x4921F20,              // GameObject.SetActive(bool)
    kForceOpenButton = 0x90,             // EventQuestView._forceOpenButton
};

static bool (*try_get_free_open)(void **entity, const void *method);
static void *(*get_game_object)(void *component, const void *method);
static void (*set_active)(void *game_object, bool active, const void *method);

__attribute__((visibility("hidden"), used)) void timetable_shown(void *view) {
    void *button = view ? *(void **)((char *)view + kForceOpenButton) : NULL;
    if (!button) return;
    void *entity = NULL;
    bool open = try_get_free_open(&entity, NULL);
    void *object = get_game_object(button, NULL);
    if (object) set_active(object, open, NULL);
}

__attribute__((naked)) static void timetable_shown_hook(void) {
    __asm__ volatile(
        "mov x0, x19\n"
        "ldp x29, x30, [sp, #0x20]\n"
        "ldp x20, x19, [sp, #0x10]\n"
        "ldr d8, [sp], #0x30\n"
        "b timetable_shown\n");
}

int guerrilla_unlock_button(uint8_t *base, int (*hook)(uint32_t *at, const uint32_t original[4], void (*target)(void))) {
    try_get_free_open = (bool (*)(void **, const void *))(base + kTryGetFreeOpen);
    get_game_object = (void *(*)(void *, const void *))(base + kGetGameObject);
    set_active = (void (*)(void *, bool, const void *))(base + kSetActive);
    return hook((uint32_t *)(base + kTimetableEnd), kEpilogue, timetable_shown_hook);
}
