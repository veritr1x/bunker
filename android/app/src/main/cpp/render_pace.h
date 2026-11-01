// How often the game draws, above the game's own 30 fps (render_pace.c).
#pragma once

/** Seconds without a touch (outside battles) before drawing slows to 30 a second. */
#define RENDER_PACE_IDLE_SECONDS 2.0

/**
 * Loads the IL2CPP API through resolve ("il2cpp_domain_get", ...) and, once the
 * game has started, takes over EventSystem.Update to pace drawing each frame.
 * fps is the chosen rate (above 30); idle and heat turn the two slow-downs on.
 * each_frame (or NULL) also runs every frame on Unity's main thread, from the
 * first frame after IL2CPP has started. Returns 0, or -1 if the API is missing.
 */
int render_pace_init(void *(*resolve)(const char *name), void (*log)(const char *message), int fps, int idle, int heat,
                     void (*each_frame)(void));

/** 1 once EventSystem.Update is taken over and render_pace.c sets the render interval each frame. */
int render_pace_active(void);

/** The device's heat: 0 nominal, 1 fair, 2 serious, 3 critical (iOS thermalState, Android thermal status). */
void render_pace_set_thermal(int level);

/** The pacing state, for render_pace.c and its tests. Starts zeroed. */
typedef struct {
    int last_set;  // the interval written last; 0 before the first
    int game;      // the interval the game itself asked for
    double idle;   // seconds without a touch, outside battles
} RenderPace;

/**
 * The OnDemandRendering.renderFrameInterval for this frame: the game's own
 * (power saving), or slower while idle (30 a second) or hot (60 when serious,
 * 30 when critical). current is the interval in effect; delta the frame's
 * unscaled time.
 */
int render_pace_decide(RenderPace *pace, int fps, int current, float delta, int touching, int battle, int thermal, int idle, int heat);
