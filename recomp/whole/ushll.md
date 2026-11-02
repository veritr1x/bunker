# Unsigned widening shift

The original Managed-copy gate reached Unity ZIP enumerator413e00 and stopped
at the unsupported instruction at413eb0, bytes `00 a4 20 2f`,
`ushll v0.2d,v0.2s,#0`. The runtime diagnostic reports the next PC70413eb4.
Candidate4, its executable and failure log remain preserved. The ADD at413eb4
is unchanged.

USHLL/USHLL2 now decode unsigned8→16,16→32 and32→64 lane widening with every
legal immediate0..width−1. Q selects the lower or upper64 source bits; both
forms overwrite the entire128-bit destination. UXTL/UXTL2 aliases share these
semantics. This decoder rejects immh0 and immh with bit3 set. At the outer
instruction dispatcher, immh0 belongs to the separate valid MOVI encoding;
the tests require that it remain a constant write with no source read.
Signed SSHLL and the
fixed-width SHLL instruction retain their prior unsupported behavior.

The semantics snapshot the full source before any destination write, use an
unsigned64-bit shift after zero extension, and preserve NZCV/FPSR/FPCR.
The6 instruction selections distinguish source width and source half.

`test_ushll.py` assembles473 fixture functions using the installed Android NDK,
then links that actual object into an AArch64 Linux reference and the lifted
fixture image. Each Linux/Windows run compares121,088 full records against both
ARM64 QEMU and an independent integer lane model. Records include full results,
source and unrelated registers, NZCV/FPSR/FPCR and output guards. Inputs cover
edge patterns, deterministic random bits, every immediate, lower/upper halves,
overlapping operands, registers17/31, UXTL aliases and the exact reached word.
Input/output alignments vary, the source memory must remain unchanged, and the
translated caller must return with its original SP and checked completion PC.
The shared NDK core contains only actual vector loads, the tested instruction,
vector stores and return. The native-only ARM64 wrapper sets/records flags
with real MSR/MRS and restores the caller's state. The translated C++ boundary
sets/records the corresponding State fields around that identical core,
including both raw flags and their individual Remill fields. It does not
claim support for the existing unsupported MRS/MSR NZCV decoder.

`test_ushll_decode.py` tests every Q/immh/immb combination (112 legal USHLL,
16 alternate MOVI,128 reserved), the literal reached word at70413eb0, unchanged signed/fixed-shift
negatives, and the full original ZIP enumerator from the pinned original ELF.
Both scripts require a new output directory and freeze/hash compiler inputs;
they preserve prior binaries and failed candidates. Acceptance files are emitted
only after their actual comparisons pass. Fixture success alone does not prove
Managed extraction, engine initialization, managed execution or a game frame.

Run in WSL with explicit `--lift`, optional `--semantics-dir`, `--out`, and
the accepted Remill headers. The semantic gate also requires `--ndk` and
`--reference-root`; use `--windows` for the MinGW/native Windows comparison.
The decode gate requires `--unity` pointing to the original pinned libunity.so.

Accepted evidence is in `work/ushll-linux2/acceptance.json`,
`work/ushll-windows2/acceptance.json` and `work/ushll-decode2/acceptance.json`:
121,088 records on each platform and260 decoder/original-code controls pass.
The frozen lifter SHA256 is
`fa80a8edb3f33d1815ad4b256d7eaa9d1625889adfd6ff59044be0b1cc6277ad`;
semantics SHA256 is
`9524e65b09c51e5b62d1a2f2fae631da9cb6f8ddda5fa3af6401947986cae802`.
The shared NDK core object SHA256 is
`a0101b8ed22fc7c5ac80d7f90b10c0e1157010c173c3ba76b9fc7317b8a2c17e`.
Linux and QEMU normalized record SHA256 is
`0f681b71f100526c559f2500ff49a597c7fa2ac2d8fc99e35a93b7805f24458b`.
Windows records compare exactly after text newline normalization; their raw
file hash differs because the native CRT emits CRLF.

The first `ushll-linux`, `ushll-windows` and `ushll-decode` attempts are preserved.
Their failures exposed test-boundary assumptions: existing MRS NZCV support was
absent, and immh0 was incorrectly classified as globally invalid. The corrected
boundary above executes the identical core and measures real State/native
flags; the decoder controls distinguish MOVI from source-reading USHLL. No
system-register implementation or original opcode was substituted.
