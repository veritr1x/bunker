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
