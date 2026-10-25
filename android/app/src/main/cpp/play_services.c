// The game's Firebase start-up checks Google Play services before the title
// screen (Firebase_App_CSharp_CheckAndroidDependencies, then again after
// trying to fix them). Without them the check never passes and the game stays
// black after the logo, on de-Googled phones and Waydroid. Firebase's
// google_play_services::CheckAvailability now answers 0 (available), as it
// does on a phone that has them; the server stands in for Firebase's services.
// The other two waits are answered in Java (NoPlayServices.java).
//
// The library is the game's 3.7.1 libFirebaseCppApp-9_6_0.so; the function's
// first instructions are checked first, and on anything else nothing changes.
#include "play_services.h"

#include <dlfcn.h>

static const uint32_t kCheckAvailability[2] = {0xa9bd57f6u, 0xa9014ff4u};

const char *play_services_fix(int (*write_word)(uint32_t *address, uint32_t value)) {
    void *firebase = dlopen("libFirebaseCppApp-9_6_0.so", RTLD_NOW);
    uint32_t *check = firebase ? dlsym(firebase, "_ZN20google_play_services17CheckAvailabilityEP7_JNIEnvP8_jobject") : NULL;
    if (!check) return "Play services: Firebase library not found";
    if (check[0] == 0x2a1f03e0u && check[1] == 0xd65f03c0u) return NULL;
    if (check[0] != kCheckAvailability[0] || check[1] != kCheckAvailability[1])
        return "Play services: unsupported Firebase library; nothing changed";
    // mov w0, wzr; ret
    if (write_word(check + 1, 0xd65f03c0u) || write_word(check, 0x2a1f03e0u))
        return "Play services: could not write Firebase's check";
    return NULL;
}
