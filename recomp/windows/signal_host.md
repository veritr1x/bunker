# Isolated signal and semaphore foundations

These new providers are not installed in the production Unity harness. They do
not interrupt native Windows execution, create signal frames, establish GC-safe
provider phases, implement full Linux signal policy, or prove GC correctness.

SignalHost owns process dispositions and explicit virtual thread lifetimes.
RegisterThread snapshots a parent's mask and starts with no pending signals;
BindCurrent pins delivery to the owning host thread. DropThread leaves a
tombstone, so a stale token cannot be rebound. The owner must call DropThread
when its real thread exits and keep the host alive until all waits/callbacks end.
An unreported OS-thread exit is not detected by this isolated policy model.

Queue coalesces standard signals, preserving the first pending siginfo. It
publishes an acquire/release NeedsPoll flag on a stable ThreadRef and invokes the
optional parent poll notifier only after releasing locks. Unblocking signals
also requests a poll. Only DispatchOne, on the bound target thread, can invoke
the supplied delivery boundary. It copies action/info/original mask, applies
automatic handler blocking, unlocks, runs the boundary, and restores masks even
on exceptions. The callback can return an explicit replacement mask for later
ucontext edits. Nested DispatchOne/Suspend calls remain explicit; the owner must
provide a separate handler State/frame, never execute in the interrupted State.

Suspend atomically replaces the mask before checking pending work or waiting.
Per-thread generation events prevent a queued restart from being lost between
the check and sleep. The delivery metadata saves the mask from before
sigsuspend, and normal completion restores it and reports EINTR. This includes
explicit nested stop-handler-shaped waits for a restart signal. There is no
claim that the actual Boehm collector is integrated.

Android 13's
[signal.cpp](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/signal.cpp),
[sigprocmask.cpp](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/sigprocmask.cpp)
and [reserved-signal rules](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/platform/bionic/reserved_signals.h)
are authoritative here: pthread_sigmask, sigprocmask and sigsuspend filter
reserved signals so 32 stays blocked and 33–40 are unblocked. Kernel-level
SIGKILL/SIGSTOP mask removal applies too. Sigaction's handler mask is deliberately
not subjected to the Bionic reserved-signal filter.

This subset accepts standard caught/ignored actions with SA_SIGINFO/SA_RESTART.
Default process effects, real-time queuing, SA_NODEFER/RESETHAND/ONSTACK/RESTORER,
process-directed routing, hardware faults and cancellation are unsupported.
Queue without supplied siginfo populates only the signal number; integration
must provide truthful code/process/UID metadata when those fields matter.
Primitive results are positive Android errno values. Isolated import adapters
preserve pthread direct-error conventions and translate POSIX calls to -1 plus
the configured tracked errno sink.

Semaphores has Android's 16-byte/four-byte-aligned storage and a sidecar registry.
Initialization/destruction invalidate the full lifetime; counter publication
uses tracked guest writes. Mutex ordering publishes ordinary memory across
post/wait. Waiters use the same per-thread generation event for semaphore posts
and pending signals. No registry, semaphore or guest-memory lock is held across
the target boundary, so a handler can post an acknowledgment or enter a nested
sigsuspend. Named/process-shared semaphores are unsupported.

Android 13
[semaphore.cpp](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/semaphore.cpp)
specifies the 0x3fffffff count limit and trying an available token before
validating a timed-wait deadline. Invalid nanoseconds return EINVAL; negative or
expired absolute realtime deadlines return ETIMEDOUT. Host-clock-unrepresentable
deadlines report EOVERFLOW explicitly. Null invalid pointers are checked where
possible, rather than crashing the host; arbitrary unmapped addresses still
require the caller's memory-validation boundary.

Two reference details matter:

- Real ARM64 QEMU confirms untimed sem_wait restarts with SA_RESTART, while
  absolute sem_timedwait returns EINTR even with that flag. Linux 6.1's
  [futex wait path](https://github.com/torvalds/linux/blob/v6.1/kernel/futex/waitwake.c)
  uses ERESTARTSYS without a timeout and a restart block with an absolute timeout;
  the [ARM64 handler path](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/kernel/signal.c)
  converts the latter to EINTR after a caught signal.
- The glibc/QEMU reference validates invalid nanoseconds before its ready-token
  path. Bionic explicitly does the opposite. Tests record this reference
  difference and require the Android result for that case, rather than treating
  glibc as an Android ABI oracle.

test_signal_host.py builds actual NDK callers for dispositions, masks, pending
coalescence, sigsuspend, ignored signals and semaphore results. Common API results
are compared against ARM64 QEMU, with the documented Bionic exception above.
Direct cross-thread gates cover target ownership, notification after unlock,
mask inheritance/restoration, token ABA, nested stop/restart/acknowledgments,
pending requests during delivery, semaphore interruption/restart, timeout errors
and overflow. The NDK test uses a separate copied State in its explicit callback
boundary; it is not asynchronous delivery.

Linux and native Windows each passed 155 foundation checks, 35 actual NDK
result records and all four QEMU interruption/restart scenarios. The NDK image
has 20 translated traces with zero unsupported instructions.
