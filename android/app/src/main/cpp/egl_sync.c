// Unity's frame pacing (Swappy, inside libunity) fences each frame with an EGL
// sync: the render thread creates it, a waiter thread waits on it, the render
// thread destroys it. Now and then the render thread destroys one twice. The
// Android 17 emulator's driver then frees memory twice and the allocator
// (Scudo) stops the game: "invalid chunk state when deallocating", SIGABRT in
// eglDestroySyncKHR on Thread-9. Unity's crash handler holds the process, so
// the screen stays black after the logo. About every other start crashed so.
//
// libunity's imports of eglGetProcAddress and dlsym (it reads libEGL.so's
// sync functions both ways) now go through lookup() and lookup_symbol() below,
// which hand Unity wrappers for the three sync functions. They keep the set of
// live syncs: a destroy or wait on a sync that is not live is skipped (and
// logged once) instead of reaching the driver.
//
// The GOT offsets come from the 3.7.1 ARM64 libunity.so (R_AARCH64_JUMP_SLOT
// eglGetProcAddress and dlsym). Each slot is checked to hold that function
// first; on anything else nothing is changed.
#include "egl_sync.h"

#include <android/log.h>
#include <dlfcn.h>
#include <pthread.h>
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>
#include <unistd.h>

typedef void *(*GetProc)(const char *name);
typedef void *(*Symbol)(void *handle, const char *name);
typedef void *(*CreateSync)(void *display, unsigned type, const int *attributes);
typedef unsigned (*DestroySync)(void *display, void *sync);
typedef int (*ClientWaitSync)(void *display, void *sync, int flags, unsigned long long timeout);

enum { kGotEglGetProcAddress = 0x123E600, kGotDlsym = 0x123E570, kLive = 256 };
enum { EGL_TRUE_ = 1, EGL_CONDITION_SATISFIED_KHR_ = 0x30F6 };

static GetProc real_lookup;
static Symbol real_symbol;
static CreateSync real_create;
static DestroySync real_destroy;
static ClientWaitSync real_wait;

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static void *live[kLive];
static int skipped_destroy, skipped_wait;

static int find(void *sync) {
    for (int i = 0; i < kLive; i++) if (live[i] == sync) return i;
    return -1;
}

static void *create(void *display, unsigned type, const int *attributes) {
    void *sync = real_create(display, type, attributes);
    if (!sync) return sync;
    pthread_mutex_lock(&lock);
    int slot = find(NULL);
    // A full table means Unity keeps more syncs than expected; stop checking those.
    if (slot >= 0) live[slot] = sync;
    pthread_mutex_unlock(&lock);
    return sync;
}

static unsigned destroy(void *display, void *sync) {
    pthread_mutex_lock(&lock);
    int slot = find(sync);
    if (slot >= 0) live[slot] = NULL;
    int skip = slot < 0 && sync != NULL && find(NULL) >= 0;
    int first = skip && skipped_destroy++ == 0;
    pthread_mutex_unlock(&lock);
    if (first) __android_log_print(ANDROID_LOG_WARN, "Bunker", "EGL sync: skipped destroying a sync that was already destroyed");
    return skip ? EGL_TRUE_ : real_destroy(display, sync);
}

static int wait_sync(void *display, void *sync, int flags, unsigned long long timeout) {
    pthread_mutex_lock(&lock);
    int skip = sync != NULL && find(sync) < 0 && find(NULL) >= 0;
    int first = skip && skipped_wait++ == 0;
    pthread_mutex_unlock(&lock);
    if (first) __android_log_print(ANDROID_LOG_WARN, "Bunker", "EGL sync: skipped waiting on a sync that was already destroyed");
    return skip ? EGL_CONDITION_SATISFIED_KHR_ : real_wait(display, sync, flags, timeout);
}

static void *wrap(const char *name, void *function) {
    if (!function || !name) return function;
    if (!strcmp(name, "eglCreateSyncKHR")) { real_create = (CreateSync)function; return (void *)create; }
    if (!strcmp(name, "eglDestroySyncKHR")) { real_destroy = (DestroySync)function; return (void *)destroy; }
    if (!strcmp(name, "eglClientWaitSyncKHR")) { real_wait = (ClientWaitSync)function; return (void *)wait_sync; }
    return function;
}

static void *lookup(const char *name) { return wrap(name, real_lookup(name)); }
static void *lookup_symbol(void *handle, const char *name) {
    void *function = real_symbol(handle, name);
    // Swappy (Unity's frame pacing) reads eglGetProcAddress this way, then the sync functions through it.
    if (function && name && !strcmp(name, "eglGetProcAddress")) return (void *)lookup;
    return wrap(name, function);
}

/** Points one of libunity's imports at replacement, if it holds expected. */
static int redirect(uint8_t *base, uintptr_t offset, void *expected, void *replacement) {
    void **slot = (void **)(base + offset);
    if (*slot == replacement) return 0;
    if (*slot != expected) return -1;
    uintptr_t page = (uintptr_t)sysconf(_SC_PAGESIZE), start = (uintptr_t)slot & ~(page - 1);
    if (mprotect((void *)start, page, PROT_READ | PROT_WRITE)) return -1;
    *slot = replacement;
    return 0;
}

const char *egl_sync_fix(void) {
    void *unity = dlopen("libunity.so", RTLD_NOW);
    void *egl = dlopen("libEGL.so", RTLD_NOW);
    void *proc = egl ? dlsym(egl, "eglGetProcAddress") : NULL;
    void *anchor = unity ? dlsym(unity, "JNI_OnLoad") : NULL;
    Dl_info info;
    if (!proc || !anchor || !dladdr(anchor, &info)) return "EGL sync: Unity library not found";
    uint8_t *base = info.dli_fbase;
    void **lookup_slot = (void **)(base + kGotEglGetProcAddress), **symbol_slot = (void **)(base + kGotDlsym);
    if ((*lookup_slot != proc && *lookup_slot != (void *)lookup) || (*symbol_slot != (void *)dlsym && *symbol_slot != (void *)lookup_symbol))
        return "EGL sync: unsupported Unity library; nothing changed";
    real_lookup = (GetProc)proc;
    real_symbol = dlsym;
    if (redirect(base, kGotEglGetProcAddress, proc, (void *)lookup) || redirect(base, kGotDlsym, (void *)dlsym, (void *)lookup_symbol))
        return "EGL sync: could not write Unity's imports";
    __android_log_print(ANDROID_LOG_INFO, "Bunker", "EGL sync: checking Unity's fence syncs");
    return NULL;
}
