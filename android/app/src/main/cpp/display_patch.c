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
//   RenderManager never goes above the screen's own resolution.
// - Battles: BattleUpdate advances the battle by one 30 Hz step per frame. It
//   now passes the fraction of a step the frame lasted (30 x frame time, at
//   most one step, as before); the battle's TurnManager accumulates fractions.
// - Field movement: ActorController moves characters in FixedUpdate by its
//   time step, but runs once per rendered frame while physics keeps the 1/30 s
//   step, so at 60 frames characters move twice as fast. Once per frame the
//   physics step is set to that frame's duration (1/240 to 1/30 s); measured
//   on a Galaxy Fold at 60, walking then matches 30 fps (3.7 m/s).
//
// The RVAs come from the 3.7.1 ARM64 game's IL2CPP metadata. Every site is
// checked first; on any unknown instruction nothing is changed.
#include <dlfcn.h>
#include <jni.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

enum { FullHD = 6, WQHD = 7, DeviceMax = 8 };

typedef struct { uint32_t rva, original, patched; } Site;

static uint32_t mov_w(int reg, int value) { return 0x52800000u | (uint32_t)value << 5 | (uint32_t)reg; }

// orr x11, x11, #(size << 32): the immediate is encoded as a run of set bits.
static uint32_t orr_x11_size(int size) {
    switch (size) {
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

/** BattleUpdate.OnStateUpdate's step for KernelBattle.Process: the part of a 30 Hz step this frame lasted. */
__attribute__((visibility("hidden"), used)) double battle_step(void) {
    double step = 30.0 * time_unscaled_delta(NULL);
    return step > 1.0 ? 1.0 : step;
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
// ldp x20, x19, [sp], #0x20; b KernelBattle.Process": the hook sets d0 to battle_step().
static const uint32_t kBattleStepCall[4] = {0x1e6e1000u, 0x2a1f03e1u, 0xaa1f03e2u, 0xa8c24ff4u};
__attribute__((visibility("hidden"), used)) uintptr_t battle_process;
__attribute__((naked)) static void battle_step_hook(void) {
    __asm__ volatile(
        "stp x0, x30, [sp, #-16]!\n"
        "bl battle_step\n"
        "ldp x0, x30, [sp], #16\n"
        "mov w1, wzr\n"
        "mov x2, xzr\n"
        "ldp x20, x19, [sp], #0x20\n"
        "adrp x16, battle_process\n"
        "ldr x16, [x16, :lo12:battle_process]\n"
        "br x16\n");
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

static const char *apply(int fps, int size, char *message, size_t length) {
    Site list[8];
    int count = sites(fps, size, list);
    if (!count) return "";
    void *library = dlopen("libil2cpp.so", RTLD_NOW);
    void *symbol = library ? dlsym(library, "il2cpp_init") : NULL;
    Dl_info info;
    if (!symbol || !dladdr(symbol, &info)) {
        snprintf(message, length, "Game library not found: %s", dlerror());
        return message;
    }
    uint8_t *base = info.dli_fbase;
    const struct { uint32_t rva; const uint32_t *original; } hooks[] = {{0x2D5F7A0, kFixedProcessPrologue}, {0x2A6530C, kBattleStepCall}};
    for (int h = 0; fps > 30 && h < 2; h++) {
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
    if ((fps && (fps < 30 || fps > 240)) || (size && (size < FullHD || size > DeviceMax)))
        return (*env)->NewStringUTF(env, "Unsupported display setting");
    return (*env)->NewStringUTF(env, apply(fps, size, message, sizeof message));
}

