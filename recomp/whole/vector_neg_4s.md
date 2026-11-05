# Bounded integer NEG.4S extension

The next original failure reported PC `0x7065185c`. The preceding word at `0x70651858` is `0x6ea0ba31`, `NEG V17.4S,V17.4S`. This extends the integer two-lane work to four 32-bit lanes; it does not introduce floating-point negation or saturating SQNEG.

`integer_neg4s_source.py` applies two checked changes to an isolated copy of the accepted NEG.2S sources. The decoder retains size=2, selecting a 64-bit source for Q=0 and 128-bit source for Q=1. A new `IntegerNeg4S` captures all four source lanes before writing unsigned zero-minus-lane modulo 2^32 into the full 128-bit destination. Source/destination aliasing is valid. Unlike 2S, upper lanes contain their own negated results. NZCV, FPCR and FPSR are unchanged; other sizes and scalar SIMD NEG remain outside the extension.

`build_integer_neg4s_toolchain.py --execute` records the isolated recipe: rebuild Arch.cpp and Instructions semantics with two workers, borrowing Decode, Lift, guest-call lowering, extraction, passes and other libraries unchanged. Accepted directories are immutable; use fresh isolated locations for reproduction. Build receipt `work/integer-neg4s-preparation1/build1/acceptance.json` SHA256 `f8903174135fe6cc9b86b6222ef0d790cd2bfcaa59338393030e2caa0b1209de` establishes all 1269 old semantic operations and 1430 selectors preserved (attribute IDs resolved and only inline-assembly source coordinates excluded), plus one new semantic function/selector.

The frozen directory is `work/integer-neg4s-preparation1/toolchains/d4f5365f2a75d3f0-dfe9c12f5b2e56d1`. Lifter SHA256 is `d4f5365f2a75d3f00938fbedcb6bb7f3a1c24bb60f79c12f0847c775f0303880`; semantics SHA256 is `dfe9c12f5b2e56d1aef735727deb55e47ef22e603da133d62f6f1c042dc317ad`.

## Kernel qualification and limits

`test_vector_neg_4s.py` passed `work/vector-neg4s-qualification1/acceptance.json`, SHA256 `5c0f682804cf16640dc4751f71ef8b5ba3d4d2f9f42d79299bad57d50d73a627`. Actual static NDK/Bionic ARM, raw Windows and exact polled Windows kernel objects each produced 8704 identical records. One actual NDK object is shared between reference and translated execution, and the original instruction bytes are checked against the pinned Unity ELF.

Four kernels cover actual V17-to-V17 and distinct V5-to-V3 NEG.4S, plus the two prior NEG.2S register shapes as a regression. The 272 four-lane edge/random vectors include INT_MIN in every lane; distinct/in-place buffers and four architectural-status seeds complete the matrix. An independent unsigned 32 model verifies every lane, full 128-bit 4S output and retained 2S upper 64 clearing. All input/output guards, all nonoutput State1200 bytes and opaque Memory64 contents/identity are checked, with unchanged status and saved registers. No FP normal-domain filter or output normalization is used.

This is **instruction-kernel qualification, not an execution test of the 296-byte recursive Unity function**. Its instruction lowering, guarded calls and 127 unchanged neighbors are separate static proofs; actual original integration remains separate. Runtime flags/other operands were not logged and are not inferred. No broader instruction arrangement, full game or first-frame claim is made.
