# Unsigned widening add

The original IL2CPP word at8261b670 (RVA261b670) is`2e641047`, `UADDW V7.4S,V2.4S,V4.4H`. It was exposed after the earlier USHLL/USHLL2 candidate recovered four preceding widening shifts; the old diagnostic reports nextPC8261b674. This isolated component does not execute that original function or change any game cohort.

The proposed three-file patch adds the single family decoder in Arch.cpp, removes its old Decode.cpp stub, and extends the existing SIMD_INTEGER.cpp widening helpers. It supports the six unsigned forms8→16/16→32/32→64 with either lower or upper64-bit second-source half. Size3 is reserved and rejected. Signed SADDW, UADDL, USUBW, saturating operations and other families retain their previous behavior.

Both complete source vectors are snapshotted before any destination write, so destination/source aliases and all-same-register forms are supported. The wide first source always supplies128 bits; Q selects only the second, narrow source's lower/upper64 bits. Unsigned64-bit addition followed by the final lane-width cast implements modulo2^16/2^32/2^64, including64-bit wraparound without signed overflow. The full128-bit destination is overwritten; flags and unrelated state remain unchanged. Vector operands use the existing full-vector register transport conventions.

The cached official Arm DDI0602 ID032025 UADDW/UADDW2 section is preserved in primary/uaddw.txt. It specifies unsigned interpretation of both operands, second-source Vpart selection, and low2*esize result bits. Its source PDF SHA is b7baa6869789722df70da60170d999a62810409aaabbb6db1ef729ed68686bdf, from https://documentation-service.arm.com/static/67e40f3398aa3c3b6eea6a85 . Scope assumes the existing AdvSIMD-enabled profile; privilege/feature traps are not expanded.

## Actual qualification

Acceptance `qualification1/acceptance.json` SHA8e5a66baf8c7c8704f3b1ddbb6ddc4977b205afdd421449b5473d7a599a6bd4f records12544 matching full-state records on EACH ARM64/QEMU, native Linux and native Windows. The49 cases cover all six forms with separate operands, destination aliasing either source, shared sources, all-same operands, high registers and ABI callee-save registers, plus the exact original word. Every case runs256 seeds containing zero/max/sign-bit/alternating patterns, wrapping and nonwrapping boundaries, differing source halves and deterministic raw random bits.

Complete800-byte before/after snapshots check all GPR/SIMD registers, SP, NZCV, FPCR and FPSR before pointer/SP normalization and digesting. Sixteen NZCV seeds, all16 existing FPCR rounding/FZ/DN combinations and both sticky FPSR/QC seeds are represented. Input and output guards are checked. Native callee-save state is restored. The same NDK core object is linked into the native ARM64 reference and both lifted hosts; saved raw symbols independently match all49 literal words followed by RET, including original`4710642e`.

The normalized record digest is c4a0056714b5ec82f61503ac26a5b1bd88189d876f8ca8c7d9ae6a39fb32ba42. Each translated host has99 trace heads/one object, zero unsupported traces and zero unresolved direct targets. An ordinary scalar load/store control keeps its real memory effect.

The actual initialized-public-decoder gate passes782 checks: all32 registers in each of three operand positions and all-same aliases across all six variants, one original word, and13 boundaries. Size3/Q0 andQ1 remain rejected; signed/other-widening neighbors remain unsupported; previously supported USHLL/USHLL2, scalar FRINTP and load/store controls remain separate and supported.

## Isolated tools and unchanged semantics

Source baseline is clean Remill1098caf013cb9806c3c02ef0efd7e577120da109. A new source/build and copied dependencies live at `/home/user/bunker-recomp/recomp/work/uaddw-isolated1`. Authority, old native builds, existing tools and game cohorts were not modified.

New frozen pair under work/uaddw-preparation1/toolchains/cd9a90b4a41eb74a-e7849513b29db93e:

* Lifter SHAcd9a90b4a41eb74afc89676860d8a8d73196f38cfa8b26e835c77d7ab6648492.
* Semantics SHAe7849513b29db93eb59326e3820323ce729345e51f8e7793d807f25acba9ece3.

Compiled proof0281690441c162995a91c67b1e76622e8befc0e3a8fd4196021197c2e947d8ca adds exactly six selectors/functions, preserving all1362 existing selector bindings and1216 prior bodies after metadata ID normalization. The supplement separately verifies referenced function attribute sets unchanged, actual NDK raw words and record identity, and511 copied dependency/configuration files. State header bytes remain identical and the actual compiled layout remains1200/align16. The new functions access only their three vector-register operands, call no guest memory helper, contain no floating arithmetic, and return the unchanged memory token.

A pre-build preparation guard caught selection of the wrong helper file; unused partial copies and its log remain preserved. The actual isolated native build and first complete functional gate both pass. This is a compiler component result, not an original-head repair, initialization return, collection/retention, game frame or playable-game claim. No global refresh is proposed.

## Local source promotion

The exact three tested Remill source files were committed locally as`22466cfdb061b6851bccf611950e67862eaf7d45` after independent review and the Game22 aggregate. No existing native build/toolchain or selected cohort was rebuilt or changed.

The repository controller uses `ROOT=HERE.parent.parent` so its support archive follows the actual repository location. This is the only controller change from tested source SHA`cd5a022dde32314e581476a030d339b545f9173b354cdcac24d901edcdd91720` to promoted SHA`5603d082a8590c102bddcfb0fd87cc1827623475add3d600a384b3680229eaab`. All other AST nodes and the five core/reference/decoder fixture files are byte-identical; an actual repository-path assertion passed. No broad gate was repeated for this metadata-only portability change.
