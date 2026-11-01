# Native Windows recompilation: status and remaining work

The target is a standalone Windows x86_64 executable running the original
game's translated native libraries. Work is on `recomp-x86_64`; it is not yet
part of the normal Bunker release. The game does not boot or render yet.

## Current checkout and tools

- Windows source: `C:\GitRepos\bunker`. The replaced checkout is preserved at
  `C:\GitRepos\bunker-backup-before-replace`.
- Remill fork: `recomp/work/remill-src`, branch `bunker`, remote
  `veritr1x/remill`. This is a separate Git repository, ignored by Bunker.
  Preserve Remill changes there as well as Bunker changes here.
- WSL build mirror: `/home/sattam/bunker-recomp`. The older
  `/home/sattam/bunker` contains unrelated Archive edits; leave those alone.
- Working build uses native WSL LLVM 18, Python 3.12, pyelftools and Capstone 5.
  Native Windows host code uses MinGW GCC 15.2. Docker Desktop is running,
  but the LLVM 22 Docker development image has not completed building.
- Original APK, extracted libraries, reference tools, reports, generated
  objects and executables remain in ignored work/input directories.

## Completed gates (November 1, 2026)

- Whole-library ELF planning, relocation-backed function pointers, translated
  address dispatch, recursive/direct/indirect/tail calls, constructors and
  checked imports. The integration fixture passes **100,105 checks** on both
  Linux x86_64 and native Windows, including absolute/undefined-weak symbols.
- Parallel, resumable Windows COFF translation with hash-verified caches and
  immutable lifter/semantics snapshots. Unknown targets and unliftable
  instructions fail explicitly.
- Guard-proven jump-table recovery finds 5,238 Unity and 13,473 IL2CPP case
  entries, including width-equivalent masked indices,
  bounded loop closure and joined guard paths.
  Byte/halfword/signed-word, masked-loop and joined layouts pass 9,984
  ARM64-reference checks per platform. Ambiguous patterns remain unresolved.
- Real `libFastAES.so` executes as native Windows x86_64 code: all 48 calls
  match the original ARM64 reference and OpenSSL.
- Real `libmain.so` translated `JNI_OnLoad` registers its original loader
  methods. Its load/unload path works with an explicitly synthetic Unity
  module. This does not establish that real Unity initializes.
- Windows JNI, module loading, mounted files, Android context metadata,
  logging/formatting, scalar ABI, libc and pthread providers have direct and
  NDK-translated caller tests. See [windows/README.md](windows/README.md)
  for supported behavior and remaining boundaries.
- Remill additions cover ADC/ADCS, lane/replicate/structure loads, table
  lookups, release stores, shifts/narrowing/permutations and many scalar/vector
  FP comparisons, conversions and arithmetic operations. FP result bits and
  FPSR are checked against ARM64 QEMU across rounding/FZ/DN modes, boundary
  values and deterministic random inputs. Physical ARM64 validation remains
  useful, especially for floating point.

Latest three-library instruction-form audit with LLVM 18 / Remill `09f7d4d`
(`windows-exclusive`):

| Library | Supported forms | Unsupported occurrences | Weighted liftability |
|---|---:|---:|---:|
| `libunity.so` | 1,262 / 1,442 | 9,005 | 99.6958% |
| `libil2cpp.so` | 917 / 941 | 177 | 99.9982% |
| `libgrpc_csharp_ext.so` | 769 / 826 | 888 | 99.7750% |

These sample one encoding per operand form and exclude control flow; they do
not establish whole-program correctness or execution coverage. The first
Unity Windows translation completed with 58,850
traces in 463 objects, 2,419 unsupported traces and zero unresolved direct
targets. The pair-enabled snapshot has 58,855 traces and 1,860 unsupported
traces. The masked-switch snapshot has 59,552 traces / 1,889 unsupported, and
its native Windows executable completes constructors 1–128. Constructor 129
passed the added `getpagesize` adapter, then reached a joined-guard switch
whose recovery now passes focused tests; its rebuilt executable is pending.
The earlier store/pair/masked-switch blockers at constructors 53, 71 and 95
are cleared. JNI_OnLoad has not run. The initial IL2CPP translation completed
with 393,781 traces in 3,079 objects, 192 unsupported traces and zero unresolved
direct targets. Exploratory objects retain explicit failure paths for
unsupported instructions.

## Active work

1. Build complete Unity and IL2CPP Windows object sets; inspect unsupported
   traces and unresolved targets. Unity has 417 initializers/344 imports;
   IL2CPP has nine initializers/280 imports.
2. Execute every real Unity initializer and its `JNI_OnLoad` with Windows
   providers. Implement concrete missing behavior with tests. Never skip
   initializers or turn unknown imports into successful no-ops.
3. Close instruction gaps reached by startup, then remaining reciprocal
   estimates, SIMD stores/shifts/permutations, FP rounding and crypto groups.
   Coordinate shared Remill builds; engine builds use immutable snapshots.
4. Audit actual imports against available providers, then implement
   startup-critical libc/resource gaps using translated NDK caller tests.

## Remaining milestones

- Real Unity/IL2CPP startup and the Java service/native lifecycle catalog
  required by this APK. JNI support is an explicit catalog, not a Java interpreter.
- IL2CPP GC suspension/signals and needed Bionic/ELF TLS. Nonzero
  `pthread_kill`, `pthread_sigmask` and `pthread_atfork` currently return
  `ENOSYS`; GC signal handling is not implemented.
  [The binary/ABI evidence and required gates](windows/GC-SUSPENSION.md) are
  preserved for the implementation; both stop and resume acknowledgments are
  needed by this collector's default retry mode.
- Finish provider memory integration and exercise paired exclusives in real
  Unity startup. The replacement single/pair reservation protocol passes 90,112
  instruction comparisons per platform plus 97 runtime checks and five
  rejection checks per platform.
  Host providers must participate in tracked reads/writes and allocation
  lifetime invalidation; untracked native/external writes remain a boundary.
- A Windows window, actual EGL/GLES-compatible rendering, surface lifecycle,
  frame scheduling, input and audio. None is verified yet.
- Real APK/data/decompression paths and Bunker backend/launcher services,
  including required networking and Android service behavior.
- Reach title screen, load a save, exercise gameplay/render/audio/input, then
  package a reproducible Windows build consuming user-supplied game assets.
- Preserve local checkpoints in both Git repositories after review. No remote
  push or public upstream PR has been made during this continuation.

## Reproduction and cautions

[whole/README.md](whole/README.md) describes the current compiler and gates.
[README.md](README.md) retains the older Docker/reference experiments.
Use a WSL filesystem for large builds; source can be read from Windows.

The fork now tracks included semantics sources as CMake dependencies. Rebuild
Remill before starting a new translation snapshot after compiler edits.
`--resume` reuses compatible, hash-verified output; keep one writer per output
directory. `--allow-unsupported` is diagnostic, never evidence of a complete
translated library.
