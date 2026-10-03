// Minimal imported-symbol rebinding for one already-linked image.
//
// The game is an arm64 (not arm64e) binary using classic dyld binding, so its
// imported C functions are called through pointer tables in __DATA and
// __DATA_CONST. Rewriting a table entry redirects calls from that image only.
// Approach after Facebook's fishhook (BSD licence); written for this project.
#include "rebind.h"

#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach/mach.h>
#include <string.h>

static const struct lt_rebinding *pending;
static size_t pending_count;
static const char *pending_image;

static void write_pointer(void **slot, void *value, int read_only) {
    if (read_only) {
        vm_address_t page = (vm_address_t)slot & ~(vm_address_t)(vm_page_size - 1);
        if (vm_protect(mach_task_self(), page, vm_page_size, 0, VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY) != KERN_SUCCESS) return;
        *slot = value;
        vm_protect(mach_task_self(), page, vm_page_size, 0, VM_PROT_READ);
    } else {
        *slot = value;
    }
}

static void rebind_section(const struct section_64 *section, intptr_t slide, const struct nlist_64 *symbols,
                           const char *strings, const uint32_t *indirect, int read_only) {
    uint32_t *indices = (uint32_t *)indirect + section->reserved1;
    void **slots = (void **)(slide + section->addr);
    for (uint64_t i = 0; i < section->size / sizeof(void *); i++) {
        uint32_t index = indices[i];
        if (index == INDIRECT_SYMBOL_ABS || index == INDIRECT_SYMBOL_LOCAL || index == (INDIRECT_SYMBOL_LOCAL | INDIRECT_SYMBOL_ABS)) continue;
        const char *name = strings + symbols[index].n_un.n_strx;
        if (name[0] != '_') continue;
        for (size_t j = 0; j < pending_count; j++) {
            if (strcmp(name + 1, pending[j].name) != 0 || slots[i] == pending[j].replacement) continue;
            if (pending[j].original && !*pending[j].original) *pending[j].original = slots[i];
            write_pointer(&slots[i], pending[j].replacement, read_only);
        }
    }
}

static void rebind_image(const struct mach_header *raw, intptr_t slide) {
    Dl_info info;
    if (!dladdr(raw, &info) || !info.dli_fname || !strstr(info.dli_fname, pending_image)) return;
    const struct mach_header_64 *header = (const struct mach_header_64 *)raw;
    if (header->magic != MH_MAGIC_64) return;
    const struct segment_command_64 *linkedit = NULL;
    const struct symtab_command *symtab = NULL;
    const struct dysymtab_command *dysymtab = NULL;
    const uint8_t *cursor = (const uint8_t *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        const struct load_command *command = (const struct load_command *)cursor;
        if (command->cmd == LC_SEGMENT_64 && strcmp(((const struct segment_command_64 *)command)->segname, SEG_LINKEDIT) == 0)
            linkedit = (const struct segment_command_64 *)command;
        else if (command->cmd == LC_SYMTAB) symtab = (const struct symtab_command *)command;
        else if (command->cmd == LC_DYSYMTAB) dysymtab = (const struct dysymtab_command *)command;
        cursor += command->cmdsize;
    }
    if (!linkedit || !symtab || !dysymtab || !dysymtab->nindirectsyms) return;
    uintptr_t base = (uintptr_t)slide + linkedit->vmaddr - linkedit->fileoff;
    const struct nlist_64 *symbols = (const struct nlist_64 *)(base + symtab->symoff);
    const char *strings = (const char *)(base + symtab->stroff);
    const uint32_t *indirect = (const uint32_t *)(base + dysymtab->indirectsymoff);
    cursor = (const uint8_t *)(header + 1);
    for (uint32_t i = 0; i < header->ncmds; i++) {
        const struct load_command *command = (const struct load_command *)cursor;
        cursor += command->cmdsize;
        if (command->cmd != LC_SEGMENT_64) continue;
        const struct segment_command_64 *segment = (const struct segment_command_64 *)command;
        int read_only = strcmp(segment->segname, "__DATA_CONST") == 0 || strcmp(segment->segname, "__AUTH_CONST") == 0;
        if (!read_only && strcmp(segment->segname, SEG_DATA) != 0) continue;
        const struct section_64 *sections = (const struct section_64 *)(segment + 1);
        for (uint32_t s = 0; s < segment->nsects; s++) {
            uint32_t type = sections[s].flags & SECTION_TYPE;
            if (type == S_LAZY_SYMBOL_POINTERS || type == S_NON_LAZY_SYMBOL_POINTERS)
                rebind_section(&sections[s], slide, symbols, strings, indirect, read_only);
        }
    }
}

void lt_rebind_image_symbols(const char *image, const struct lt_rebinding *bindings, size_t count) {
    pending = bindings;
    pending_count = count;
    pending_image = image;
    // Called immediately for every image already loaded, then for later ones.
    _dyld_register_func_for_add_image(rebind_image);
}
