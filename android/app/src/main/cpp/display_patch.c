// Frame rate and resolution for the 3.7.1 game, chosen in Pod Programs.
//
// Runs in the game's process before Unity starts (see DisplayPatch.java). It
// loads the game library first and rewrites a few instructions in memory:
//
// - Frame rate: the game sets Application.targetFrameRate to 30 at start (two
//   places), and its performance presets ask OnDemandRendering for 30 frames
//   (Dark.Component.PerformanceSetting.Config, UnSavePowerTargetRenderFrameRate).
//   Both become the chosen rate (up to the screen's maximum refresh rate).
//   Power saving keeps its own 10 frames.
// - Resolution: the presets with effects on (the start preset, Highest and
//   High) and the first resolution the game sets use the chosen RenderTargetSize.
//   RenderManager never goes above the screen's own resolution. 540p and 640p go
//   below the game's own 720p (HD) to use less memory.
// - Battles: BattleUpdate advances the battle by one 30 Hz step per frame. It
//   now advances it by one whole step each time 1/30 s of frame time has
//   built up, and skips the frames in between. Fractional steps crashed the
//   summon reveal, which runs on the battle code.
// - Field movement: ActorController moves characters in FixedUpdate by its
//   time step, but runs once per rendered frame while physics keeps the 1/30 s
//   step, so at 60 frames characters move twice as fast. Once per frame the
//   physics step is set to that frame's duration (1/240 to 1/30 s); measured
//   on a Galaxy Fold at 60, walking then matches 30 fps (3.7 m/s).
// - Story-event zones: a zone the player walks through while an event's
//   balloon fades out still counts (see the notes above state_changing). This
//   one applies at every frame rate, the game's own 30 included.
// - Special Gift Roulette: IronSource.showRewardedVideo raises the video's
//   "rewarded" and "closed" events at once instead (roulette_ads.c). This one
//   applies with any settings too.
// - Text builder: ArtStringBuilder grows its buffer to fit long text instead of
//   writing past its end (text_buffer.c). This one applies with any settings too.
// - Remaining days: "{0}d" times stop at 999 days, so a campaign left open to
//   2099 fits its badge (remain_days.c). Any setting.
// - EGL fence syncs: Unity's render worker can destroy a sync twice, which on
//   Android 17 stops the game on a black screen (egl_sync.c). Any setting.
// - Google Play services: Firebase's start-up check passes without them
//   (play_services.c), so de-Googled phones get past the logo. Any setting.
// - Snapping lists (the summon banners): DarkScrollRect.UpdateSnapPosition eases
//   the list to the chosen row with SmoothDamp and counts it as there within
//   0.01. Above 30 fps each frame's step is so small that, far down a long list,
//   it is below the position's float precision: the list stops just short,
//   keeps a small speed, and IsScrolling stays true, so the Summon buttons
//   ignore taps. It now counts as there within 1 unit (invisible). Any setting.
//
// The RVAs come from the 3.7.1 ARM64 game's IL2CPP metadata. Every site is
// checked first; on any unknown instruction nothing is changed.
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <unistd.h>

#include "egl_sync.h"
#include "play_services.h"
#include "remain_days.h"
#include "roulette_ads.h"
#include "text_buffer.h"

// RenderTargetSize, from the game's metadata: H320 1, H450 2, H540 3, H640 4, HD 5 (its own), FullHD 6, WQHD 7, DeviceMax 8.
enum { H540 = 3, H640 = 4, FullHD = 6, WQHD = 7, DeviceMax = 8 };

typedef struct { uint32_t rva, original, patched; } Site;

static uint32_t mov_w(int reg, int value) { return 0x52800000u | (uint32_t)value << 5 | (uint32_t)reg; }

// orr x11, x11, #(size << 32): the immediate is encoded as a run of set bits.
static uint32_t orr_x11_size(int size) {
    switch (size) {
    case H540: return 0xb260056bu;
    case H640: return 0xb25e016bu;
    case FullHD: return 0xb25f056bu;
    case WQHD: return 0xb260096bu;
    default: return 0xb25d016bu;
    }
}

