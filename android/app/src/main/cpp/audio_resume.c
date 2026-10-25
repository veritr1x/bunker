// Music after the game comes back (AudioResume.java).
//
// The game's Unity (2019.4.29f1) stops its audio output when the game is
// paused, and on Android 10 and later it does not start it again when the
// game resumes: after switching to the Bunker, the home screen or any other
// app, the game stays silent until it is restarted (Unity's UUM-5652, fixed
// only in 2020.3). Unity keeps the native calls to stop and start the output
// (AudioSettings.Mobile), though the game's own code does not use them.
//
// Stopping and starting the output brings the sound back, but only once the
// game has resumed: at the moment it regains focus, Unity's own resume runs
// after and leaves it silent again. So the focus after a pause, which Unity
// reports through Application.InvokeFocusChanged, only sets a time a second
// later and 5 frames on, as frames only come once Unity has resumed (its
// pause and resume take seconds on a slow phone or emulator);
// Canvas.SendWillRenderCanvases, which Unity calls every frame, does the
// restart then. Both run on Unity's main thread. Their entries are
// pointed here, and each then runs the game's own method as before.
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

typedef struct { void *pointer; } MethodInfo;

static void (*focus_original)(bool focus, const void *method);
static void (*frame_original)(const void *method);
static void (*start_output)(void);
static void (*stop_output)(void);
static volatile bool paused;
static double restart_at;
static int restart_frames;

static double now_seconds(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

/** Application.InvokeFocusChanged(bool focus). */
static void focus_changed(bool focus, const void *method) {
    if (focus && paused) {
        paused = false;
        restart_at = now_seconds() + 1.0;
        restart_frames = 5;
    }
    focus_original(focus, method);
}

/** Canvas.SendWillRenderCanvases(), once a frame. */
static void frame(const void *method) {
    if (restart_at && --restart_frames <= 0 && now_seconds() >= restart_at) {
        restart_at = 0;
        stop_output();
        start_output();
        __android_log_print(ANDROID_LOG_INFO, "Bunker", "Music: audio output started again after a pause");
    }
    frame_original(method);
}

static MethodInfo *find_method(void *domain, const char *assembly_name, const char *klass, const char *name, int args) {
    void *il2cpp = dlopen("libil2cpp.so", RTLD_NOW);
    void *(*assembly_open)(void *, const char *) = dlsym(il2cpp, "il2cpp_domain_assembly_open");
    void *(*assembly_image)(void *) = dlsym(il2cpp, "il2cpp_assembly_get_image");
    void *(*class_from_name)(void *, const char *, const char *) = dlsym(il2cpp, "il2cpp_class_from_name");
    void *(*method_from_name)(void *, const char *, int) = dlsym(il2cpp, "il2cpp_class_get_method_from_name");
    if (!assembly_open || !assembly_image || !class_from_name || !method_from_name) return NULL;
    void *assembly = assembly_open(domain, assembly_name);
    void *cls = assembly ? class_from_name(assembly_image(assembly), "UnityEngine", klass) : NULL;
    MethodInfo *method = cls ? method_from_name(cls, name, args) : NULL;
    return method && method->pointer ? method : NULL;
}

static const char *install(void) {
    if (focus_original) return "";
    void *il2cpp = dlopen("libil2cpp.so", RTLD_NOW);
    if (!il2cpp) return "game library not found";
    // il2cpp_domain_get creates the domain if there is none yet, which crashes
    // before Unity has started IL2CPP; its core library being loaded says it has.
    void *(*get_corlib)(void) = dlsym(il2cpp, "il2cpp_get_corlib");
    void *(*domain_get)(void) = dlsym(il2cpp, "il2cpp_domain_get");
    void *(*thread_attach)(void *) = dlsym(il2cpp, "il2cpp_thread_attach");
    void (*thread_detach)(void *) = dlsym(il2cpp, "il2cpp_thread_detach");
    void *(*resolve_icall)(const char *) = dlsym(il2cpp, "il2cpp_resolve_icall");
    if (!get_corlib || !domain_get || !thread_attach || !resolve_icall) return "IL2CPP functions not found";
    if (!get_corlib()) return "not ready";
    void *domain = domain_get();
    if (!domain) return "not ready";
    void *thread = thread_attach(domain);
    MethodInfo *focus = find_method(domain, "UnityEngine.CoreModule", "Application", "InvokeFocusChanged", 1);
    MethodInfo *canvases = find_method(domain, "UnityEngine.UIModule", "Canvas", "SendWillRenderCanvases", 0);
    start_output = (void (*)(void))resolve_icall("UnityEngine.AudioSettings::StartAudioOutput");
    stop_output = (void (*)(void))resolve_icall("UnityEngine.AudioSettings::StopAudioOutput");
    if (thread && thread_detach) thread_detach(thread);
    if (!focus || !canvases) return "Unity's focus or canvas callback not found";
    if (!start_output || !stop_output) return "Unity's audio output calls not found";
    frame_original = canvases->pointer;
    canvases->pointer = (void *)frame;
    focus_original = focus->pointer;
    focus->pointer = (void *)focus_changed;
    return "";
}

/** Points Unity's two callbacks here. Returns "", "not ready" (try later) or why not. */
JNIEXPORT jstring JNICALL Java_org_veritr1x_bunker_AudioResume_nativeInstall(JNIEnv *env, jclass cls) {
    (void)cls;
    return (*env)->NewStringUTF(env, install());
}

/** The game was paused: its audio output needs starting once it is back. */
JNIEXPORT void JNICALL Java_org_veritr1x_bunker_AudioResume_nativePaused(JNIEnv *env, jclass cls) {
    (void)env;
    (void)cls;
    paused = true;
}
