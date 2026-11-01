# Isolated AArch64 signal-frame bytes

`signal_frame.{h,cpp}` serialize and restore the Android AArch64 little-endian
wire format using host byte buffers. They do not deliver signals, perform an
`rt_sigreturn`, apply masks/altstack policy, park providers, or establish GC
correctness. Existing dispatcher/runtime/pthread code is unchanged.

The layout follows Linux 6.1's
[`signal.c`](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/kernel/signal.c),
[`sigcontext.h`](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/include/uapi/asm/sigcontext.h)
and [`ucontext.h`](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/include/uapi/asm/ucontext.h).
The NDK handler separately compiles against Bionic's actual `siginfo_t`,
`ucontext_t`, `mcontext_t`, `stack_t` and FPSIMD declarations, consistent with
the [Android 13 ucontext headers](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/sys/ucontext.h).

The caller supplies registered interrupted/delivery stack bounds, an already
selected delivery top, signal number, handler/restorer addresses, raw siginfo,
saved mask/altstack/fault metadata, and full interrupted PSTATE. Placement is:

```
record = align_down(selected_top - 16, 16)
frame  = record - 4688
```

The 16-byte FP-chain record saves old X29/LR. Handler SP is `frame`, X29 is
`record`, LR is the supplied restorer, and PC is the handler. X0 is the signal;
SA_SIGINFO additionally sets X1=`frame` and X2=`frame+128`. TLS is retained in
the caller's State baseline; Linux ucontext has no TLS field.

The frame contains 128-byte siginfo and a 4560-byte ucontext. Machine context
starts at frame+304; the reserved record area starts at frame+592. A 528-byte
FPSIMD record (`0x46508001`) stores 32 vector registers and 32-bit FPCR/FPSR,
followed by a 16-byte null terminator. Other bytes are deterministically zero.
State.sr is authoritative for NZCV and six cumulative FPSR flags: serialization
replaces stale mirror flags and preserves other FPSR bits, including QC. Restore
updates both canonical flags and mirrors. Full non-NZCV PSTATE is returned as
explicit metadata because Remill State cannot represent it completely. Handler
PSTATE metadata clears TCO; BTI and SVE/SME entry policy are unsupported.

Serialization has no guest-memory side effects. The caller must validate that
handler/restorer are executable translated entries, publish bytes with tracked
writes, and provide the appropriate execution/TLS/fenv context. The serializer
checks nonzero code alignment, stack ranges, arithmetic overflow and frame fit.
Restoration is transactional and validates its bounded byte view, saved SP/PC,
record size/alignment, duplicate/missing FPSIMD and terminator. Unknown extension
records, including SVE/SME/extra/ESR, are rejected instead of silently discarded.
High nonarchitectural State FPCR/FPSR bits are rejected. Raw mask, siginfo,
altstack and PSTATE metadata are preserved; validity/application under complete
Linux signal policy remains the caller's future responsibility.

`test_signal_frame.py` builds actual NDK handler readers/writers, translates them,
and runs both normal-stack and alternate-stack byte images through the checked
host adapter. Tests cover all GPR/SIMD bytes, register pointer roots physically
present in the synthetic stack, handler edits, FP-chain/return context, flag
canonicalization and transactional failures. A separate ARM64 QEMU `SA_SIGINFO`
probe on Cortex-A53 confirms real generated normal/alternate frame addresses,
FP chain, mask/altstack fields, FPSIMD magic/size/terminator and header offsets.
QEMU user-mode evidence is not an execution test on an Android 13 kernel.
The glibc reference has a larger userspace `sigset_t` than Bionic's 8-byte type;
ucontext reserves the same 128-byte mask area, so the checked machine-context
offset agrees. The serializer uses Android's 64-bit mask.

Linux and native Windows each passed **3,921 checks across 32 NDK translated
reader/writer cases**, with three translated functions and zero unsupported
instructions. Both real QEMU normal/alternate signal-frame probes passed too.

```sh
python recomp/whole/test_signal_frame.py --ndk /path/to/ndk --lift /path/to/remill-lift-18 --remill /path/to/remill-src --reference-root /path/to/reference-tools/root
# Add --windows for the native Windows adapter gate.
```