static int sites(int fps, int size, Site *out) {
    int n = 0;
    if (fps) {
        out[n++] = (Site){0x2E5BE0C, 0x321f0fe0u, mov_w(0, fps)};  // Generator.OnlyWhenStarting: targetFrameRate = 30
        out[n++] = (Site){0x2E5C31C, 0x321f0fe0u, mov_w(0, fps)};  // Generator.SetupRenderer: targetFrameRate = 30
        out[n++] = (Site){0x2C7AC80, 0x321f0fe9u, mov_w(9, fps)};  // Config..cctor: UnSavePowerTargetRenderFrameRate = 30
    }
    if (size) {
        out[n++] = (Site){0x2C7ACD8, 0xd2c000aau, 0xd2c0000au | (uint32_t)size << 5};  // Config..cctor: HD for the start preset and High
        out[n++] = (Site){0x2C7AD10, 0xb25f056bu, orr_x11_size(size)};                 // Config..cctor: FullHD for Highest
        out[n++] = (Site){0x2EC1D04, 0x528000a1u, mov_w(1, size)};                      // RenderManager.DelayStart: HD at start
    }
    return n;
}

static int write_word(uint32_t *address, uint32_t value) {
    uintptr_t page = (uintptr_t)sysconf(_SC_PAGESIZE);
    void *start = (void *)((uintptr_t)address & ~(page - 1));
    if (mprotect(start, page, PROT_READ | PROT_WRITE | PROT_EXEC)) return -1;
    *(volatile uint32_t *)address = value;
    __builtin___clear_cache((char *)address, (char *)(address + 1));
    mprotect(start, page, PROT_READ | PROT_EXEC);
    return 0;
}

// UpdateSnapPosition: "ldr s0, [x8, #0x18]" (kScrollBorder, 0.01) becomes "fmov s0, #1.0".
static const Site kSnapArrive = {0x30DF5A0, 0xbd401900u, 0x1e2e1000u};

// Unity's Time accessors, from the same metadata.
static float (*time_unscaled_delta)(void *method);
static float (*time_fixed_delta)(void *method);
static void (*time_set_fixed_delta)(float value, void *method);
static int (*time_frame_count)(void *method);
static int last_frame = -1;

/** Runs at the start of ActorController.FixedProcess, on Unity's main thread. */
__attribute__((visibility("hidden"), used)) void follow_frame_time(void) {
    int frame = time_frame_count(NULL);
    if (frame == last_frame) return;
    last_frame = frame;
    float step = time_unscaled_delta(NULL);
    if (step < 1 / 240.f) step = 1 / 240.f;
    if (step > 1 / 30.f) step = 1 / 30.f;
    if (time_fixed_delta(NULL) != step) time_set_fixed_delta(step, NULL);
}

static double battle_time;

/** Whether BattleUpdate.OnStateUpdate runs a 30 Hz step this frame: 1 once 1/30 s has built up, else 0. */
__attribute__((visibility("hidden"), used)) int battle_step(void) {
    battle_time += 30.0 * time_unscaled_delta(NULL);
    if (battle_time < 1.0) return 0;
    // At most one step per frame, as before; a long frame doesn't build a backlog.
    battle_time = battle_time >= 2.0 ? 0.0 : battle_time - 1.0;
    return 1;
}

// Replaces four instructions with "ldr x16, #8; br x16; <hook address>". The
// first word is the "already hooked" marker.
static int hook(uint32_t *at, const uint32_t original[4], void (*target)(void)) {
    if (at[0] == 0x58000050u) return 0;
    for (int i = 0; i < 4; i++) if (at[i] != original[i]) return -1;
    uintptr_t page = (uintptr_t)sysconf(_SC_PAGESIZE), start = (uintptr_t)at & ~(page - 1);
    if (mprotect((void *)start, page * 2, PROT_READ | PROT_WRITE | PROT_EXEC)) return -1;
    at[0] = 0x58000050u;  // ldr x16, #8
    at[1] = 0xd61f0200u;  // br x16
    *(volatile uint64_t *)&at[2] = (uint64_t)(uintptr_t)target;
    __builtin___clear_cache((char *)at, (char *)(at + 4));
    mprotect((void *)start, page * 2, PROT_READ | PROT_EXEC);
    return 0;
}

