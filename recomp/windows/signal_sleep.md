# Interruptible usleep

`SignalSleeps` implements Android LP64 `int usleep(useconds_t)`: only W0's
unsigned32 input participates, and the result is signed32. Android13's
[implementation](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/usleep.cpp)
normalizes microseconds and directly returns `nanosleep` with no remaining-time
output. Durations at or above one second are valid, including UINT32_MAX.
Completion returns0 and preserves guest errno; a caught handler returns-1 with
Android EINTR4 even when the disposition contains SA_RESTART.

The budget uses a fixed active-monotonic deadline, with checked arithmetic.
Windows uses
[QueryUnbiasedInterruptTimePrecise](https://learn.microsoft.com/en-us/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttimeprecise),
which excludes sleep/hibernation and requires Windows10 or later. Linux uses
CLOCK_MONOTONIC. Generation-based relative waits recheck this deadline after
notifications. Blocked/ignored signals and spurious wakes neither interrupt
the call nor restart its budget. No timer-resolution or power setting changes.

The caller must supply its actual bound SignalHost token, a delivery boundary
and an explicit admission policy. New `DispatchOneAdmitted` atomically rejects
eligible excluded bits before consuming any pending signal or information.
Legacy `DispatchOneAllowed` retains its selection behavior. An unsupported
phase, stale/foreign owner, clock failure or host exception is a named fatal
import boundary; exceptions cannot unwind through translated LLVM.

The provider preserves native errno, floating environment and Windows
LastError. After actual handler delivery, it reapplies the interrupted guest's
current rounding mode. Guest-memory effects belong to the real handler and
configured errno sink, rather than to a fabricated acknowledgment or timeout.

The game adapter admits zero signals at this timed-delay boundary. Its only
qualified collector delivery phase remains the finalizer's exact condition
wait and nested restart scope. The adapter and its forwarding Runtime outlive
worker drain. Its log records actual original call arguments and return values.
Original head825b3860 polls acknowledgment semaphore87cb1e68, calls
usleep(3000) at825b3948 and polls again; the sleep provider neither consumes
the semaphore nor posts to it.

Qualification5 acceptance SHA256 is
`aabf579f56b5b2bd81c4716bd713209319bd8a679271b69ece60f0219067f1b3`;
held receipt `work/signal-sleep-held5.json` SHA256 is
`53c4eb66e9440bda4fb20f5eaca5fa3da10a7eb64aeeef144b2bc54a7a1f067e`.
Independent component peer `work/usleep-final-peer1/peer.json` SHA256 is
`e3efafbc4b4143d62d8ac062f2ab05222940fe6ba6212b3f7a3001b74bde8241`.
The final component/wiring peer SHA256 is
`d8eb1ec5826ba3b86022d894323bb2ae8355a67530876c5879bfcede38623ce0`;
static/source/capability acceptance SHA256 is
`20681ff9716c065af9e382b367d4b2137a23233152cf68d212e2bb4cace2b5aa`.
Actual NDK/Bionic ARM64 and both translated hosts match16 normalized call
records, including direct/indirect calls, poisoned upper X0 bits and interrupted
UINT32_MAX. Each translated host passes176 focused checks with10 heads/two
objects, real SignalDelivery handlers, both SA_RESTART modes, blocked/ignored
signals, spurious/enrollment wakes, mixed excluded-signal races, retained
siginfo, native environment restoration and foreign/retired owners. Two real
fatal subprocess boundaries per host check excluded admission and unknown
exceptions. Existing default signal/semaphore checks159 and allowed-dispatch
regressions also pass with the new core. Runtime imports retain their existing
exclusive-reservation invalidation on both normal and interrupted calls.

Earlier attempts remain preserved: underaligned native Bionic TLS; an incorrect
fixture expectation that reservations survive imports; a missing MinGW precise
clock import; and Kernel32 lacking the actual forwarding export on this host.
The final provider resolves the same precise API from loaded KernelBase,
which [Microsoft's API metadata](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttimeprecise.md)
lists. No lower-precision clock is substituted.
The controller takes an explicit `--preparation` directory, plus `--out`,
`--ndk` and `--toolchain`, so it can replay the frozen preparation from the
repository rather than depending on the controller's scratch location.

This qualification changes no game inputs or collector admission. Physical
suspend/resume, edited signal-context rounding, an executed game usleep,
completed collection, managed retention, successful initialization and a
rendered frame remain outside its evidence.
