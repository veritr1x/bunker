# Scalar numeric floating-point minimum and maximum

The first original startup using the complete guest-transfer cohort reaches
`FMINNM S0,S0,S1` at `709a12c0`, bytes `0078211e`. Its unsupported path reports
the next PC, `709a12c4`. Function `709a1280` occupies FDE
`709a1280..709a12ec`, selected object343. Frontier receipt:
`work/first-frame-guest-transfer-frontier1/acceptance.json`, SHA256
`d9a42f9b7ea1a9dca1789f1c04c4130a1373943af7eded2651edd83c3b1cba0c`.

The isolated repair adds four scalar S/D FMINNM/FMAXNM decoder/semantic forms.
It unpacks both operands, preserves sticky IDC when flushing subnormals,
handles a lone quiet NaN numerically, and retains the existing minimum/maximum
helper for signaling NaNs, DN, signed zeros and ordering. Integer bit operations
avoid host floating-point NaN differences. The baseline requires enabled FP
with traps and AFP alternate/merging controls disabled. Half, vector and
pairwise forms remain outside this repair.

The official semantics are Arm DDI0602 ID032025, FPMinNum/FPMaxNum, preserved
in `work/game14-next-boundary-audit/arm-arm-ddi0487.{pdf,txt}`. The isolated
source excerpt and source delta are pinned by the toolchain receipt below.

Qualification uses the same NDK core object on ARM64/QEMU and translated
Windows/Linux. All three produce 24,576 matching records: 24 register/alias
cases, 16 FPCR modes, 32 operand pairs and two initial FPSR values. Every
record checks complete 800-byte architectural snapshots against an independent
bit oracle, including NaN priority/payloads, signed zeros, subnormals and
infinities. Each translated host additionally passes 384 full 1,200-byte
State and opaque memory-token checks, plus an ordinary memory-effect control.
These leaf fixtures use unchanged `compile.py`; guest-transfer integration
is checked separately on the actual guarded game shard.

Receipts:

- `work/fp-numeric-minmax-qualification1/acceptance.json`, SHA256
  `19d724b9b523f4d446c9231da9aea5661cd1ceaca8969d7661037c1bc29cecc3`.
- `work/fp-numeric-minmax-decode2/acceptance.json`, SHA256
  `09e4e2b647485cfc90d38410cb7cff2fadbdf0c5190c4b1a3698cb789f3c41ed`:
  897 numeric decoder cases and 150 legacy/excluded controls; the latter
  serialize exactly as the baseline. Q1's legacy vector-register expectation
  error is preserved; no tool or semantic change was required.
- `work/fp-numeric-minmax-preparation1/acceptance.json`, SHA256
  `fbfc1cf5a52e2d8999770ba95f2a9704a9a79bc7682f9ee973d5cd8152acbc71`:
  lifter `14f6409b2d88fbde54b3641ff09db0b3bd03907e3efa33de405755e85542e11b`,
  semantics `6dd3ed0e502e37b97e8042de4ea6f3f95ed56066068d753d64b2f873ad83f56e`.
  All 1,264 old function texts and 1,425 old selectors remain exact. Nine
  diagnostic-only source-coordinate nodes on 45 unchanged empty assembly
  barriers differ; all other metadata remains exact. The initial strict
  comparison failure is preserved. Unrelated default and opted-in final IR
  matches the qualified guest-transfer tool.

A fresh lift of all128 heads also permutes private scratch allocations and
local names in six neighboring functions. That full object remains held.
The selected diagnostic candidate instead splices only the freshly qualified
`709a1280` body into the old raw module, retaining every other module byte.
Fresh polling, LLVM verification, optimized guest-transfer guard analysis and
COFF compilation pass. The final raw/polled neighbors and all127 neighboring
native function projections are exact; the fixed function is the only native
change. All direct references remain closed against the same595404 heads.

Scope receipt: `work/unity-numeric-minmax-scope3/acceptance.json`, SHA256
`0f14c8a50d4704a6a3a8ef8f40481120e72941781efc90e9ed058ad1b281b98b`.
The first execution of this sparse diagnostic remains a separate gate;
component qualification alone establishes no frame or playable game.
