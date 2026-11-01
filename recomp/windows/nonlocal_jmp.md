# Android 13 arm64 nonlocal context foundation

NonlocalJumps saves an actual guest context into the Android 13 Bionic buffer
and provides a checked, pure decoded transfer plan. The save imports have real
effects and return zero on their normal first return. All longjmp imports
currently terminate with a specific diagnostic and exit 3, including decoded
destination PC/SP when validation succeeds. They never return a fabricated
success, call a Windows CRT longjmp, or throw an exception through lifted LLVM.
This is not a working nonlocal transfer implementation.

The supported virtual CPU profile has PAC disabled, no HWASan instrumentation,
and Bionic's 8192-byte shadow-stack offset mask. The adapter implements that
wire encoding; it does not allocate or supply shadow-stack storage.
PACIASP/AUTIASP in the original source
are hints on the reference cortex-a53 CPU. Authenticating real PAC-signed return
addresses, HWASan stack-unpoisoning, and a different SCS profile are unsupported.
The process must advertise a compatible virtual CPU rather than claiming PAC.

The implementation is tied to the primary Android 13 sources:

- [arm64 setjmp.S](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/arch-arm64/bionic/setjmp.S)
- [process cookie implementation](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/setjmp_cookie.cpp)
- [public setjmp declarations](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/setjmp.h)

The public jmp_buf is 256 bytes; sigjmp_buf is 264 bytes. The actual assembler
uses only the first 25 64-bit words. Word 0 contains an even random process cookie
with the save-mask flag in bit 0. Word 1 contains the mask only when requested.
Words 2–15 contain cookie-mangled X30/SP, X28/X29 through X20/X21, the low
13 bits of X18, and X19. Words 16–23 contain D14/D15 through D8/D9. Word 24 is the XOR
of words 0–23. Reserved trailing words remain untouched; an unsaved mask word
also remains untouched but contributes to the checksum.

setjmp saves the mask, _setjmp does not, and sigsetjmp accepts only flags 0 or 1:
the original Bionic cookie helper rejects other bits. FPCR/FPSR, TLS, caller
saved GPRs and NZCV are not restored from this buffer. A pure Materialize plan
retains the current FP environment/TLS, restores the saved callee GPRs and SP,
merges only the saved low X18 bits, clears the high SIMD halves when restoring
D8–D15, and normalizes an int return value of zero to one. It does not apply the
mask or change execution. Caller saved registers/flags in that pure result are
not a promise of exact assembler scratch-register values.

The owner supplies the actual current target-thread token/generation and guest
stack bounds, a truthful mask reader, executable code-range validation, and an
owning-region resolver with lifetime generation. The adapter validates the full
declared buffer before access, checks alignment and stack bounds, captures those
identities at save, and rejects thread reuse, region reuse/revocation, changed
stack bounds, corrupt cookie/checksum, invalid continuation, or a saved SP below
the current SP. Forget and DropThread retire registrations. No owner callback
or guest-memory operation runs while the internal registration mutex is held.
Guest input/output uses the shared tracked-memory APIs.

A FileSystem mmap generation can establish mapping lifetime, including reuse
at the same address. It cannot prove the lifetime of individual Unity arena
subobjects. Similarly, stack bounds and SP ordering cannot detect every return
from a C frame followed by later stack reuse. The owner must explicitly retire
known environments and future controlled transfers require active execution/
frame identities. Concurrent mutation or destruction of a buffer being saved
is not made safe by this adapter. A raw VirtualQuery result or fabricated mask
is insufficient integration evidence.

test_nonlocal_jmp.py downloads the original assembler into ignored work output,
requires SHA256 cd0eacde5d3332c6726a0a07ccc0c37f8ac3eb4a5e90f6e3078e9c40875e0309,
retains its copyright, and uses its unmodified body with minimal ENTRY/END,
alias and SCS constant scaffolding. The test namespaces its public symbols,
uses a deterministic cookie and controlled mask helper, and executes it under
ARM64 QEMU cortex-a53. 512 save contexts check raw words against independently
captured actual registers/SP/LR. A further 64 real nonlocal returns verify
callee restoration, SIMD high-half clearing, X18 merging, value normalization,
mask/no-mask behavior and unchanged current FPCR/FPSR. The controlled mask helper
isolates the private wire algorithm; it does not replace the separately tested
SignalHost/Bionic mask-policy foundation.

The same assembly caller is built by the actual NDK and statically translated
to each host. Native Linux and Windows tests each pass 563 checks including all 512 normal save calls,
buffer guards, ownership/ABA rejection, pure plan materialization, and decisive
fatal longjmp/corruption/flag paths. NDK compilation independently asserts both
public buffer sizes. The fixture requires no Remill changes.
Ignored work/nonlocal-linux and work/nonlocal-windows result.json files record
the exact tested source, executable, reference and manifest hashes.

The observed Unity call is setjmp at RVA 0x43a048 with return PC 0x7043a04c,
inside entry 0x7043a014. Its buffer is scope object +8, observed at
0x144000017f8. The current trace header contains the function entry but not the
saved return PC. Normal first return uses the existing translated continuation.
A future nonlocal dispatch needs a real root at the post-call instruction and
an owning shard refresh with closure/State-ABI validation.

Simply changing State.pc from the import cannot redirect optimized translated
control flow. Throwing a C++ exception through current intrinsics is also
invalid: lifted PLT IR declares __remill_jump nounwind, and return intrinsics
have that contract too. A complete transfer requires a compiler/runtime protocol
that unwinds exactly the abandoned guest/native continuation chain, checks the
saved execution lifetime, preserves nested Runtime/provider cleanup and FPU/
reservation state, applies the saved mask only after committing an accepted
transfer, and dispatches the rooted saved PC. An exception design would first
need coordinated IR-contract and Windows unwind-metadata changes with tests;
an explicit transfer-status propagation design may avoid that requirement.
No such runtime/compiler change is included here.
