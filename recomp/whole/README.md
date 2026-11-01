# Whole-library ARM64 to native x86_64

`compile.py` reads an AArch64 ELF, discovers trace entries, lifts shards with
the Bunker Remill fork, and compiles LLVM IR to Linux ELF or Windows COFF
objects. The original library supplies data and relocated guest pointers;
`runtime.*` dispatches guest code addresses to linked x86_64 functions.
Native Windows execution does not emulate ARM64 instructions.

FastAES and synthetic integration gates execute. Full Unity/IL2CPP game startup
remains unverified. See [../TODO.md](../TODO.md).

## Dependencies

- WSL/Linux Python 3.11+ with `pyelftools` and `capstone>=5,<6`.
- Bunker Remill fork with the file/multiple-entry/trace-head/snapshot CLI
  extensions, matching `aarch64.bc`, and LLVM/Clang 18 on this machine.
- Android NDK for Android ABI caller fixtures; ARM64 Linux cross-sysroot
  and QEMU for independent ARM64 reference runs.
- MinGW-w64 GCC/G++ for native Windows hosts and executable linking.

Install the tested Python dependencies with
`python -m pip install -r recomp/whole/requirements.txt`.

This machine keeps its Python environment and lifter under
`/home/user/bunker-recomp/recomp/work/`, NDK under
`/home/user/bunker-tools/android-sdk/ndk/27.2.12479018`, and Windows
compilers under `C:\mingw64\bin`. Generated files belong under ignored `work/`.

## Plan and compile

Example from the repository root in WSL (adjust paths to the build checkout):

```sh
PY=~/bunker-recomp/recomp/work/tools/bin/python
LIFT=~/bunker-recomp/recomp/work/remill-src/build-native/bin/lift/remill-lift-18
LIB=~/bunker-recomp/recomp/work/lib/libunity.so
OUT=~/bunker-recomp/recomp/work/whole-unity

$PY recomp/whole/compile.py "$LIB" --out "$OUT" --lift "$LIFT" \
  --base 0x70000000 --target x86_64-w64-windows-gnu --plan-only

$PY recomp/whole/compile.py "$LIB" --out "$OUT" --lift "$LIFT" \
  --base 0x70000000 --target x86_64-w64-windows-gnu --cxx clang++-18 \
  --jobs 4 --shard-size 128 --resume
```

For IL2CPP, use `libil2cpp.so`, a separate output directory and base
`0x80000000`. Windows bases require 64-KiB alignment. Use
`--target x86_64-linux-gnu` for Linux execution.

Strict builds reject unsupported traces. Diagnostic `--allow-unsupported`
builds retain explicit failure paths to locate missing operations at startup;
they are not complete translations.

Outputs include `plan.json` (source/hash/imports/exports/initializers), raw code
bytes, entries, per-shard IR/objects/logs/caches, `manifest.json` and `traces.h`.
Executable sections distinguish code from strings in mixed RX segments. Seeds
come from symbols, unwind records, code relocations, proven jump tables and
statically proven `__cxa_atexit`/`atexit` callback arguments. Callback recovery
checks real GOT/PLT imports and load-base provenance; numeric values that only
resemble code RVAs are rejected. Tiny callbacks can lack both symbols and FDEs.
`--no-callback-recovery` exists for diagnostic baseline comparisons only.
Proved direct calls to real `setjmp`/`_setjmp`/`sigsetjmp` GOT/PLT imports also
seed their executable post-call PCs by default. The `nonlocal_roots` manifest
section retains proofs and unresolved calls; `--no-nonlocal-roots` is its
diagnostic opt-out. This makes continuation code available without implementing
`longjmp` transfer. See [the proof and gates](nonlocal_roots.md).
Ambiguous indirect branches remain reported.

Each build snapshots its lifter and semantics. Resume checks source, target,
compiler/pipeline, known trace boundaries and IR/object hashes. Keep one writer
per output directory. Changed compiler snapshots invalidate incompatible shards.

Optional `--poll-instrument` freezes an LLVM18 cooperative poll instrumenter
and adds State escape points at trace entries and cycle cuts. Link
`cooperative_poll.cpp` when using it. It is disabled for current engine
snapshots. See [the contract and gates](cooperative_poll.md); signal delivery,
provider transition roots and GC integration remain separate work.

## Integration gates

Run `--help` on each driver for paths and platform options:

```sh
$PY recomp/whole/test_lifter.py --lift "$LIFT"
$PY recomp/whole/test_fixture.py --lift "$LIFT" --cc clang-18 --cxx clang++-18
$PY recomp/whole/test_compile_cache.py --library recomp/work/whole-fixture/fixture.so \
  --lift "$LIFT" --cxx clang++-18
$PY recomp/whole/test_fastaes.py --help
$PY recomp/whole/test_semantics.py --help
$PY recomp/whole/test_jump_tables.py --help
$PY recomp/whole/test_callback_roots.py --help
$PY recomp/whole/test_nonlocal_roots.py --help
$PY recomp/whole/test_nonlocal_compile.py --help
```

`test_fixture.py` checks constructors, calls, recursion, relocations, imports,
mixed RX data, absolute symbols and undefined weak symbols. Unknown targets
must abort diagnostically. It passes 100,105 checks on Linux and native Windows.

`test_semantics.py` and `test_fp_*.py` compare translated results/FPSR against
ARM64 references. `--windows` runs a real PE executable through WSL interop.
QEMU generates reference results only; translated Windows code runs natively.
Jump-table tests also reject unsafe patterns.

`build_windows.ps1` links complete FastAES/fixture/semantics COFF outputs with
the Windows data loader and runtime. It rejects unsupported traces:

```powershell
recomp/whole/build_windows.ps1 -BuildDirectory <Windows-objects-directory> `
  -Library <original-ARM64-library> -Program fixture `
  -Cxx C:\mingw64\bin\g++.exe -Cc C:\mingw64\bin\gcc.exe
```

JNI, variadic formatting, file handles, pthread state and Android wire layouts
have dedicated adapters under [../windows](../windows/README.md). Guest
callbacks dispatch through the runtime; never cast guest code pointers to
native Windows callbacks.

## Shared guest memory and exclusive operations

The replacement exclusive protocol keeps a reservation across trace dispatch
within a guest execution. A shared lock and versioned 64-byte granules detect
intervening tracked writes, including ABA and same-value writes. Native atomic
operations implement conditional stores. Import/host entry may conservatively
clear the current execution's reservation. Single and paired operations pass
90,112 ARM64-reference comparisons on each host platform, plus runtime
contention/ABA checks. This is not a full game synchronization validation.

Host providers must use `ReadGuestMemory` to snapshot input and
`WriteGuestMemory` to publish output. `WithGuestMemoryWrite` is for short native
writes only: its non-recursive lock must never span translated callbacks,
nested tracked operations, blocking I/O or waits. `InvalidateGuestMemory`
records allocation lifetime changes. `guest_memory.h` provides bounded string
snapshots without reading beyond NUL or a printf precision limit.

Use private buffers around native libraries and operating-system I/O, then
publish changed guest bytes. Direct external writes, shared-file aliases and
uninstrumented providers do not participate in the protocol. Each provider's
tests and documentation state its current coverage.
