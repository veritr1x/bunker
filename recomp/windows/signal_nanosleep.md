# Relative nanosleep

`SignalNanoSleeps` implements the Android LP64 `nanosleep(request, remaining)`
entry separately from the existing `SignalSleeps` provider. The old usleep,
SignalHost, Runtime and collector implementations remain unchanged. The new
marker is `0x7ff600300008`; only the original two pointer arguments participate.

The request is one fault-safe, unaligned 16-byte snapshot containing signed
64-bit seconds and nanoseconds. An unreadable request returns `-1/EFAULT14`;
negative seconds or nanoseconds outside `[0,999999999]` return `-1/EINVAL22`.
An immutable observation reports the actual pointers, copied fields and copy
status outside memory and signal locks. It neither rereads caller storage nor
publishes a new collector root.

The fixed budget uses the same active monotonic clock as existing timed
providers: actual `QueryUnbiasedInterruptTimePrecise` on Windows and
`CLOCK_MONOTONIC` on Linux. Signed ktime saturation includes the exact
`KTIME_SEC_MAX` boundary. Native waits are limited to one second per iteration
without rearming that deadline. Spurious notifications and blocked or ignored
signals cannot shorten the budget.

Completion preserves guest errno and leaves the output untouched. A caught,
admitted signal returns `-1/EINTR4` even with `SA_RESTART`. A nonnull remainder
is normalized and copied before the genuine translated handler runs; handler
execution time is not subtracted afterward. Request/output aliasing uses the
original snapshot. An invalid remainder on an interrupted call produces
`EFAULT14` while still running the real handler. The output is not validated
or written on ordinary completion. The expired-remainder race follows the
retained Android kernel branch that can complete without copying.

The owner must provide its actual bound signal lifetime, errno sink, delivery
boundary and admission policy. The game keeps admission zero here. Eligible
excluded signals and their siginfo remain pending; no pthread condition
checkpoint or new collector delivery phase is installed. Native errno,
floating environment and Windows LastError are preserved, with real handler
FPCR changes reapplied using the existing provider convention.

Fault-safe copies participate in Runtime shared-memory locking and write
invalidation. Their qualified scope requires stable native mapping and
protection during each copy. Concurrent `VirtualProtect`/`mprotect` mutation
and atomic equivalence of partial fault writes are not claimed. Read-only and
guard-page cases are tested without changing their protection in the copy.
Tagged addresses remain an explicit unsupported ABI profile.

The ARM reference uses the actual NDK/Bionic binary under QEMU8.2.2. That
emulator ignores both request-copy and remainder-copy errors and also copies
the remainder on any syscall error. Its 24 supported records cover normal
delays, invalid-value return/errno and valid/no-output/alias interruptions. Four
unreadable-request cases and two bad-remainder cases are excluded from the ARM
oracle. A separate native Linux x86_64 reference covers all 30 records,
including those six real `EFAULT` cases; it is not an ARM execution claim.
Invalid-request remainder bytes are excluded from both native comparison
oracles. Host tests independently require no invalid-request output mutation
from the primary Android kernel's early-return path. Failed references and
copied diagnostics remain in `work/nanosleep-arm-reference1`,
`work/nanosleep-arm-reference2` and the corresponding diagnostic directories.
The component's handler-delay import is explicitly a test fixture and is
never installed in the game.

Primary implementation inputs are Android13 Bionic's
[syscall list](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/SYSCALLS.TXT),
Android common13-5.10's
[nanosleep and remainder paths](https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.10/kernel/time/hrtimer.c),
and its
[time64 validation and saturation](https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.10/include/linux/time64.h).
Fetched bytes and hashes are retained in
`work/continuation1-nanosleep-design1`. These component and source checks do not
establish an original game frame.

Final qualification `work/nanosleep-qualification2/acceptance.json`, SHA256
`596efcd8c20d899f4783d97b8fbef7ca1aee352fe0e464a3c7f2a0117b16aa09`,
passes30 records and292 checks on Windows,30 records and290 checks on Linux,
and two named fatal controls per host. Both hosts match the supported24-case
ARM/Bionic subset and the full30-case native Linux reference. Actual translated
NDK callers and SignalDelivery handlers exercise direct/function-pointer calls,
fault-safe snapshots, output aliasing, handler-delayed remainder observations,
blocked/ignored signals, spurious wakeups, excluded pending signals and native
environment restoration. The first host attempt is retained with its successful
Linux run and Windows strict-compiler formatting failure; the final held source
passes both hosts. These are component tests, not an original game execution.
