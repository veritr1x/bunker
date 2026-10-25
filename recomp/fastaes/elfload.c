#define _GNU_SOURCE
#include "elfload.h"

#include <elf.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>

#ifndef R_AARCH64_ABS64
#define R_AARCH64_ABS64 257
#define R_AARCH64_GLOB_DAT 1025
#define R_AARCH64_JUMP_SLOT 1026
#define R_AARCH64_RELATIVE 1027
#endif

static uint8_t *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc(size);
    if (data && fread(data, 1, size, f) != (size_t)size) data = (free(data), NULL);
    fclose(f);
    return data;
}

static int relocate(struct elf_image *image, const Elf64_Rela *rela, size_t count, elf_resolver resolve) {
    const Elf64_Sym *syms = image->dynsym;
    for (size_t i = 0; i < count; i++) {
        uint64_t *slot = (uint64_t *)(image->base + rela[i].r_offset);
        uint32_t type = ELF64_R_TYPE(rela[i].r_info), sym = ELF64_R_SYM(rela[i].r_info);
        if (type == R_AARCH64_RELATIVE) {
            *slot = (uint64_t)image->base + rela[i].r_addend;
        } else if (type == R_AARCH64_GLOB_DAT || type == R_AARCH64_JUMP_SLOT || type == R_AARCH64_ABS64) {
            const char *name = image->dynstr + syms[sym].st_name;
            void *target = syms[sym].st_shndx != SHN_UNDEF ? image->base + syms[sym].st_value : resolve(name);
            if (!target) {
                fprintf(stderr, "elfload: unresolved import %s\n", name);
                return -1;
            }
            *slot = (uint64_t)target + rela[i].r_addend;
        } else {
            fprintf(stderr, "elfload: unsupported relocation type %u\n", type);
            return -1;
        }
    }
    return 0;
}

int elf_load(const char *path, uintptr_t base, elf_resolver resolve, struct elf_image *image) {
    memset(image, 0, sizeof *image);
    const uint8_t *file = read_file(path);
    if (!file) return perror(path), -1;
    const Elf64_Ehdr *eh = (const Elf64_Ehdr *)file;
    if (memcmp(eh->e_ident, ELFMAG, SELFMAG) || eh->e_machine != EM_AARCH64) {
        fprintf(stderr, "elfload: %s is not an AArch64 ELF\n", path);
        return -1;
    }
    const Elf64_Phdr *ph = (const Elf64_Phdr *)(file + eh->e_phoff);
    size_t span = 0;
    for (int i = 0; i < eh->e_phnum; i++)
        if (ph[i].p_type == PT_LOAD && ph[i].p_vaddr + ph[i].p_memsz > span) span = ph[i].p_vaddr + ph[i].p_memsz;
    span = (span + 0xffff) & ~(size_t)0xffff;
    // RWX keeps the test simple: natively the code runs in place, recompiled it is only data.
    void *map = mmap((void *)base, span, PROT_READ | PROT_WRITE | PROT_EXEC,
                     MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (map != (void *)base) return perror("elfload: mmap"), -1;
    image->base = map, image->span = span, image->file = file;

    const Elf64_Dyn *dyn = NULL;
    for (int i = 0; i < eh->e_phnum; i++) {
        if (ph[i].p_type == PT_LOAD) memcpy(image->base + ph[i].p_vaddr, file + ph[i].p_offset, ph[i].p_filesz);
        if (ph[i].p_type == PT_DYNAMIC) dyn = (const Elf64_Dyn *)(image->base + ph[i].p_vaddr);
    }
    // The symbol count comes from the section headers, which these libraries keep.
    const Elf64_Shdr *sh = (const Elf64_Shdr *)(file + eh->e_shoff);
    for (int i = 0; i < eh->e_shnum; i++)
        if (sh[i].sh_type == SHT_DYNSYM) image->nsyms = sh[i].sh_size / sizeof(Elf64_Sym);

    const Elf64_Rela *rela = NULL, *jmprel = NULL;
    size_t relasz = 0, pltrelsz = 0;
    for (; dyn && dyn->d_tag != DT_NULL; dyn++) {
        uint8_t *at = image->base + dyn->d_un.d_ptr;
        switch (dyn->d_tag) {
        case DT_SYMTAB: image->dynsym = at; break;
        case DT_STRTAB: image->dynstr = (const char *)at; break;
        case DT_RELA: rela = (const Elf64_Rela *)at; break;
        case DT_RELASZ: relasz = dyn->d_un.d_val; break;
        case DT_JMPREL: jmprel = (const Elf64_Rela *)at; break;
        case DT_PLTRELSZ: pltrelsz = dyn->d_un.d_val; break;
        }
    }
    if (relocate(image, rela, relasz / sizeof(Elf64_Rela), resolve) ||
        relocate(image, jmprel, pltrelsz / sizeof(Elf64_Rela), resolve))
        return -1;
    __builtin___clear_cache((char *)image->base, (char *)image->base + span);
    return 0;
}

void *elf_symbol(const struct elf_image *image, const char *name) {
    const Elf64_Sym *syms = image->dynsym;
    for (size_t i = 0; i < image->nsyms; i++)
        if (syms[i].st_shndx != SHN_UNDEF && !strcmp(image->dynstr + syms[i].st_name, name))
            return image->base + syms[i].st_value;
    return NULL;
}
