// Campaign badges set their remaining time once a second, for Android and iOS
// (the iOS launcher builds this file too).
//
// CampaignSingleBadge.Update calls UpdateRemainingTime every frame, which
// formats the time left and hands it to its label (DarkTextMeshPro.SetText).
// TextMeshPro rebuilds the label's mesh and marks its layout dirty on every
// SetText, even with the same text. Lunar Tear keeps campaigns open, so lists
// such as Subquests carry a badge on many rows; at 120 fps the badges and the
// rebuilds they cause were a large part of each frame on those screens.
//
// The time shown changes at most once a second (days, or h:mm:ss), so the
// original Update runs on a badge's first frame and then on its first frame in
// each new second. Update is taken over through its IL2CPP MethodInfo, as
// bunker_button.c does; the game's code is not changed. If anything is missing
// the badges update as before.
#include "badge_pace.h"

#include <pthread.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>
#include <unistd.h>

int badge_pace_due(BadgePace *pace, void *self, void *label, int64_t second) {
    size_t slot = ((uintptr_t)self >> 4) % BADGE_PACE_SLOTS;
    for (size_t probe = 0; probe < 8; probe++) {
        size_t i = (slot + probe) % BADGE_PACE_SLOTS;
        if (pace->self[i] == self) {
            if (pace->label[i] == label && pace->second[i] == second) return 0;
            pace->label[i] = label;
            pace->second[i] = second;
            return 1;
        }
        if (!pace->self[i] || pace->second[i] < second - 2) {  // free, or a badge not seen for a while
            pace->self[i] = self;
            pace->label[i] = label;
            pace->second[i] = second;
            return 1;
        }
    }
    return 1;  // no room: update every frame, as the game does
}

typedef struct { void *pointer; } Method;  // Il2Cpp MethodInfo starts with its code pointer.

static struct {
    void *(*domain_get)(void);
    void **(*domain_get_assemblies)(void *domain, size_t *count);
    void *(*assembly_get_image)(void *assembly);
    void *(*class_from_name)(void *image, const char *ns, const char *name);
    Method *(*class_get_method_from_name)(void *klass, const char *name, int args);
    void *(*class_get_field_from_name)(void *klass, const char *name);
    size_t (*field_get_offset)(void *field);
    void *(*thread_attach)(void *domain);
    void *(*get_corlib)(void);
} il2cpp;

static void (*report)(const char *message);
static Method *update;
static void (*update_original)(void *self, Method *method);
static BadgePace pace;  // Unity's main thread only
static size_t label_offset;  // CampaignSingleBadge._remainingTimeLabel

static void say(const char *message) { if (report) report(message); }

static void update_hook(void *self, Method *method) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    void *label = *(void **)((uint8_t *)self + label_offset);
    if (badge_pace_due(&pace, self, label, (int64_t)now.tv_sec)) update_original(self, method);
}

static void *find_class(const char *ns, const char *name) {
    size_t count = 0;
    void **assemblies = il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
    for (size_t i = 0; i < count; i++) {
        void *klass = il2cpp.class_from_name(il2cpp.assembly_get_image(assemblies[i]), ns, name);
        if (klass) return klass;
    }
    return NULL;
}

// Classes are looked up only once IL2CPP has finished starting, as in bunker_button.c
// (its core library exists, then its assembly list has not changed for 2 s).
static void *install(void *unused) {
    (void)unused;
    for (int i = 0; !il2cpp.get_corlib(); i++) {
        if (i > 1200) { say("Badge pacing: the game did not start"); return NULL; }
        usleep(100000);
    }
    size_t last = 0;
    for (int i = 0, steady = 0; steady < 20; i++) {
        if (i > 1200) { say("Badge pacing: the game did not start"); return NULL; }
        size_t count = 0;
        if (il2cpp.domain_get()) il2cpp.domain_get_assemblies(il2cpp.domain_get(), &count);
        steady = count && count == last ? steady + 1 : 0;
        last = count;
        usleep(100000);
    }
    il2cpp.thread_attach(il2cpp.domain_get());
    void *badge = find_class("Dark.View.UserInterface.Outgame", "CampaignSingleBadge");
    update = badge ? il2cpp.class_get_method_from_name(badge, "Update", 0) : NULL;
    void *label = badge ? il2cpp.class_get_field_from_name(badge, "_remainingTimeLabel") : NULL;
    if (label) label_offset = il2cpp.field_get_offset(label);
    if (!update || !update->pointer || !label) { say("Badge pacing: unsupported game; badges update every frame"); return NULL; }
    update_original = (void (*)(void *, Method *))update->pointer;
    update->pointer = (void *)update_hook;
    say("Badge pacing: ready");
    return NULL;
}

int badge_pace_init(void *(*resolve)(const char *name), void (*log)(const char *message)) {
    report = log;
#define LOAD(name) if (!(*(void **)&il2cpp.name = resolve("il2cpp_" #name))) return -1;
    LOAD(domain_get) LOAD(domain_get_assemblies) LOAD(assembly_get_image) LOAD(class_from_name) LOAD(class_get_method_from_name)
    LOAD(class_get_field_from_name) LOAD(field_get_offset) LOAD(thread_attach) LOAD(get_corlib)
#undef LOAD
    pthread_t thread;
    if (pthread_create(&thread, NULL, install, NULL)) return -1;
    pthread_detach(thread);
    return 0;
}