// BattleUpdate.OnStateUpdate ends with "fmov d0, #1.0; mov w1, wzr; mov x2, xzr;
// ldp x20, x19, [sp], #0x20; b KernelBattle.Process": the hook makes that call only
// when battle_step() is 1, and otherwise returns.
static const uint32_t kBattleStepCall[4] = {0x1e6e1000u, 0x2a1f03e1u, 0xaa1f03e2u, 0xa8c24ff4u};
__attribute__((visibility("hidden"), used)) uintptr_t battle_process;
__attribute__((naked)) static void battle_step_hook(void) {
    __asm__ volatile(
        "stp x0, x30, [sp, #-16]!\n"
        "bl battle_step\n"
        "mov w17, w0\n"
        "ldp x0, x30, [sp], #16\n"
        "ldp x20, x19, [sp], #0x20\n"
        "cbz w17, 1f\n"
        "fmov d0, #1.0\n"
        "mov w1, wzr\n"
        "mov x2, xzr\n"
        "adrp x16, battle_process\n"
        "ldr x16, [x16, :lo12:battle_process]\n"
        "br x16\n"
        "1: ret\n");
}

// FixedProcess(this, float deltaTime, MethodInfo*) starts with these four instructions;
// the hook runs them after follow_frame_time and continues at the fifth.
static const uint32_t kFixedProcessPrologue[4] = {0xd10283ffu, 0x6d033befu, 0x6d0433edu, 0x6d052bebu};
__attribute__((visibility("hidden"), used)) uintptr_t fixed_process_resume;
__attribute__((naked)) static void fixed_process_hook(void) {
    __asm__ volatile(
        "stp x0, x1, [sp, #-32]!\n"
        "stp x30, xzr, [sp, #16]\n"
        "str s0, [sp, #24]\n"
        "bl follow_frame_time\n"
        "ldr s0, [sp, #24]\n"
        "ldr x30, [sp, #16]\n"
        "ldp x0, x1, [sp], #32\n"
        "sub sp, sp, #0xa0\n"
        "stp d15, d14, [sp, #0x30]\n"
        "stp d13, d12, [sp, #0x40]\n"
        "stp d11, d10, [sp, #0x50]\n"
        "adrp x16, fixed_process_resume\n"
        "ldr x16, [x16, :lo12:fixed_process_resume]\n"
        "br x16\n");
}

// Story-event zones. An event state waits for the player to walk into a zone
// (EventTriggerOnEnterCollision) for a few seconds; when that times out, the
// event plays a 1.5 s balloon fade and then waits on the same zone with
// EventTriggerOnEnterCollision plus EventTriggerOnStayCollision. A player who
// walks into the zone during the fade has left it before that fallback starts,
// so neither fires and the event never continues (6-4: Levania walks off the
// map). Even at 30 fps a steady walk reaches 6-4's second zone 2 ms before
// its time-out; above 30 the faster story text and frame timing put players in
// that gap. When such a fallback starts, a collider that entered its zone in
// the last 10 s is passed to EventTriggerOnStayCollision.OnStay, which checks
// it is the player's and continues the event as if they were still there.
typedef struct { void *zone, *collider; double time; } ZoneEntry;
static ZoneEntry zone_entries[32];
static int zone_next;
typedef struct { void *conductor; double since; } ZoneFallback;
static ZoneFallback zone_fallbacks[8];
static void *stay_class, *enter_class;
static void (*stay_on_stay)(void *self, void *collider, void *method);
static uintptr_t stay_begin, stay_update_original;

static double now_seconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

