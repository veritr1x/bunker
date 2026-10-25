// ARM64 reference: loads the original libFastAES.so and calls it natively.
#include <stdlib.h>
#include <string.h>

#include "cases.h"
#include "elfload.h"

static void stack_chk_fail(void) { abort(); }
static int cxa_atexit(void (*f)(void *), void *arg, void *dso) { return (void)f, (void)arg, (void)dso, 0; }
static void cxa_finalize(void *dso) { (void)dso; }

static void *resolve(const char *name) {
    if (!strcmp(name, "memcpy")) return (void *)memcpy;
    if (!strcmp(name, "memset")) return (void *)memset;
    if (!strcmp(name, "__stack_chk_fail")) return (void *)stack_chk_fail;
    if (!strcmp(name, "__cxa_atexit")) return (void *)cxa_atexit;
    if (!strcmp(name, "__cxa_finalize")) return (void *)cxa_finalize;
    return NULL;
}

int main(void) {
    struct elf_image image;
    if (elf_load(LIB, BASE, resolve, &image)) return 1;
    // The library reads its stack guard from TPIDR_EL0 + 0x28, as on bionic. On glibc that
    // address is inside the thread's static TLS block, readable and stable, which is all it needs.
    return run_cases((aes_enc_fn)elf_symbol(&image, "AES_CBC_encrypt"), (aes_dec_fn)elf_symbol(&image, "AES_CBC_decrypt"));
}
