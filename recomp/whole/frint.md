# Scalar directed floating-point rounding

The selected IL2CPP cohort has122 currently unsupported FRINTP/M sites in81 trace heads. All are scalar S/D forms: FRINTP59S/15D and FRINTM29S/19D. The implementation adds exactly those four scalar forms. Qualification used a separate scratch build and did not change any selected guest cohort.

The four existing stubs are removed from Decode.cpp and their supported definitions live beside the operand helpers in Arch.cpp. Existing exact extraction masks already identify the four forms. The new FP_ROUND_INT.cpp receives scalar source bits through numeric R32/R64 carriers and writes the scalar destination with upper bits cleared. A single Runtime/Instructions.cpp include exposes its selectors.

The integer-only rounding helper follows the official Arm DDI0602 ID032025 scalar instruction and shared FPRoundInt/FPProcessNaN pseudocode. It uses explicit toward-plus/toward-minus directions independently of FPCR's rounding setting, preserves signed zero and infinity, quiets signaling NaNs with IOC, obeys DN, and flushes subnormals with IDC when FZ is set. Fractional input adds no IXC because exact=FALSE; existing sticky status remains. No native floating-point operation or source-address dereference is used. Scope is the existing baseline FP-enabled profile with exception traps and FEAT_AFP alternate/merging controls disabled. Half, vector, other FRINT operations, privilege/trap/AFP capabilities remain outside the patch.

The primary document SHA is b7baa6869789722df70da60170d999a62810409aaabbb6db1ef729ed68686bdf, from https://documentation-service.arm.com/static/67e40f3398aa3c3b6eea6a85 . Relevant excerpts remain in primary/.

## Executed component evidence

`qualification2/acceptance.json` SHA80501c369b5a887292723f181c3476074968eaf5762f4e7d989288856e6c55ce:

* 65536 records on EACH ARM64/QEMU, native Linux and native Windows, with exact normalized record identity.
* Sixteen actual NDK core functions: four forms with separate/in-place/high-register operands plus four literal instructions independently matched against original IL2CPP bytes.
* All16 FPCR rounding/FZ/DN combinations, two initial sticky FPSR values, both signs of zero/subnormals/fractions/integral boundaries/max finite/infinity/quiet and signaling NaNs, and deterministic random raw input bits.
* Complete before/after800-byte snapshots check all GPR and SIMD registers, SP, NZCV, FPCR and expected sticky FPSR effects, input immutability and output guards before pointer/SP normalization and hashing. Native callee-save registers are restored. Non-flag-setting CSET/ORR records NZCV in the shared core; only the native wrapper uses NZCV system-register instructions.
* 4118 actual initialized-public-decoder checks: all4096 Rd/Rn combinations across the four forms, four literal original words and18 half/vector/reserved/other-rounding/known-neighbor controls. Scalar sources remain numeric register operands; the destination is the whole128-bit vector.
* Each translated host has33 trace heads/one object, zero unsupported traces and zero unresolved direct targets. An ordinary scalar load/store control retains its real memory effect.

The record-only normalized digest is78f62ea097c1851935b966a3e0e817e989b287eb6f84b548bcf70d060cb42169. Each record was locally checked against complete expected state before printing. This is compiler component qualification; it is not original-function, initialization, audio-backend or game-frame success.

## New immutable tools and scope

The fresh source archive is clean accepted Remill10ab6febe9a37125ba17d460be27c4f37a171c8f plus only four changed/new files. A new native source/build and copied dependency tree reside at `/home/user/bunker-recomp/recomp/work/frint-isolated2`; existing source/build/tool paths were never written. Authority remained clean before and after the build.

New frozen pair under work/frint-scalar-preparation2/toolchains/9bff048102b6cb23-aae195eeea5695da:

* Lifter SHA9bff048102b6cb23ab218d6e340ceb0b1183c1cfec8eb9e1ffe2e398fc88e7a1.
* Semantics SHAaae195eeea5695daaa51c76961bb26eca1da113821c3c7b773e157c56fc08bfb.

The snapshot contains actual source hashes, compile/link recipe and15 static decoder libraries, headers, system LLVM pin and compiled State1200/align16 probe. Compiled inspection adds exactly four FRINT selectors/functions and preserves all1358 prior selector bindings and1212 prior function bodies after metadata ID normalization. A separate supplement verifies the actual referenced function attribute sets unchanged. New source bits are never converted to a pointer: only the destination argument uses inttoptr. No guest memory callback or floating arithmetic is introduced. State header bytes remain identical. Actual copied C/C++ dependencies and build configuration511 files are pinned separately.

No global refresh or sparse cohort replacement is performed. Newly exposing a truncated original trace can reveal further instructions; component success alone cannot qualify an unbuilt replacement object.

## Preserved attempts

Preparation1/reference1 passed the same65536 ARM64 records. Isolated1 then failed compilation because operand helpers were private to Arch.cpp while the first proposed definitions were in Decode.cpp. Preparation2 corrects only their placement and retains unchanged semantics. Its native build passes.

The first freeze attempt lacked the tools/bin PATH entry for ninja; its partial tool directory and log remain under the `-partial-freeze1` suffix. The corrected freeze copied the identical completed native pair.

Qualification1 passed4118 decoder cases,65536 ARM64 records and Linux33-head translation, then failed while recording a relative compiler path. Qualification2 changes only that runner lookup to shutil.which and completes both translated hosts. All earlier source, logs, binaries and outputs remain intact; no failure was counted as semantic success.

## Local source promotion

The exact four tested Remill source files were committed locally as`1098caf013cb9806c3c02ef0efd7e577120da109` after independent review and the Game22 aggregate. No existing native build/toolchain or selected cohort was rebuilt or changed.

The repository controller uses `ROOT=HERE.parent.parent` so its support archive follows the actual repository location. This is the only controller change from tested source SHA`d04feb7b2c08d4afafa95d1ecda2d38b1d4ebfaee294c57ded3d82404e4db2e6` to promoted SHA`21b0047019a3f2bb4c0ef52861e5bce2bac0cf08352b6f4a04d23693e4c4e13d`. All other AST nodes and the five core/reference/decoder fixture files are byte-identical; an actual repository-path assertion passed. No broad gate was repeated for this metadata-only portability change.
