// Minimal loader for an Android AArch64 shared library: maps it at a fixed base,
// applies its relocations and resolves imports through a callback. The same
// layout is used natively on ARM64 and as the memory image for recompiled code.
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void *(*elf_resolver)(const char *name);

struct elf_image {
    uint8_t *base;
    size_t span;
    const uint8_t *file;
    const void *dynsym;
    const char *dynstr;
    size_t nsyms;
};

// Returns 0 on success; prints the reason and returns -1 otherwise.
int elf_load(const char *path, uintptr_t base, elf_resolver resolve, struct elf_image *image);
void *elf_symbol(const struct elf_image *image, const char *name);

#ifdef __cplusplus
}
#endif
