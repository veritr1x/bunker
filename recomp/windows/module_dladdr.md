# Translated ELF address metadata and Android libdl

`ModuleRegistry::Address` implements the Android LP64 `dladdr` wire layout:
four 64-bit pointers at offsets 0, 8, 16 and 24. An active translated module
owns an address only inside one of its actual `PT_LOAD.p_memsz` half-open
intervals. Rounded reservations, segment holes and the exclusive image end
are not ownership. AArch64 top-byte tags are removed for module membership;
the original tagged argument remains the symbol lookup input, following the
pinned Android 13 linker implementation.

Known ownership returns 1 and publishes exactly 32 bytes through the shared
guest-memory write protocol. The filename and optional symbol name refer to
registry-owned immutable strings; they remain valid until registry destruction,
including after the final close. The registered filename is explicit, normally
a canonical guest path with `/`, rather than an inferred native PE pathname.
Address lookup includes defined local symbols, excludes TLS and zero-size
symbols, and requires containment in a symbol's actual size. It does not choose
the nearest symbol. SysV uses dynsym index order; GNU uses bucket/chain order.
A matching IFUNC is unsupported because executing an ARM resolver natively is
not valid. Unknown ownership returns 0 without accessing the output, changing
errno, or consuming/overwriting dlerror. Active modules without address metadata
are a named incomplete-catalog boundary rather than a false unknown result.

`DescribeModuleElf(file, byte_length, load_bias, filename)` copies metadata from
ELF64 little-endian AArch64 ET_DYN/ET_EXEC bytes. The byte length must be the
actual source-file size, never the loader's rounded mapped span. It validates
program, dynamic, string, symbol, version and hash table bounds and arithmetic;
the supported catalog requires SysV or GNU dynamic hashing. Base is the load
bias plus the lowest page-rounded load VMA; segment membership remains exact.
Metadata retains no borrowed pointer into the source bytes. The factory does
not map the image, run constructors or discover a native OS module. Ambiguous
overlapping registered load intervals are rejected. Users must quiesce registry
imports and metadata-pointer users before registry destruction.

The default `Module::ExportPolicy::DeclaredAddresses` retains the existing
explicit export map, including a valid declared address zero. The optional
`BionicRawSymbols` policy still uses that map as the allowed-name catalog but
resolves eligible defined GLOBAL/WEAK raw dynamic symbols using Android's
`load_bias + st_value`, including SHN_ABS. Qualified exports must have ordinary
binding and no unresolved default-version ambiguity. Like Bionic's
`is_symbol_global_and_defined`, this lookup does not add a visibility filter.
Ordinary dlsym accepts
any non-hidden version, including Unity's actual version index 2. Hidden
candidates are skipped before default-candidate ambiguity is checked; a name
with only hidden candidates is ordinary missing and sets dlerror. Explicit
named-version lookup is not provided; TLS, IFUNC and multiple unhidden default
candidates remain explicit boundaries. `elf_symbol` remains
the legacy raw integrity lookup.
The root-owned `elf_load_bionic` opt-in applies the same Android SHN_ABS bias
during actual relocations; default `elf_load` retains its existing behavior.
The old four libdl marker addresses and callable types are preserved. `dladdr`
is appended at offset 32. Its import and the newly fallible dlsym import have
exception fences which diagnose and abort before returning through lifted LLVM.

The observed original IL2CPP `end` symbol has raw value `0x7cb1e78`, size zero,
and SHN_ABS. Android resolution returns `0x87cb1e78`; that is exactly the last
PT_LOAD's exclusive end. Both values correctly yield `dladdr == 0`. No rebasing
is performed to manufacture ownership. Original absolute GOT slots at offsets
`0x72aeb08` and `0x73f9770` must hold `0x87cb1e78` and `0x85408660` respectively
under the opt-in Android relocation profile.

The focused gate builds real NDK SysV and GNU ELF fixtures and an NDK direct /
volatile-function-pointer caller. That exact caller object and those exact ELF
files also run under QEMU against a genuine dynamically linked ARM64 glibc
`dladdr`. The NDK errno accessor is explicitly forwarded to the reference
process's real glibc TLS errno. Common function/data interior ownership, names,
relative symbol addresses, unknown output preservation and errno are compared
record for record. This is not the NDK static libdl stub. Bionic-specific tag,
local-symbol ordering, absolute resolution and exact-load-boundary behavior use
the separately pinned Android 13 linker source and explicit component checks;
glibc is not claimed as their oracle.

The host tests exercise actual translated calls on Windows and Linux, output
canaries, stable copied metadata, guest exclusive reservations, concurrent
queries, recursive constructor/finalizer queries, holes and segment endpoints,
malformed bounds, and named unsupported imports. They check real legacy versus
Android relocations for ABS64 with addend 7, GLOB_DAT, ordinary symbols and
RELATIVE. Original Unity and IL2CPP metadata are parsed, and both actual IL2CPP
absolute GOT slots are checked in a data-only mapped image. No original
constructor, initializer, collector or frame is executed by this gate. The
unchanged ModuleRegistry regression also runs on both hosts. Separate game
source gates qualify default/enabled compilation and capability refusal; these
are not a native game run or successful initialization claim.

Evidence is preserved under `work/module-dladdr*` and the static source gate.
The actual Windows subprocess status is captured natively as 3 with UCRT abort
reporting disabled by the fixture; Linux status is SIGABRT (-6). No fast-fail
code is inferred from a truncated interop status. Static source gate 6 passed
default and enabled syntax compilation, rejected the missing cooperative-cohort
build, and preserved unavailable-profile refusal and PowerShell parsing.

Final candidate 6 passed 843 focused checks, 130 actual translated NDK calls,
four named installed-import abort boundaries and the unchanged 22-check
ModuleRegistry regression on each host. For each hash style, all ten dladdr
records and the ordinary-version-selection record matched the actual dynamic
ARM64 reference on both translated hosts. This is final qualification of the
skip-hidden/default-selection correction; candidate 5 is preserved separately.

The first focused candidate passed. Candidate 2 preserved a fixture failure:
its malformed-bound assertion changed an unused PT_PHDR field instead of a
PT_LOAD field. The corrected fixture locates the actual load program header
before corrupting its bounds; no provider change was made for that assertion.
Candidate 3 caught the provisional policy's overly strict rejection of Unity's
real unhidden version 2. The policy now follows Android's ordinary-dlsym
`vi == nullptr` rule rather than rejecting all version indices above 1. All
earlier candidates are retained and are not presented as final qualification.
The independent source review also removed an extra visibility filter absent
from Bionic; real hash-eligible dynsym entries modified only to STV_HIDDEN and
STV_INTERNAL exercise that correction without executing modified code.
Candidate 5 passed its then-current tests but is not the final version-policy
qualification: review found its rejection of any hidden candidate was too
strict. The final fixture builds actual `fixture_versioned@V1` (hidden) and
`fixture_versioned@@V2` (default) with an NDK version script for both hash
styles. Ordinary dlsym must select the actual V2 helper address; the dynamic
ARM64 glibc reference independently checks that pointer equality. A hidden-only
name must be missing. The named negative boundary uses two unhidden defaults,
not a valid hidden version. This is ordinary dlsym selection, not dlvsym.
