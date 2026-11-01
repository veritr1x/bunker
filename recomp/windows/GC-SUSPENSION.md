# IL2CPP GC suspension: evidence and implementation requirements

**Status: signals and GC suspension are unimplemented.** Nonzero
`pthread_kill` and `pthread_sigmask` are not a working stop-world mechanism.
The current Windows startup/resource gates do not establish GC correctness.
The linked collector resembles upstream Boehm's POSIX implementation, including
its resumed-epoch bit, but its exact version has not been proved.

## Actual binary behavior

These are RVAs in the inspected `libil2cpp.so`, before the loader base is added.
The ignored `work/gc-signal-audit.json` contains imported call sites, FDE bounds
and disassembly. Conclusions below also include direct examination of the
wrappers and ELF initial data.

| RVA | Observed role |
| --- | --- |
| `0x25b3020` | GC signal/semaphore initialization |
| `0x25aad50` | Stop wrapper: increments epoch by **2**, publishes stopped state, sends suspension requests and waits for acknowledgments |
| `0x25aae3c` | Resume wrapper: clears stopped state, sends restart requests and waits for acknowledgments when retries are enabled |
| `0x25b2ca4` / `0x25b2d18` | Suspend-all traversal / `pthread_kill` call |
| `0x25b2f00` / `0x25b2f70` | Resume-all traversal / `pthread_kill` call |
| `0x25b2af4` | Suspend frontend: checks signal number and saves/restores errno |
| `0x25b2b4c` | Suspend body: finds the current GC thread, publishes stack position, acknowledges, then waits for restart |
| `0x25b2c70` | Restart handler: checks signal number and returns |
| `0x25bea74` / `0x25beb3c` | Guest `sigaction` wrapper / handler-dispatch thunk |
| `0x25b2da4` / `0x25b2e84` | Timed acknowledgment/retry path / blocking acknowledgment wait |

Initialization selects suspension signal **30** and restart signal **24** when
their configured globals are `-1`. The suspension action uses `0x10000004`
(`SA_RESTART | SA_SIGINFO`); the restart action clears the `SA_SIGINFO` value
`4`. Both masks initially exclude signals 2, 3, 6 and 15 from a full mask.
The temporary `sigsuspend` mask additionally unblocks restart signal 24.

Important global RVAs:

- `0x7984e10`: retry setting, initialized to **1** in this binary. An absent
  `GC_RETRY_SIGNALS` environment variable therefore leaves retries enabled;
  the explicit value `0` disables them.
- `0x7984e14` / `0x7984e18`: suspend/restart signals, initially `-1`.
- `0x79a6b08` / `0x79a6b10`: stop epoch / world-stopped flag, initially zero.
- `0x79a6b18` / `0x79a6b28`: suspend wait mask / 256 GC-thread buckets.
- `0x79a7698`: original-handler table used by the guest dispatch thunk.
- `0x7cb1e68`: acknowledgment semaphore.

The suspend body uses `pthread_self` to find the **target thread's** record.
It stores its X29 in record offset `0x18`, posts the semaphore, and release-stores
the epoch at offset `0x10`. After restart, retry mode posts a second
acknowledgment and stores `epoch | 1`. Thus default behavior requires **both
stop and resume acknowledgments**. Dead-thread error `ESRCH` is explicitly
handled by the send loops. Duplicate requests are checked against the epoch.

The separately observed SIGSEGV/SIGBUS registration at `0x25b1908` is gated by
`GC_LOOP_ON_ABORT`; it is a diagnostic path, not the normal suspend protocol.

## Independently checked Android wire layouts

The installed Android NDK **27.2.12479018** AArch64 compiler independently evaluated `sizeof`
and `offsetof` expressions from its actual headers, using stdin and LLVM IR
output. These are Android AArch64 layouts, not Windows CRT structures.
The signal/ucontext layouts are also consistent with the
[Android 13 Bionic headers](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/sys/ucontext.h).
The corresponding primary declarations are in
[`signal_types.h`](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/bits/signal_types.h),
[`semaphore.h`](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/semaphore.h)
and the [AArch64 signal context header](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/kernel/uapi/asm-arm64/asm/sigcontext.h).

| Type | Size / relevant offsets in bytes |
| --- | --- |
| `sigaction` | 32; flags 0, handler 8, mask 16, restorer 24 |
| `sigset_t` | 8 |
| `siginfo_t` | 128 |
| `stack_t` | 24 |
| `ucontext_t` | 4560; stack 16, mask 40, machine context 176 |
| `mcontext_t` | 4384; registers 8, SP 256, PC 264, PSTATE 272, extension area 288 |
| `fpsimd_context` | 528; vector-register payload 16 |
| `sem_t` | 16; `SEM_VALUE_MAX = 0x3fffffff` |

