# Scalar FRINTA repair and retained-function recovery

Runtime18 stopped at reported PC `0x70828c28` after 32 original render returns
and 30 swaps, with no accepted visible frame. The unsupported instruction was
the preceding `0x70828c24`, word `0x1e264063`: `FRINTA S3,S3`. The old lifted
body advanced NEXT_PC, stored error32, and called `__remill_error`; the following
FDIV had not executed. The exact static receipt is
`work/runtime18-frinta-frontier1/acceptance.json`, SHA-256
`a3c35387a1b8e5956405a57e71ac6ef417ef0261c293202169ea38c9b7447685`.

The authoritative Windows Remill fork adds the two scalar S/D decoders and
selectors. Sources remain numeric bit carriers; destinations clear the upper
bits of their 128-bit vector register. Integer-only semantics implement nearest
rounding with halfway values moving away from zero, independently of FPCR's
rounding direction. They preserve signed zero and infinity, quiet signaling
NaNs with IOC, apply DN, and flush subnormal inputs with IDC under FZ. They add
no IXC and preserve prior sticky status. Native floating-point rounding and
exception state are untouched. The profile matches the existing scalar P/M
implementation: FP enabled, exception traps and AFP alternate/merging controls
disabled. Half-precision, vector forms, and additional FP capabilities are outside
this patch.

Arm's scalar FRINTA operation and shared rounding/NaN pseudocode were read from
the retained primary document, PDF SHA
`b7baa6869789722df70da60170d999a62810409aaabbb6db1ef729ed68686bdf`.
Existing P/M decoder functions and every original `FP_ROUND_INT.cpp` byte are
preserved by an exact two-insertion inverse. The three-file patch contains 69
insertions and removes six unsupported-decoder stub lines.

The isolated tool receipt is `work/frinta-toolchain1/tools-ready.json`, SHA
`50b1c6fbe959c443eb89f197365ec8ca0c8b58333f39db290632500460d03180`.
It freezes lifter `73a1d6cf...` and semantics `24e908b3...`, using a fresh source
snapshot and CMake build with one compiler and unchanged dependency archives.
Previously qualified tools remain unchanged. The authoritative fork's exact
tested source was committed locally as
`1187c09aef09e130a2abe4605fced3cfb5a62bf9`. Append-only provenance and a patch
identical to the executed source patch are in
`work/frinta-toolchain1/source-commit.json`, SHA
`c74be009b1201859f2add1de974f6181ffcc28940f61ac566a25066dcc824869`.
Earlier executed tool/source receipts retain their original identities.

Primitive qualification is sealed in
`work/frinta-qualification1/acceptance.json`, SHA
`cb9960c0e2735683217584594daf675c924cb01437926f578ddde97b037295f6`.
It binds 94,848 actual ARM/Bionic and Windows records across nine register/alias
variants, 188 single-precision and 362 double-precision edge inputs, all sixteen
rounding/FZ/DN combinations, and two initial FPSR values. Public decoder tests
pass 2,069 controls, including all 2,048 S/D register pairs, an original literal,
and twenty boundary/neighbor controls. Old P/M fixture files are unchanged.

The exact original executable-word census finds five S-form FRINTA instructions
and no D-form sites in Unity/IL2CPP. They belong to two selected Unity functions:
`0x7042dee4..0x7042e060` (380 bytes, four instructions), and
`0x70828b78..0x70828c98` (288 bytes, the reached instruction). The census receipt
is `work/frinta-retained-census1/acceptance.json`, SHA
`4ddaddc979a2f4d5309c5e3c96d7d64acf35d00492aee6862e8f6aa8c6a40d56`.

`build_frinta_retained_overlay.py` relifts only those original FDE bodies and
splices them into the actual retained objects166 and289. Its default invocation
is read-only. The candidate receipt is
`work/frinta-retained-overlay2/acceptance.json`, SHA
`ea40ff36e8559bde28c21b5323c48911eea1a0263aa8fe79c3052730a8fb68bc`.
Objects are `4b2632b4...` and `646dce4b...`. In each module, all 127 neighboring
raw bodies, polled bodies, complete native bytes, and relocation contexts remain
exact. Old internal helpers and metadata definitions remain exact; new metadata
is appended with fresh IDs. The 4,660-object / 595,548-head inventory and all four
generated headers stay unchanged. Unrelated unsupported heads remain explicit.

Attempt1 was rejected before native compilation because instrumenting an entire
module renumbered old noalias metadata IDs. Its failure and artifacts remain in
`work/frinta-retained-overlay1`. Attempt2 instruments each fresh target alone,
then splices that polled body into the old polled module with a complete inverse.
It passes the strict preservation checks without normalizing old function bytes.

Both function gates link the actual candidate COFF objects. The 380-byte gate,
`work/frinta-380-qualification3/acceptance.json` (`77e6870a...`), compares 96
original ARM/Bionic, raw, and polled records. Original cached/fallback helpers
execute; width/height callbacks and inputs are explicit fixture controls. The
288-byte gate, `work/frinta-function-qualification2/acceptance.json`
(`ebda6b56...`), passes 9,988 checks over 384 finite binary-exact cases, using
genuine Bionic modff and the Windows tracked-write modf bridge. It checks normal
ABI return, Memory64, zero FPSR in this bounded corpus, and byte-exact guarded
data. Primitive NaN/FPCR coverage does not expand either full-function profile.
These gates establish no integrated original startup, visible game frame, or
gameplay result.
