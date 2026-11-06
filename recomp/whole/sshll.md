# Signed widening shift and reached Unity font function

Runtime15 reached the original `SSHLL V0.2D,V0.2S,#0` at `708d13d8`, word
`0f20a400`. Its old unsupported stub reported the next PC, `708d13dc`, which
is the unchanged following `STR Q0,[SP,#0x10]`.

The decoder now admits signed 8-to-16, 16-to-32 and 32-to-64 widening, both
source halves and every legal immediate. SXTL/SXTL2 use the zero-shift alias.
The semantics snapshot the source, sign-extend each selected lane, shift using
unsigned arithmetic, truncate to the widened lane and replace the complete
128-bit destination. This avoids undefined C++ left shifts of negative values.
NZCV, FPSR and FPCR remain unchanged. The existing unsigned widening bodies are
unchanged; reserved widening encodings remain rejected.

`test_sshll.py` passes 121,088 records from 473 actual NDK assembly functions.
The same instruction object executes against real static Bionic under ARM64
QEMU and as lifted Windows x86_64 code. An independent signed-integer oracle
checks every row. Widths, halves, all shifts, aliases, separate/overlapping
operands, high registers, edge values, deterministic random bits, unaligned
buffers and the exact reached word are covered. Full source/results, flags and
memory guards are checked. The Windows boundary also checks all unrelated
State bytes and the value and contents of a nonnull opaque Memory64 token.

`test_sshll_decode.py` passes 260 controls: 112 legal widening encodings,
16 separate MOVI encodings, 128 reserved encodings, the exact signed word,
unchanged unsigned/fixed-shift controls and the complete original 940-byte FDE
at `708d13a8..708d1754`.

The bounded producer replaces only `sub_708d13a8` in selected object301.
All 127 neighboring raw/polled bodies and their full native function bytes,
internal helpers, State type, existing polls and call/transfer guards are
preserved. No trace heads are added; the other 4,657 objects and all four
generated headers remain unchanged. The new target has 22 actual guest calls
paired with 22 transfer checks. The complete optimized module passes its guard
audit. Original opcode bytes are not patched.

`test_sshll_function.py` additionally passes 3,840 Windows checks across 256
cases matched to the real original ARM function. The original 940-byte body
and four original helper bodies (68 bytes) execute unmodified. One explicit
test font callback observes the actual signed stack spill and returns a
nonzero status, selecting a genuine early-error epilogue. The repaired
Windows polled body matches the status, defined memory changes and spill;
callee-saved GPRs, SP/LR/PC and Memory64 are checked. The fixture does not claim
the font callback's production semantics, successful font-loading paths,
whole-game execution or a visible game frame.

Evidence:

- `work/sshll-windows1/acceptance.json`
- `work/sshll-decode2/acceptance.json`
- `work/sshll-function-qualification1/acceptance.json`
- `work/sshll-unity-fde-overlay1/acceptance.json`
- `work/sshll-qualification1/acceptance.json` combines the gates and their
  exact source/tool/object identities.

The decoder's first attempt retained the unsigned test's old ELF offset and
failed that fixture assertion after its encoding controls. The corrected
attempt reads `8d13d8`. A copied console-only “ZIP enumerator” label was fixed
afterward; its strict one-line inverse is recorded separately. The semantic
suite's frozen copy of the decoder driver is unused by that suite and remains
historical. No executed artifact or receipt was rewritten to hide these
differences.
