# Original frame-rounding function repair

The original run reached an unliftable instruction reported at `0x70167c1c`. Original FDE `0x70167bbc..0x70167c3c` contains `FMINNM S0,S0,S3` at `0x70167c18`; the old unsupported path reports the following PC. The selected shard 31 repair uses the existing qualified numeric min/max toolchain. It changes only this function; the other 127 raw/polled function bodies and native projections remain exact in the separate candidate receipt.

`work/unity-70167bbc-repair1/candidate.json` SHA256 `df875e23f758b58b708791bef948666e3182a697569ad8e00c1f27cba3324e54` binds exact candidate COFF `e025d76836d00830cacd5f3328c752fa5e1f3f39504493dbd54aaa11ead957c0`. Existing whole-family numeric-minimum/maximum qualification remains separate; this repair makes no new universal floating-point claim.

## Executed normal-input profile

`work/frame-rounding-qualification3/acceptance.json` SHA256 `1ea54fd47354dc7e59d0c9c17ea4ab83e737d6613c0784b7b7d6bbd445ae63e8` passed 336 exact records on each of actual original ARM/static Bionic, raw Windows and the exact repaired 128-definition polled COFF. Before execution, a semantic predicate admits each geometry scalar only when its exponent is not 255 and it is normal or signed zero. This selects 19 geometry samples plus two real component-lookup-miss profiles. Both parent-chain shapes, four rounding modes and two initial sticky-FPSR values are exercised. There is no output-based filtering or normalization.

The complete function executes three genuine selected helpers: component lookup `7025d944`, rectangle access `70366140`, and its clean-component path through `70365b10`. TEST-owned valid component containers/type-range metadata and object chains supply their inputs; no helper return is manufactured. The fixture explicitly seeds the type-range descriptor and clean component fields, and does not claim whole Unity initialization or dirty-transform update coverage. Unreachable linker references abort if executed.

Records compare return value, FPSR, FPCR, NZCV, Q0..Q3 bytes and complete owned-data hashes. Additional assertions check genuine hit versus 120 fallback paths, real global-counter restoration, frame/SP/PC, saved high64 GPRs, Q31/high State cell, State1200 alignment and opaque Memory64 contents/identity. The exact original 128-byte body executes its own 16-byte frame. Neighbor 127 preservation is established by the candidate source/native projection proof, rather than by unrelated test execution.

## Retained edge limitations and all 16 FPCR projection

Qualification 2 deliberately tried 2176 broader records on original ARM and the exact polled candidate. It found 96 differences: 32 with a signaling NaN as the second comparison operand (missing cumulative IOC), and 32 each in two subnormal-scale cases with FZ enabled (including result differences). All raw records, failure and mismatch summary remain preserved. These edge cases are outside the normal-input predicate; they are not repaired, normalized or accepted by this gate. Qualification 1 failed before execution because its controller used a wrong QEMU path.

`work/frame-rounding-normal-projection1/acceptance.json` SHA256 `abfe796829575e2f20024fa1258bfb94a1ad03e51edfd316b4faa0cb3fd0238f` performs a read-only projection of the complete preserved qualification 2 records. It uses the already-qualified input predicate and byte-identical scalar initializer, independently of observed results. All 1344 normal-domain records match exactly between actual original ARM and the exact production polled object across four rounding modes, FZ off/on, DN off/on, both chain shapes and both sticky-FPSR seeds. All 96 known mismatches remain outside the predefined domain. This does not extend raw-Windows execution beyond qualification 3's four rounding modes with FZ/DN clear.

No live geometry values or FPCR were logged, so the fixture does not infer them. Actual original-game integration remains a separate test. No full ART, global IEEE correctness, synthetic frame, timeout, native helper-result stub or game/process control is claimed.
