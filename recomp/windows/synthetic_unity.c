// Explicitly synthetic translated Unity stand-in for exercising real libmain's
// loader. It verifies lifecycle/VM plumbing, not real Unity boot or rendering.
#include <stdint.h>
uint32_t synthetic_version = 0x00010006;
static volatile uint64_t constructed, loaded, unloaded, finalized;
__attribute__((constructor)) static void initialize(void) { ++constructed; }
__attribute__((destructor)) static void finalize(void) { ++finalized; }
struct VM { uintptr_t *functions; };
int32_t JNI_OnLoad(struct VM *vm, void *reserved) {
    (void)reserved;
    void *env = 0;
    typedef int32_t (*get_env)(struct VM *, void **, int32_t);
    if (!vm || ((get_env)vm->functions[6])(vm, &env, 0x00010006) || !env) return -1;
    ++loaded;
    return synthetic_version;
}
void JNI_OnUnload(struct VM *vm, void *reserved) { (void)vm; (void)reserved; ++unloaded; }
uint64_t synthetic_counts(void) { return constructed | (loaded << 16) | (unloaded << 32) | (finalized << 48); }
