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
- WSL build mirror: `/home/user/bunker-recomp`. The older
  `/home/user/bunker` contains unrelated Archive edits; leave those alone.
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
- Real Unity now completes all 417 constructors, returns JNI 1.6 with all 42
  native registrations checked against ELF/DEX, and exits cleanly through
  `JNI_OnUnload` and its actual finalizers. The separate `initJni(Context)`
  diagnostic now returns cleanly with zero original JNI exception events,
  using checked Java strings, launch intents and the original APK boot.config.
  The bounded UnityMain surface gate also completes actual created/changed/
  detached native calls, observing two fromSurface, two acquire and four release
  calls against the same actual HWND-backed token before close. The separate
  bounded first-frame diagnostic now receives actual HWND focus, returns from
  nativeResume and enters nativeRender. Reached PackageManager and Intent
  services now have checked implementations. The latest frame attempt stops
  earlier because Windows has no default audio output (`E_NOTFOUND`); no frame
  has completed or rendered. A read-only native
  volume observer supplies resume's cached initial music/mute state without an
  invented initial native callback. The full Java/game lifecycle remains open.
- Real IL2CPP completes all nine constructors and both finalizers. Its actual
  parameterless GC signal-initialization routine also passes, installing the
  evidenced actions and acknowledgment semaphore. A validated one-shard overlay
  fixes old pair-exclusive instructions; this remains a mixed diagnostic
  snapshot with 189 unsupported traces. No collection or il2cpp_init has run.
  See [the exact lineage and boundary](windows/il2cpp_bootstrap.md).
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
- FP32/FP64 scalar/vector reciprocal and reciprocal-square-root estimates now
  match 3,354,880 ARM64 reference records on each host, including every lookup
  bucket boundary, FZ/DN/rounding modes and cumulative FPSR. Existing engine
  objects retain their earlier frozen semantics until refreshed.
  See [the exact estimate gate](whole/fp_estimates.md).
- Immediate signed/unsigned SIMD right shifts match 245,760 ARM64 reference
  records on each host, covering every legal shift amount, overlap, upper
  clearing and unchanged flags. See [the shift gate](whole/right_shifts.md).
- SIMD TRN1/TRN2 transposes match 17,920 ARM64 reference records on each host,
  including all allocated arrangements and source/destination overlaps.
  See [the transpose gate](whole/transpose.md).
- Proved direct setjmp import calls now seed executable post-call continuations
  in the compiler: 49 roots in Unity and one in IL2CPP. Native dispatch checks,
  normal context-save tests and whole-compiler regressions pass on both hosts.
  This does not implement longjmp transfer or refresh existing engine objects.
  See [continuation proofs and boundaries](whole/nonlocal_roots.md).

Latest three-library instruction-form audit with LLVM 18 / Remill source `c535b75`
(`windows-estimate-shifts`, November 2):

| Library | Supported forms | Unsupported occurrences | Weighted liftability |
|---|---:|---:|---:|
| `libunity.so` | 1,280 / 1,442 | 5,579 | 99.8115% |
| `libil2cpp.so` | 918 / 941 | 176 | 99.9982% |
| `libgrpc_csharp_ext.so` | 776 / 826 | 666 | 99.8313% |

Compared with `windows-st1`, exactly the estimate/right-shift forms change:
3,031 unsupported occurrences are removed and no previously supported forms
are lost. The combined remaining count is 6,421. Hashes and per-form evidence
are recorded in ignored `work/coverage-windows-estimate-shifts.json`.

These sample one encoding per operand form and exclude control flow; they do
not establish whole-program correctness or execution coverage. The first
Unity Windows translation completed with 58,850 traces. The current callback/
ST1 snapshot has 59,561 traces in 469 objects and 1,774 unsupported traces.
The refreshed estimate/shift/TRN snapshot has 59,610 traces in 469 objects,
1,345 unsupported traces and zero unresolved direct targets. Its constructor,
JNI, initJni and paused surface/shutdown gates pass natively. Original entries
are retained and all 49 new entries are proved continuations; see
[the frozen lineage and exact execution boundary](windows/unity_snapshot_native2.md).
The optional `initJni` diagnostic retains exception history so clearing a Java
exception cannot turn a missing-service path into success. Static callback
root recovery finds 112 Unity callback entries, including three otherwise
unseeded tiny destructors; this clears the observed finalization failure.
The initial IL2CPP translation completed
with 393,781 traces in 3,079 objects, 192 unsupported traces and zero unresolved
direct targets. Exploratory objects retain explicit failure paths for
unsupported instructions.

