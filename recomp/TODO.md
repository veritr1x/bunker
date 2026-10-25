# Recomp TODO

Handoff for continuing the ARM64 → x86_64 static recompilation experiments,
mainly from a Windows PC. Read `recomp/README.md` first: it explains every tool
here. This file says where things stand and what to do next.

## Where things stand

- **Branch:** `recomp-x86_64` in this repo, off `main`. Not meant to be merged
  into `main`: nothing here is part of the Bunker build or release.
- **Remill:** our fork [veritr1x/remill](https://github.com/veritr1x/remill),
  branch `bunker` (Remill v6.0.1 plus our commits). `recomp/remill/fetch.sh`
  clones it into `recomp/work/remill-src`. Commit and push Remill changes there,
  not here.
- **Done:**
  - Library survey (`survey.py`) and per-library instruction coverage (`coverage.py`).
  - libFastAES recompiled to x86_64 end to end: 48/48 calls match the ARM64
    original and OpenSSL (`fastaes/`).
  - Remill batch 1: vector FP arithmetic, FMUL by element, element moves, FCSEL,
    STP of Q and indexed STP/STR of FP registers; fixes for lost FP exception
    flags, FPSR.DZC and the test harness writing FPSR into FPCR. All 1,161
    AArch64 differential tests pass.
- **Coverage now** (instructions; SIMD in brackets): `libil2cpp.so` 99.98%
  (99.8%), `libunity.so` 97.93% (85.4%), `libgrpc_csharp_ext.so` 98.72% (85.9%).

## Setting up on Windows

1. Install WSL2 (Ubuntu) and Docker Desktop with the WSL2 backend. Run every
   script from the WSL shell, not PowerShell or cmd.
2. Clone into the WSL filesystem (`~/...`), not `/mnt/c/...`: builds there are
   much faster, and git fails on Windows-mounted folders the same way it does on
   macOS bind mounts (see Gotchas).
3. `git switch recomp-x86_64`, then `recomp/remill/fetch.sh`.
4. Put the original game files in `inputs/` (they are not in git):
   `game-3.7.1.apk` at least. Then `python3 recomp/survey.py --apk inputs/game-3.7.1.apk`
   extracts the libraries into `recomp/work/lib/` (needs the Android NDK; set
   `ANDROID_NDK_HOME`).
5. `recomp/remill/dev.sh image` and `recomp/remill/dev.sh build`. The first
   build compiles the dependencies too and takes a while.

## Important: the differential tests need an ARM64 CPU

`dev.sh test` runs each instruction natively and lifted, then compares the
results. On an x86_64 PC the ARM64 container runs under QEMU emulation. That
should work but is slow, and QEMU's floating-point exception flags are not
guaranteed to match real hardware, so an FPSR mismatch there may be QEMU's fault
and not the semantics'. Treat results from the Mac (Apple Silicon) or another
real ARM64 Linux machine as the reference. Writing semantics, building and
measuring coverage all work fine on x86_64.

## Next tasks

### 1. Remill batch 2: the next most common missing instructions

From `coverage.py report --tag bunker1` (counts are occurrences in the library):

- `libunity.so`: `ld1 {v.s}[i]` single-lane load (3,248), `ushl` vector (2,726),
  `frecps` (2,668), `scvtf` vector (2,468), `ld1r` (2,378), `fcmgt`/`fcmge`
  vector (1,974 / 1,695), `xtn` (1,966), `shl` vector immediate (1,648),
  `fmin` vector (1,569). Run the report for the full list.
- `libil2cpp.so`: `scvtf s, s` (268), `fnmul` (141), `fabd` (65), `ld1r`,
  `fcvtn`/`fcvtl`/`fcvtzu`/`ucvtf` vector, `stlr xzr` (53). Small counts, but
  this is the game's own code, so each one matters.
- `libgrpc_csharp_ext.so`: `adcs` (2,756 across forms), `stxr` (467), `tbl`,
  `mla` by element, `ushr`/`sli`, the AES instructions.

How each one is added (see batch 1 in the fork for worked examples):

1. `python3 recomp/remill/unstub.py <ISEL_NAME>...` removes the generated
   `return false` decoder stubs from `lib/Arch/AArch64/Decode.cpp`.
2. Write the decoder in `lib/Arch/AArch64/Arch.cpp` (operand order must match
   the semantic function's parameters) and the semantics plus `DEF_ISEL` in
   `lib/Arch/AArch64/Semantics/*.cpp`.
3. Add a test file under `tests/AArch64/<CATEGORY>/` and include it in
   `tests/AArch64/Tests.S`. FP tests should use `TEST_INPUTS_FP32_EXCEPT` /
   `TEST_INPUTS_FP64_EXCEPT` (defined in `SIMD/FP_ASIMDSAME_ONLY.S`) so every
   FPSR exception is exercised.
4. `dev.sh run remill/clean_semantics.sh`, `dev.sh build`, `dev.sh test`.
5. Re-measure: `dev.sh run coverage_lift.sh <lib> <tag>`, then
   `python3 recomp/coverage.py report --lib <lib> --tag <tag>`. Update the
   tables in `recomp/README.md` and this file.
6. Commit in the fork, one commit per instruction group, and push `bunker`.

### 2. Run the existing Bunker APK on x86_64 through ARM translation

The practical route for players, and Windows is the right machine for it: the
Android Studio emulator with an API 30+ Google APIs **x86_64** image (these
include ARM translation). Build the APK as usual (`scripts/build.py --apk ...`),
`adb install artifacts/bunker.apk`, and check: the launcher starts, Lunar Tear
starts, the game reaches the title screen and loads in. The parts most likely
to fail under translation are the native patches in
`android/app/src/main/cpp/` (`play_services.c`, `egl_sync.c`, `display_patch.c`).
Record what works and what does not in `recomp/README.md`.

### 3. Offer the Remill bug fixes upstream

The first two commits on the fork's `bunker` branch fix real Remill bugs (FP
operations escaping the exception-flag window; DZC and the FPSR/FPCR mix-up in
the test harness). They could go to `lifting-bits/remill` as a PR. Ask before
opening it: it is public and under the user's account.

### 4. Not started

Whole-library lifting with indirect calls (a table from original addresses to
recompiled functions) has not been started.

## Gotchas

- **Semantics rebuilds:** the build does not notice edits to
  `lib/Arch/AArch64/Semantics/*.cpp`. Run `dev.sh run remill/clean_semantics.sh`
  before `dev.sh build`, or the tests run the old semantics.
- **Test harness assembly is checked in:** `generated/Arch/AArch64/{Save,Restore}State.S`
  are generated from `tests/AArch64/Print{Save,Restore}State.cpp` by
  `dev.sh run remill/regen_state_asm.sh`. `generated/Arch` is gitignored but
  tracked, so stage those files with `git add -f`.
- **Build directory in a Docker volume:** `dev.sh` keeps `build-dev` and ccache
  in the volumes `bunker-remill-build` and `bunker-remill-ccache`, because git
  (used by the sleigh fetch during configure) fails with "does not match index"
  on bind-mounted folders.
- **gtest flags:** the test runner parses its command line with gflags, which
  rejects `--gtest_*`. `test_in_dev.sh` passes `GTEST_FILTER` and `GTEST_BRIEF`
  through the environment instead: `dev.sh test '*FADD*'`.
- **Full test log:** `recomp/work/remill-test.log`. A mismatch reports byte
  offsets into `State` with both values; `dev.sh run remill/state_offsets.sh`
  prints the status-register fields' offsets (`sr.dzc` is at 1155). Add fields
  to its list as needed.
- **`docker run --platform`:** with Docker Desktop's containerd store, passing
  `--platform` can make Docker miss a locally built single-platform image. The
  scripts leave it out.
- **Remill's own images:** `ghcr.io/lifting-bits/remill` is not accessible;
  Docker Hub's `trailofbits/remill` images are old (LLVM 11) and lift exactly
  what v6.0.1 lifts. Use the fork.
- **Line endings:** `.gitattributes` keeps `*.sh` LF. If a script fails with
  `bad interpreter` or `$'\r'`, it was checked out with CRLF.
