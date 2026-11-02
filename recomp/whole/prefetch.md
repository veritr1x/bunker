The immediate prefetch gate executes the same NDK-assembled core object through the frozen AArch64 lifter on Windows/Linux and as real AArch64 instructions under pinned QEMU. It supports no game initialization or guest-PC bypass.

The structured decoder probe sweeps all 512 signed imm9 and 4096 scaled imm12 values, every Rn/Rt combination for both classes, the six original IL2CPP words, and neighboring load/store/reserved/literal/register instructions. It inspects address-calculation operands, unsigned numeric hint fields, SP selection and ordinary fallthrough rather than inferring effective addresses from an effect-free hint.

The native core snapshots all GPRs, vectors, SP, NZCV/FPCR/FPSR around each hint. Its real ABI frame restores callee-saved GPRs and q8–q15 before returning; the native reference wrapper separately restores FP control/status. Per-host addresses are checked locally before normalization for record comparison. Separate raw leaves allow full State preservation checks without snapshot writes. Real LDXR/hint/STXR probes qualify exclusive preservation. An actual neighboring load/store remains observable, and a real no-access load is isolated in each reference/host subprocess as a negative control.

Arm DDI0602 ID032025 supplies the signed/scaled immediate, numeric hint, SP-without-alignment-check and tagchecked=false operation. Arm-owned ACLE permits implementations with no prefetch effect. This gate does not establish cache timing, hardware performance, MTE functionality, privileged execution or physical hardware behavior from QEMU. NOP is an unchanged runtime control; currently unsupported YIELD/WFE/WFI remain decoder-only controls and gain no wait-semantics qualification.

Run `test_prefetch.py` under WSL with an accepted immutable toolchain directory, a new output path, accepted support commit and pinned reference tools. It creates a fresh frozen source tree, records compiler/tool/input hashes, requires terminal markers and exact normalized records, preserves failed candidates, and rehashes all frozen inputs after execution. No result is accepted merely from process exit zero. Exact commands and acceptance evidence are retained in each candidate. Results must be filled from real runs; this document alone makes no passing-test claim.

The November 2 qualification is `work/prefetch-fixture5/acceptance.json`, SHA256
`e387dc78d1f3c2d21999b8e105916faa1c53f86e67084cc31ffa6aebbddb71fc`.
All 6,741 decoder checks pass. The 171-case fixture produces 5,680 records on
each of ARM64/QEMU, Linux x86_64 and native Windows, with exact normalized
record parity. Each lifted host also passes 171 raw State-preservation and 171
exclusive-reservation probes. Ordinary load/store effects remain observable;
protected-memory loads fault with SIGSEGV on ARM64/Linux and native Windows
status C0000005. Windows status is captured in native PowerShell because WSL
interop truncates exception exit codes. Both translated cohorts contain 515
heads in five objects, with zero unsupported traces or unresolved direct calls.

The Remill implementation is commit
`bace64812c4bf927dfb40e89eb9c5724e8b2fe5c`, based on `d33a182`.
Its immutable lifter SHA256 is
`7e3e484c165a1308890d482fdb48baa9db0cb959867197bc02f607cd7a6a8126`;
semantics SHA256 is
`c5f0d94e6b234f5f0f376eeb999bc9bfbaee62d654381751c3080e5c621ac3b5`.
The State ABI remains 1,200 bytes/alignment16. All 1,211 prior semantic function
bodies are unchanged; the new semantic returns its input memory token without
accessing State or target memory. Prior scalar and exclusive regressions pass
on both hosts. Seven selected prior vector cases match ARM64 and the integer
oracle; the legacy full-suite count assertion failure is preserved separately
from their explicit seven-case acceptance.

The fixture's native wrapper initializes NZCV before entering the shared core;
the lifted harness initializes the equivalent State fields. The core observes
flags through CSET and non-flag-setting shifts/ORR, restoring both scratch
registers. This avoids requiring the lifter's still-unsupported NZCV system
register access just to observe prefetch behavior. Remill dependency headers
use `-isystem`; new host test code retains `-Wall -Wextra -Werror`.

Primary instruction semantics are pinned from [Arm DDI0602 ID032025](https://documentation-service.arm.com/static/67e40f3398aa3c3b6eea6a85)
and the permitted no-effect implementation from [Arm ACLE](https://github.com/ARM-software/acle/blob/main/main/acle.md).
This component qualification permits a new sparse game cohort; it does not
establish a completed game initialization or rendered frame.