`SIG_BLOCK`, `SIG_UNBLOCK`, `SIG_SETMASK` are 0, 1 and 2. `SA_SIGINFO` is 4,
`SA_RESTART` is `0x10000000`, and `SA_ONSTACK` is `0x08000000`.
Re-probe the exact chosen NDK/Android target before introducing wire structs;
the installed NDK probe is not an execution test against an Android 13 kernel.

## Root visibility and safe delivery

The actual suspend frontend does **not** spill all interrupted registers. Its
inner function records an approximate stack position and relies on the full
interrupted context already being on that stack. This matches the assumption
documented in [upstream Boehm's POSIX stop-world code](https://raw.githubusercontent.com/bdwgc/bdwgc/v8.0.6/pthread_stop_world.c).

The proposed Windows route is cooperative delivery at compiler-inserted safe
points, followed by execution of the existing translated signal handlers on
the target thread's guest stack. Before acknowledging suspension:

1. Materialize the precise interrupted guest State, including X0–X30, SP, PC,
   PSTATE, Q0–Q31, FPCR/FPSR and TLS context. Optimized native registers/SSA
   temporaries cannot be reconstructed merely by reading a stale State object.
2. Build an aligned AArch64 signal frame below the interrupted guest SP. Keep
   the saved register context above the handler's recorded stack position so
   the collector's existing stack scan can find register-only roots. Preserve
   the frame chain, old mask and register values; provide the correct handler
   arguments and a controlled restoration route. Linux's
   [AArch64 signal implementation](https://github.com/torvalds/linux/blob/v6.1/arch/arm64/kernel/signal.c)
   is the primary frame/restoration reference.
3. Run the registered guest thunk/handler on the **same target worker**, with
   its original pthread identity, TLS and errno. Generic `Pthreads::Run` alone
   does not construct the required kernel-style frame. A host/collector-stack
   callback would publish the wrong stack and identity.
4. Let the actual handler publish its stack/epoch and acknowledgments. Resume
   through the guest restart handler, restore the saved state/mask, and clear
   the interrupted exclusive reservation. No provider or shared-memory lock
   may remain held while invoking handlers or parking.

Poll coverage must include pure guest loops and direct translated calls;
import boundaries and `Runtime::Dispatch` alone do not bound suspension
latency. The compiler must treat the slow delivery path as an observable State
escape, and optimized IR/native output must prove materialization. Do not let
read-none attributes or state-elimination passes invalidate that assumption.

Arbitrary `SuspendThread` cannot supply this guarantee and can freeze a worker
inside a host lock. [Microsoft explicitly distinguishes debugger suspension
from cooperative thread synchronization](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-suspendthread).

Native blocking providers require interruptible waits or explicit GC-safe
phases. Guest pointers held only in host temporaries need visible roots;
being inside a host import is not automatically safe for collection.

## Required virtual signal and semaphore semantics

- Process-wide dispositions and per-thread inherited masks/pending signals;
  positive pthread error returns and stable thread-token lifetime checks.
- Atomic temporary-mask replacement and waiting in `sigsuspend`, with mask
  restoration and `-1/EINTR` after a caught signal. A restart queued before
  the wait must not be lost. See [the Linux API reference](https://man7.org/linux/man-pages/man2/sigsuspend.2.html).
- Semaphore publication/acquisition ordering for both acknowledgment phases,
  absolute realtime deadlines, interrupted waits, and the binary's timeout
  resend path. Its deadline construction adds 10 ms without normalizing
  nanoseconds; the code explicitly treats `EINVAL` as a retry condition.
- Mask helpers and action queries must preserve the actual Android layouts.
  Unsupported signals, action modes, alternate-stack or context features must
  remain explicit rather than being reported as working POSIX behavior.

## Proposed gates before enabling GC

1. NDK/QEMU references for layouts, masks, pending/coalesced signals,
   `sigsuspend` lost-wakeup cases, errno restoration and semaphore error paths.
2. Optimized translated tight loops with no imports: bounded request latency,
   complete register/stack/TLS/FP restoration and exclusive-reservation clearing.
3. A root held only in an interrupted guest register remains visible to the
   real collector through the synthetic frame; removing the root later permits
   collection. Include SIMD/context snapshots and stack-boundary checks.
4. The real suspend/resume handlers publish in-range stack pointers, correct
   epochs and exactly-once acknowledgments across duplicate requests, retry
   timeouts, repeated cycles and restart-before-wait races.
5. Thread creation/exit, blocked-provider states, nested callbacks and host-only
   temporary roots remain safe without parking a worker while it holds a host
   lock needed by the collector or handler.

These are proposed implementation gates, not passed tests or a claim that GC
suspension currently works. No signal implementation was added by this audit.