## Active work

1. Integrate the complete initial IL2CPP object set and refresh its translation
   snapshot with current semantics/root recovery when startup requires it.
   Inspect reached unsupported traces and unresolved targets. Unity has 417
   initializers/344 imports; IL2CPP has nine initializers/280 imports.
2. Preserve the passing actual `initJni(Context)`/APK asset/surface handoff paths
   and continue the bounded focus/resume/frame/pause/done UnityMain flow after
   the machine has a real default audio output again. Connect the actual
   application ClassLoader/IL2CPP module path and audited internal file/cache
   services in parallel.
   Keep the passing 417-constructor/JNI/shutdown gate. Never turn unknown
   imports or unsupported Java effects into successful no-ops.
3. Close instruction gaps reached by startup, then remaining SIMD
   stores/shifts/permutations, FP rounding and crypto groups.
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
  Opt-in compiler/runtime cooperative polling passes 27,349 checks/260 pauses
  on each host, including optimized register roots and irregular CFG cycles.
  [Its contract](whole/cooperative_poll.md) leaves provider transition roots
  and interruptible waits explicit. Signal-frame byte gates also pass;
  production integration and collector correctness remain unverified. See
  [the frame contract](whole/signal_frame.md).
  [A bounded combined gate](windows/signal_delivery.md) passes 16 same-worker
  stop/restart cycles on both hosts with NDK handlers and actual guest-stack
  contexts. The game's collector handlers remain a separate required gate.
- Finish provider memory integration and exercise paired exclusives in real
  Unity startup. The replacement single/pair reservation protocol passes 90,112
  instruction comparisons per platform plus 97 runtime checks and five
  rejection checks per platform.
  Host providers must participate in tracked reads/writes and allocation
  lifetime invalidation; untracked native/external writes remain a boundary.
- Real Windows HWND/Surface ownership passes 291 NDK/host checks. The checked
  EGL bridge passes 49 checks, including real window/pbuffer draws, readback,
  swap, tracked outputs and resource lifetimes. The actual Unity surface gate
  now passes temporary crash-action setup, a real saved Bionic context, and
  observed native window handoff/detach, all with clean shutdown. Rendering
  remains a separate gate. Default-size RGBA/RGBX format support passes 391
  additional native draw/lifetime/concurrency checks; RGB565 is unsupported.
- Pinned Vulkan ANGLE now passes GLES3.2/AEP, shader, draw/compute and all 28
  ASTC formats (239 samples/61,184 bytes), including correct sRGB behavior.
  The typed query resolver passes 976 checks for six getter signatures and 133
  enum widths. A separate native Vulkan scaling variant now passes fixed-size
  buffer negotiation, physical/logical resize and present-mode checks; the
  original ANGLE bundle is preserved. Rendering/client/mapped GL APIs, Unity's
  full surface/resume/frame lifecycle, input and audio remain unverified.
- Real APK/data/decompression paths and Bunker backend/launcher services,
  including required networking and Android service behavior.
  The native APK reader passes 69 independent checks on both hosts and reads
  the actual 149-byte boot.config exactly; checked Java stream/Scanner wiring
  now clears the actual native initJni gate.
  See [the reader contract](windows/apk_assets.md).
- Normal setjmp context saving is implemented and used by the real surface
  gate with an owned mmap lifetime and inherited worker mask. Longjmp transfer
  remains fatal: it needs rooted continuation PCs and a proven unwind/status
  route compatible with lifted LLVM contracts. See
  [the exact wire/transfer boundary](windows/nonlocal_jmp.md).
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
