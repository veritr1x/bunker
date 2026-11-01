// Upscaling below the screen's own resolution on Android (render_scale.c).
#pragma once

/** Upscalers, as display.conf's upscale names them. */
enum { RENDER_SCALE_OFF = 0, RENDER_SCALE_FSR = 1, RENDER_SCALE_SGSR = 2 };

/** Hooks libunity's window, surface and swap imports for mode. Returns NULL, or why nothing changed. */
const char *render_scale_init(int mode);

/** egl_sync.c's lookups pass every function Unity asks EGL or dlsym for through this. */
void *render_scale_wrap(const char *name, void *function);
