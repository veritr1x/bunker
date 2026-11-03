# Owned native thread affinity

ThreadAffinities handles only Android syscall122 with kernel length4 under
the explicit WindowsSingleGroupNativeIndices profile. Number, pid and length
decode their low32 bits; the mask pointer keeps all64 bits and unused arguments
are ignored. Other lengths and syscalls remain named unsupported boundaries.

The pinned Android13 kernel copies exactly four unaligned user bytes before
looking up the target PID. A bad copy therefore returns EFAULT before a dead
target's ESRCH. The Windows implementation uses the existing Runtime readonly
memory lock and ReadProcessMemory on itself, without a guest write or memory
epoch change. It retains the explicit untagged lower48 address profile.

The target comes from the existing Pthreads native-handle lease. The provider
never reopens an arbitrary numeric TID. Known retired/negative IDs return ESRCH;
other unowned targets are unsupported. The duplicated handle retains the native
object across exit, without guaranteeing its continued liveness.

The requested32 bits intersect actual process/system masks. The current thread
mask is not the ceiling, so a previously narrowed thread can expand again.
An empty eligible intersection returns EINVAL. Otherwise SetThreadAffinityMask
performs the operation and GetThreadGroupAffinity checks actual readback. No
process affinity, CPU allocation or CPU-set selection is changed by the provider.

This profile requires a single native group0 and consistent native CPU indices,
online count and system mask. Process/thread CPU-set ID and newer mask selections
must be empty; CPU allocations, reservations and realtime/unknown flags are
rejected. Parking is a power-management state and is not excluded as a reservation.
Missing query APIs are explicit unsupported boundaries. This models a finite
native Windows mapping, without Linux scheduler fairness or performance parity.

Observers receive actual copied/requested and native result/readback fields
with validity flags outside registry, service and Runtime memory locks. Each
observer alone preserves native errno, LastError and floating-point environment.
Success preserves guest errno; genuine operation failures update it. An
unsupported operation does not fabricate a Return observation.

QEMU8.2.2 user-mode emulation rejects a four-byte sched_setaffinity buffer before
copying it, although the pinned real Android kernel setter accepts it. The getter
has a separate alignment rule that must not be imposed on this setter. Test
evidence must distinguish actual ARM64/QEMU four-byte divergence, a separately
labelled eight-byte ARM64 control, and native Linux four-byte kernel behavior.
No Windows/ARM64 four-byte result-parity claim may be inferred from the control.

Qualification2 passes22 native Linux four-byte records matching the22 shared
Windows cases. Qualification1's unchanged Windows execution has32 records,
158 checks,11 lifted heads/two objects and three intended native failure exits.
The22 actual ARM64/QEMU four-byte records retain the documented emulator
alignment discrepancy; two eight-byte controls are reported separately.

The final qualification corrects the native Linux assembly caller's SysV
variadic AL vector-count to zero and reruns that oracle. Windows/NDK/ARM64
source dependencies, binaries and actual executions are reused with explicit
hash/lineage proof; they were not rerun. The original qualification remains
preserved. Acceptance `work/affinity-fixture1/qualification2/acceptance.json`
SHA256 is `0e67105a96c8ecd6f4ef0e8a997039574e05b5c424ef412ebb51e8f5fa2b872e`.

An original game execution of this provider remains pending. Game27 logs the
actual four-byte call but neither reads its mask nor executes the operation.
