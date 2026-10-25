// Unity destroying an EGL fence sync twice (egl_sync.c).
#pragma once

/** Routes libunity's EGL sync calls through checked wrappers. Returns NULL, or why nothing changed. */
const char *egl_sync_fix(void);
