# Static recompilation experiments (ARM64 → x86_64)

Feasibility tests for recompiling the game's ARM64 libraries to x86_64. Nothing
here is part of the Bunker build.

## Survey

`survey.py` extracts `lib/arm64-v8a/*.so` from the game APK and counts what a
recompiler has to handle in each library: instructions, indirect branches,
SIMD, atomics, imports, relocations and unwind tables.

    python3 recomp/survey.py --apk inputs/game-3.7.1.apk

It needs the Android NDK (`ANDROID_NDK_HOME`, or the default SDK location) and
writes `recomp/work/survey.json`.

## Instruction coverage

`coverage.py` groups a library's instructions into forms (mnemonic plus operand
shape), lifts one sample of each on its own (`insn; ret`) and reports how much of
the library a Remill build can lift, weighted by how often each form occurs.

    recomp/coverage.sh bunker-remill6 remill6 libunity.so libil2cpp.so

`recomp/remill/Dockerfile` builds Remill v6.0.1 with LLVM 22 for the host's
architecture (run `recomp/remill/fetch.sh` first). The older image used
by `fastaes/` (Remill on LLVM 11) gives the same results.

Results with Remill v6.0.1 (branches and calls are not counted):

| Library | Instructions lifted | SIMD lifted | Unsupported forms |
|---|---|---|---|
| `libil2cpp.so` | 99.69% of 9.67 M | 90.5% of 253 k | 129 of 941 |
| `libunity.so` | 92.16% of 2.96 M | 41.1% of 371 k | 393 of 1,442 |
| `libgrpc_csharp_ext.so` | 98.46% of 395 k | 77.1% of 11 k | 125 of 826 |

Across all of them, 463 forms (154 mnemonics) are missing. The biggest groups:
vector floating point (`fmul`, `fadd`, `fsub` on `.4s`/`.2s`, by element too),
lane moves and `dup`, `stp`/`str` of Q and pre-indexed D registers (register
saves in nearly every function that uses SIMD), `fcsel`, byte and pair
exclusives (`ldaxrb`, `stxrb`, `ldxp`, `clrex`), `adcs`, and the AES/SHA
instructions. Remill's AArch64 semantics only define scalar `FMUL`/`FADD`.

## Extending Remill

Our changes to Remill live in the fork
[veritr1x/remill](https://github.com/veritr1x/remill), on the `bunker` branch
(Remill v6.0.1 plus our commits). `recomp/remill/fetch.sh` clones it into
`recomp/work/remill-src`; commit and push changes there, to the fork.

    recomp/remill/dev.sh image      # once
    recomp/remill/dev.sh build      # incremental; first run builds the dependencies
    recomp/remill/dev.sh test       # Remill's AArch64 differential tests: native vs lifted
    recomp/remill/dev.sh run coverage_lift.sh libunity.so bunker1   # coverage with this build

The tests need an ARM64 host (this Mac, or an ARM64 Linux machine): each test
runs the instruction natively and lifted, then compares registers, flags and
memory. The semantics build step does not notice edits to `Semantics/*.cpp`;
run `dev.sh run remill/clean_semantics.sh` before `build` after changing them.

Batch 1 (all 1,161 tests pass): vector `fadd`/`fsub`/`fmul`/`fdiv`/`faddp`,
`fmul` by element, element `mov`/`dup`, `fcsel`, `stp` of Q and indexed `stp`/`str`
of FP registers. It also fixes three existing problems: FP operations moved out
of the exception-flag window (flags lost), FPSR.DZC never tracked, and the test
harness writing FPSR into FPCR.

| Library | Remill v6.0.1 | With batch 1 | SIMD, v6.0.1 → batch 1 |
|---|---|---|---|
| `libil2cpp.so` | 99.69% | 99.98% | 90.5% → 99.8% |
| `libunity.so` | 92.16% | 97.93% | 41.1% → 85.4% |
| `libgrpc_csharp_ext.so` | 98.46% | 98.72% | 77.1% → 85.9% |

## libFastAES end to end

The smallest real library, recompiled with [Remill](https://github.com/lifting-bits/remill)
and checked against the original:

1. `lift.sh` lifts `AES_CBC_encrypt` and `AES_CBC_decrypt` to LLVM IR.
2. `build_ref.sh` loads the original library in an ARM64 Linux container with a
   minimal ELF loader (`elfload.c`) and runs the test matrix (`cases.h`) natively.
3. `build_recomp.sh` compiles the IR for x86_64, links it with the runtime
   (`recomp_x86.cpp`: Remill intrinsics, import bridges, register setup) and runs
   the same matrix in an x86_64 container.
4. `check.py` compares the two outputs call by call, and both with OpenSSL.

```
recomp/survey.py --apk inputs/game-3.7.1.apk --lib libFastAES.so   # extracts the library
recomp/fastaes/run.sh all
python3 recomp/fastaes/check.py
```

Needs Docker. On Windows run the shell scripts from WSL2 (or Git Bash) with
Docker Desktop: the x86_64 image runs natively there and the ARM64 reference
image runs under emulation.

### Library signatures (from the disassembly)

    uint32_t AES_CBC_encrypt(uint8_t *out, void *unused, const uint8_t *in, uint32_t len,
                             const uint8_t *key, uint32_t key_len, const uint8_t *iv, uint8_t padding);
    uint32_t AES_CBC_decrypt(uint8_t *out, const uint8_t *in, uint32_t len,
                             const uint8_t *key, uint32_t key_len, const uint8_t *iv, uint8_t padding);

`key_len` is in bytes (16, 24 or 32). `padding` 2 is PKCS#7; otherwise only whole
blocks are processed. Both return the output length.

### Known gaps

- This Remill build (LLVM 11, the newest image on Docker Hub) cannot lift
  `LD4`/`ST4`. libFastAES uses them only in a key copy for keys over 63 bytes,
  which the tests do not reach, so that path stops with `unliftable instruction`.
- The runtime only bridges the five imports libFastAES uses, and an indirect call
  to any other address stops with an error. Larger libraries need a table of all
  lifted functions for `BLR`/`BR` targets and bridges for every import.