/** Runs at the start of ColliderBase.OnTriggerEnter: remembers who entered which zone. */
__attribute__((visibility("hidden"), used)) void zone_entered(void *zone, void *collider) {
    zone_entries[zone_next] = (ZoneEntry){zone, collider, now_seconds()};
    zone_next = (zone_next + 1) % 32;
}

/** EventTriggerOnStayCollision's OnStateUpdate (an empty virtual it inherits). */
static void stay_update(void *self, void *method) {
    for (int i = 0; i < 8; i++) {
        if (zone_fallbacks[i].conductor != self) continue;
        double since = zone_fallbacks[i].since;
        zone_fallbacks[i].conductor = NULL;
        void *zone = *(void **)((char *)self + 0x50);
        for (int e = 0; zone && e < 32 && !*((uint8_t *)self + 0x59); e++)
            // A destroyed collider (its scene unloading) has a null m_CachedPtr.
            if (zone_entries[e].zone == zone && zone_entries[e].time >= since - 10
                && *(void **)((char *)zone_entries[e].collider + 0x10)) {
                stay_on_stay(self, zone_entries[e].collider, NULL);
                if (*((uint8_t *)self + 0x59))
                    __android_log_print(ANDROID_LOG_INFO, "Bunker", "Story event continued: the player passed its zone %.1f s ago",
                                        since - zone_entries[e].time);
            }
    }
    if (stay_update_original) ((void (*)(void *, void *))stay_update_original)(self, method);
}

/** Points the class's OnStateUpdate slot (after OnStateBegin) at stay_update. */
static void route_stay_update(void *klass, uint8_t *base) {
    uintptr_t *slots = klass;
    for (int i = 0; i < 0x100; i++) {
        if (slots[i] != stay_begin) continue;
        if (slots[i + 2] == (uintptr_t)(base + 0x3A05C64)) {
            stay_update_original = slots[i + 2];
            slots[i + 2] = (uintptr_t)stay_update;
        }
        return;
    }
}

static uint8_t *game_base;

/** Runs at the start of InternalFiniteStateMachine.ChangeState with the next state. */
__attribute__((visibility("hidden"), used)) void state_changing(void *state) {
    void *list = state ? *(void **)((char *)state + 0x48) : NULL;
    void *items = list ? *(void **)((char *)list + 0x10) : NULL;
    int size = list ? *(int *)((char *)list + 0x18) : 0;
    void *stay = NULL, *stay_zone = NULL, *enter_zone = NULL;
    for (int i = 0; items && i < size && i < 8; i++) {
        void *conductor = ((void **)((char *)items + 0x20))[i];
        void *klass = conductor ? *(void **)conductor : NULL;
        if (!klass) continue;
        if (!stay_class && !strcmp(*(const char **)((char *)klass + 0x10), "EventTriggerOnStayCollision")) {
            stay_class = klass;
            route_stay_update(klass, game_base);
        }
        if (!enter_class && !strcmp(*(const char **)((char *)klass + 0x10), "EventTriggerOnEnterCollision")) enter_class = klass;
        if (klass == stay_class) { stay = conductor; stay_zone = *(void **)((char *)conductor + 0x50); }
        if (klass == enter_class) enter_zone = *(void **)((char *)conductor + 0x58);
    }
    if (!stay || !stay_zone || stay_zone != enter_zone) return;
    int slot = 0;
    for (int i = 0; i < 8; i++) if (zone_fallbacks[i].conductor == stay || !zone_fallbacks[i].conductor) { slot = i; break; }
    zone_fallbacks[slot] = (ZoneFallback){stay, now_seconds()};
}

