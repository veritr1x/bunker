"""The guerrilla quests' Force Unlock button shows only while an unlock exists, on iOS too.

Outside their hours the guerrilla quests show their timetable and a Force Unlock
button (EventQuestView.SetVisibleTimeTable). The game data lists when that unlock
exists (m_event_quest_guerrilla_free_open; September 2021 in the live service).
The 3.7.1 game shows the button even before that: with the Original calendar,
early in every loop, it offers an unlock "for 0m" and nothing opens. Now the
button is hidden unless CalculatorGuerrillaQuest.TryGetGuerrillaFreeOpen finds
an unlock valid now, the game's own check.

The method's epilogue jumps to new code that does

    button = view._forceOpenButton; if button:
        button.gameObject.SetActive(TryGetGuerrillaFreeOpen(out _))

and then the epilogue. That code goes in TitleScreen.InitializeMenuButton, whose
first instruction lunar-scripts' ios/patch_ipa.py turns into "ret" (the end-of-
service bypass), so the rest of it never runs. The same as the Android build
(android/app/src/main/cpp/guerrilla_unlock.c). File offsets in the 3.7.1
UnityFramework; applied with text_buffer.patch_words.
"""

TIMETABLE_END = 0x219CAC0  # EventQuestView.SetVisibleTimeTable: ldp x29, x30, [sp, #0x30]
MENU_BUTTON = 0x1F1BCD0    # TitleScreen.InitializeMenuButton, already "ret"
CAVE = MENU_BUTTON + 4
TRY_GET_FREE_OPEN = 0x271F200  # CalculatorGuerrillaQuest.TryGetGuerrillaFreeOpen(out entity)
GET_GAME_OBJECT = 0x4359810    # Component.get_gameObject
SET_ACTIVE = 0x43628D8         # GameObject.SetActive(bool)

# InitializeMenuButton's own instructions after its first, and what replaces them.
_ORIGINAL = (0xA90157F6, 0xA9024FF4, 0xA9037BFD, 0x9100C3FD, 0xAA0003F3, 0xF0022014, 0x395DA288,
             0x370000E8, 0xD0017328, 0xD503201F, 0xB945CD00, 0x97DFF6A6, 0x52800028, 0x391DA288,
             0x90022CA8, 0xD503201F, 0xF942D500, 0x79425C08, 0x36480088)
_CAVE = (
    0xF9404A60,  # ldr x0, [x19, #0x90]      the view's _forceOpenButton
    0xB40001A0,  # cbz x0, done
    0xAA0003F4,  # mov x20, x0
    0x910023E0,  # add x0, sp, #0x8          out entity (a free stack slot)
    0xAA1F03E1,  # mov x1, xzr
    0x94200D46,  # bl TryGetGuerrillaFreeOpen
    0x12000013,  # and w19, w0, #1
    0xAA1403E0,  # mov x0, x20
    0xAA1F03E1,  # mov x1, xzr
    0x9490F6C6,  # bl Component.get_gameObject
    0xB4000080,  # cbz x0, done
    0x2A1303E1,  # mov w1, w19
    0xAA1F03E2,  # mov x2, xzr
    0x94911AF4,  # bl GameObject.SetActive
    0xA9437BFD,  # done: ldp x29, x30, [sp, #0x30]   SetVisibleTimeTable's epilogue
    0xA9424FF4,  # ldp x20, x19, [sp, #0x20]
    0x6D4123E9,  # ldp d9, d8, [sp, #0x10]
    0x910103FF,  # add sp, sp, #0x40
    0xD65F03C0,  # ret
)

SITES = (
    (MENU_BUTTON, 0xD65F03C0, 0xD65F03C0),  # must already be "ret" (lunar-scripts), or nothing is changed
    *((CAVE + 4 * i, original, patched) for i, (original, patched) in enumerate(zip(_ORIGINAL, _CAVE))),
    (TIMETABLE_END, 0xA9437BFD, 0x17F5FC85),  # -> b CAVE
)
