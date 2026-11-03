#pragma once
#include <cstddef>
#include <cstdint>
#include "module_registry.h"
namespace bunker::windows {
// Original ELF file bytes/byte length, NOT a mapped/rounded image span. Caller
// supplies the verified actual load bias and explicit registered ELF pathname.
// Owns all returned metadata/strings. AArch64 ELF64 LE ET_DYN/ET_EXEC only.
// Base is bias+4K-floor(min PT_LOAD vaddr); span covers those load segments.
ModuleAddressImage DescribeModuleElf(const uint8_t *file,size_t length,
                                    addr_t load_bias,std::string filename);
}