static const uint32_t kChangeState[4] = {0xa9ba6ffcu, 0xa90167fau, 0xa9025ff8u, 0xa90357f6u};
__attribute__((visibility("hidden"), used)) uintptr_t change_state_resume;
__attribute__((naked)) static void change_state_hook(void) {
    __asm__ volatile(
        "stp x0, x1, [sp, #-48]!\n"
        "stp x2, x3, [sp, #16]\n"
        "str x30, [sp, #32]\n"
        "mov x0, x1\n"
        "bl state_changing\n"
        "ldr x30, [sp, #32]\n"
        "ldp x2, x3, [sp, #16]\n"
        "ldp x0, x1, [sp], #48\n"
        "stp x28, x27, [sp, #-0x60]!\n"
        "stp x26, x25, [sp, #0x10]\n"
        "stp x24, x23, [sp, #0x20]\n"
        "stp x22, x21, [sp, #0x30]\n"
        "adrp x16, change_state_resume\n"
        "ldr x16, [x16, :lo12:change_state_resume]\n"
        "br x16\n");
}

static const uint32_t kTriggerEnter[4] = {0xf81d0ff5u, 0xa9014ff4u, 0xa9027bfdu, 0x910083fdu};
__attribute__((visibility("hidden"), used)) uintptr_t trigger_enter_resume;
__attribute__((naked)) static void trigger_enter_hook(void) {
    __asm__ volatile(
        "stp x0, x1, [sp, #-48]!\n"
        "stp x2, x3, [sp, #16]\n"
        "str x30, [sp, #32]\n"
        "bl zone_entered\n"
        "ldr x30, [sp, #32]\n"
        "ldp x2, x3, [sp, #16]\n"
        "ldp x0, x1, [sp], #48\n"
        "str x21, [sp, #-0x30]!\n"
        "stp x20, x19, [sp, #0x10]\n"
        "stp x29, x30, [sp, #0x20]\n"
        "add x29, sp, #0x20\n"
        "adrp x16, trigger_enter_resume\n"
        "ldr x16, [x16, :lo12:trigger_enter_resume]\n"
        "br x16\n");
}

static int hook_event_zones(uint8_t *base) {
    game_base = base;
    stay_on_stay = (void (*)(void *, void *, void *))(base + 0x2984420);
    stay_begin = (uintptr_t)(base + 0x2984210);
    change_state_resume = (uintptr_t)(base + 0x3A0ECF8 + 16);
    trigger_enter_resume = (uintptr_t)(base + 0x363082C + 16);
    if (hook((uint32_t *)(base + 0x3A0ECF8), kChangeState, change_state_hook)) return -1;
    return hook((uint32_t *)(base + 0x363082C), kTriggerEnter, trigger_enter_hook);
}

static int hook_frame_rate(uint8_t *base) {
    time_unscaled_delta = (float (*)(void *))(base + 0x4D7ED90);
    time_fixed_delta = (float (*)(void *))(base + 0x4D7EDC4);
    time_set_fixed_delta = (void (*)(float, void *))(base + 0x4D7EDF8);
    time_frame_count = (int (*)(void *))(base + 0x4D7EF50);
    fixed_process_resume = (uintptr_t)(base + 0x2D5F7A0 + 16);
    battle_process = (uintptr_t)(base + 0x37DC3D0);
    if (hook((uint32_t *)(base + 0x2D5F7A0), kFixedProcessPrologue, fixed_process_hook)) return -1;
    return hook((uint32_t *)(base + 0x2A6530C), kBattleStepCall, battle_step_hook);
}

static void *game_library;
static void *game_symbol(const char *name) { return dlsym(game_library, name); }
static void roulette_log(const char *message) { __android_log_print(ANDROID_LOG_INFO, "Bunker", "%s", message); }

// IronSource.showRewardedVideo starts "stp x20, x19, [sp, #-0x20]!; stp x29, x30, [sp, #0x10];
// add x29, sp, #0x10; adrp x20, ..."; the hook replaces the whole method.
static const uint32_t kShowRewardedVideo[4] = {0xa9be4ff4u, 0xa9017bfdu, 0x910043fdu, 0xd00237f4u};

static void hook_roulette_ads(uint8_t *base) {
    if (roulette_ads_init(game_symbol, roulette_log, NULL) || hook((uint32_t *)(base + 0x3291FB4), kShowRewardedVideo, (void (*)(void))roulette_ads_show))
        __android_log_print(ANDROID_LOG_WARN, "Bunker", "Special Gift Roulette: unsupported game binary; the video ad stays");
}

