// Frame rate and resolution for the 3.7.1 game, chosen in Pod Programs.
//
// Runs in the game's process before Unity starts (see DisplayPatch.java). It
// loads the game library first and rewrites a few instructions in memory:
//
// - Frame rate: the game sets Application.targetFrameRate to 30 at start (two
//   places), and its performance presets ask OnDemandRendering for 30 frames
//   (Dark.Component.PerformanceSetting.Config, UnSavePowerTargetRenderFrameRate).
//   Both become the chosen rate. Power saving keeps its own 10 frames.
// - Resolution: the presets with effects on (the start preset, Highest and
//   High) and the first resolution the game sets use the chosen RenderTargetSize.
//   RenderManager never goes above the screen's own resolution.
// - Battles: BattleUpdate advances the battle by one 30 Hz step per frame; at
//   higher rates it passes the fraction of a step a frame lasts.
// - Field movement: ActorController moves characters in FixedUpdate by its
//   time step, but runs once per rendered frame while physics keeps the 1/30 s
//   step, so at 60 frames characters move twice as fast. Once per frame the
//   physics step is set to that frame's duration (1/60 to 1/30 s); measured on
//   a Galaxy Fold, walking then matches 30 fps (3.7 m/s).
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
        // BattleUpdate.OnStateUpdate: KernelBattle.Process(battle, 1.0, false) advances the battle by one
        // 30 Hz step every frame. At 60 frames pass 0.5: TurnManager accumulates it, one step per two frames.
        out[n++] = (Site){0x2A6530C, 0x1e6e1000u, fps >= 60 ? 0x1e6c1000u : 0x1e6e1000u};  // fmov d0, #1.0 -> #0.5
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
    if (step < 1 / 60.f) step = 1 / 60.f;
    if (step > 1 / 30.f) step = 1 / 30.f;
    if (time_fixed_delta(NULL) != step) time_set_fixed_delta(step, NULL);
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

static int hook_fixed_process(uint8_t *base) {
    uint32_t *at = (uint32_t *)(base + 0x2D5F7A0);
    if (at[0] == 0x58000050u) return 0;  // Already hooked.
    for (int i = 0; i < 4; i++) if (at[i] != kFixedProcessPrologue[i]) return -1;
    time_unscaled_delta = (float (*)(void *))(base + 0x4D7ED90);
    time_fixed_delta = (float (*)(void *))(base + 0x4D7EDC4);
    time_set_fixed_delta = (void (*)(float, void *))(base + 0x4D7EDF8);
    time_frame_count = (int (*)(void *))(base + 0x4D7EF50);
    fixed_process_resume = (uintptr_t)(at + 4);
    uintptr_t page = (uintptr_t)sysconf(_SC_PAGESIZE), start = (uintptr_t)at & ~(page - 1);
    if (mprotect((void *)start, page * 2, PROT_READ | PROT_WRITE | PROT_EXEC)) return -1;
    at[0] = 0x58000050u;  // ldr x16, #8
    at[1] = 0xd61f0200u;  // br x16
    *(volatile uint64_t *)&at[2] = (uint64_t)(uintptr_t)fixed_process_hook;
    __builtin___clear_cache((char *)at, (char *)(at + 4));
    mprotect((void *)start, page * 2, PROT_READ | PROT_EXEC);
    return 0;
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
    uint32_t *fixed = (uint32_t *)(base + 0x2D5F7A0);
    if (fps > 30 && fixed[0] != 0x58000050u)
        for (int i = 0; i < 4; i++) if (fixed[i] != kFixedProcessPrologue[i]) {
            snprintf(message, length, "Unsupported game binary at 0x2D5F7A0; nothing changed");
            return message;
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
    if (fps > 30 && hook_fixed_process(base)) {
        snprintf(message, length, "Could not write the game code at 0x2D5F7A0");
        return message;
    }
    return "";
}

/** Applies the choices; 0 keeps the game's own value. Returns "" or an error. */
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_DisplayPatch_apply(JNIEnv *env, jclass cls, jint fps, jint size) {
    (void)cls;
    char message[160];
    if ((fps && (fps < 30 || fps > 120)) || (size && (size < FullHD || size > DeviceMax)))
        return (*env)->NewStringUTF(env, "Unsupported display setting");
    return (*env)->NewStringUTF(env, apply(fps, size, message, sizeof message));
}

