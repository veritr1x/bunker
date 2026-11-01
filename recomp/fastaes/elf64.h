// ELF64 wire-format declarations used by the Windows data-image loader.
// Values and layouts follow the ELF specification; no native ELF loader is used.
#pragma once
#include <stdint.h>

typedef struct {
    unsigned char e_ident[16];
    uint16_t e_type, e_machine;
    uint32_t e_version;
    uint64_t e_entry, e_phoff, e_shoff;
    uint32_t e_flags;
    uint16_t e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx;
} Elf64_Ehdr;
typedef struct {
    uint32_t p_type, p_flags;
    uint64_t p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align;
} Elf64_Phdr;
typedef struct {
    uint32_t sh_name, sh_type;
    uint64_t sh_flags, sh_addr, sh_offset, sh_size;
    uint32_t sh_link, sh_info;
    uint64_t sh_addralign, sh_entsize;
} Elf64_Shdr;
typedef struct {
    uint32_t st_name;
    uint8_t st_info, st_other;
    uint16_t st_shndx;
    uint64_t st_value, st_size;
} Elf64_Sym;
typedef struct { uint64_t r_offset, r_info; int64_t r_addend; } Elf64_Rela;
typedef struct {
    int64_t d_tag;
    union { uint64_t d_val, d_ptr; } d_un;
} Elf64_Dyn;

#define ELFMAG "\177ELF"
#define SELFMAG 4
#define EM_AARCH64 183
#define PT_LOAD 1
#define PT_DYNAMIC 2
#define SHT_DYNSYM 11
#define SHN_UNDEF 0
#define SHN_ABS 0xfff1
#define STB_WEAK 2
#define ELF64_ST_BIND(info) ((info) >> 4)
#define DT_NULL 0
#define DT_PLTRELSZ 2
#define DT_STRTAB 5
#define DT_SYMTAB 6
#define DT_RELA 7
#define DT_RELASZ 8
#define DT_JMPREL 23
#define ELF64_R_SYM(info) ((info) >> 32)
#define ELF64_R_TYPE(info) ((info) & 0xffffffff)