static const char *apply(int fps, int size, char *message, size_t length) {
    Site list[8];
    int count = sites(fps, size, list);
    void *library = dlopen("libil2cpp.so", RTLD_NOW);
    void *symbol = library ? dlsym(library, "il2cpp_init") : NULL;
    Dl_info info;
    if (!symbol || !dladdr(symbol, &info)) {
        snprintf(message, length, "Game library not found: %s", dlerror());
        return message;
    }
    uint8_t *base = info.dli_fbase;
    game_library = library;
    hook_roulette_ads(base);
    uint32_t *snap = (uint32_t *)(base + kSnapArrive.rva);
    if (*snap == kSnapArrive.original) write_word(snap, kSnapArrive.patched);
    else if (*snap != kSnapArrive.patched)
        __android_log_print(ANDROID_LOG_WARN, "Bunker", "Snapping lists: unsupported game binary; summon buttons can stop answering above 30 fps");
    if (text_buffer_fix(base, write_word))
        __android_log_print(ANDROID_LOG_WARN, "Bunker", "Text builder: unsupported game binary; long texts can still overrun");
    if (remain_days_cap(base, write_word))
        __android_log_print(ANDROID_LOG_WARN, "Bunker", "Remaining days: unsupported game binary; open campaigns show their full day count");
    const char *egl = egl_sync_fix();
    if (egl) __android_log_print(ANDROID_LOG_WARN, "Bunker", "%s", egl);
    const char *play = play_services_fix(write_word);
    if (play) __android_log_print(ANDROID_LOG_WARN, "Bunker", "%s", play);
    const struct { uint32_t rva; const uint32_t *original; } hooks[] = {{0x2D5F7A0, kFixedProcessPrologue}, {0x2A6530C, kBattleStepCall},
        {0x3A0ECF8, kChangeState}, {0x363082C, kTriggerEnter}};
    // The event-zone hooks (2 and 3) go in at every frame rate; the frame-timing ones only above 30.
    for (int h = fps > 30 ? 0 : 2; h < 4; h++) {
        uint32_t *at = (uint32_t *)(base + hooks[h].rva);
        if (at[0] == 0x58000050u) continue;
        for (int i = 0; i < 4; i++) if (at[i] != hooks[h].original[i]) {
            snprintf(message, length, "Unsupported game binary at 0x%X; nothing changed", hooks[h].rva);
            return message;
        }
    }
    for (int i = 0; i < count; i++) {
        uint32_t now = *(uint32_t *)(base + list[i].rva);
        if (now != list[i].original && now != list[i].patched) {
            snprintf(message, length, "Unsupported game binary at 0x%X (found %08X); nothing changed", list[i].rva, now);
            return message;
        }
    }
    for (int i = 0; i < count; i++) {
        uint32_t *address = (uint32_t *)(base + list[i].rva);
        if (*address != list[i].patched && write_word(address, list[i].patched)) {
            snprintf(message, length, "Could not write the game code at 0x%X", list[i].rva);
            return message;
        }
    }
    if (hook_event_zones(base)) {
        snprintf(message, length, "Could not write the game's story-event code");
        return message;
    }
    if (fps > 30 && hook_frame_rate(base)) {
        snprintf(message, length, "Could not write the game's frame timing code");
        return message;
    }
    return "";
}

/** Applies the choices; 0 keeps the game's own value. Returns "" or an error. */
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_DisplayPatch_apply(JNIEnv *env, jclass cls, jint fps, jint size) {
    (void)cls;
    char message[160];
    if ((fps && (fps < 30 || fps > 240)) || (size && (size < H540 || size > DeviceMax || size == 5)))
        return (*env)->NewStringUTF(env, "Unsupported display setting");
    return (*env)->NewStringUTF(env, apply(fps, size, message, sizeof message));
}

