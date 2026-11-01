# Bounded target-thread signal-frame delivery

`SignalDelivery` connects the checked signal-policy, cooperative-poll and
AArch64 frame components. It remains outside the real Unity/IL2CPP harness.
This is a reusable normal-stack/normal-C-return boundary, not complete Linux
signal delivery or a working collector.

Create one boundary on its owning native worker with registered guest stack
bounds, the Runtime and a predicate for translated handler/return entries.
Its `Deliver` callback obtains the actual current Runtime State, serializes
the interrupted registers into tracked bytes below its SP, and runs the handler
in a separate State. Nested explicit delivery during `sigsuspend` creates
another frame below the handler's own SP, on the same worker and registered
stack. The handler's original TLS registers remain visible.

The caller supplies a verified translated normal-return entry. It is used as
the handler's LR and intercepted after normal C return, before that entry's
instructions execute. The boundary reads the actual guest-stack context bytes
and restores validated state/mask. This does not execute `rt_sigreturn`, a
custom restorer, `longjmp` or `setcontext`. Wrong-worker/outside-Runtime calls,
unsupported action modes, corrupted return SP/PC, PC redirection, non-NZCV
PSTATE changes and alternate-stack policy changes fail explicitly. Restoration
is transactional until validation completes. Normal guest stack bytes remain
after delivery, as they would after a kernel frame is popped.

The test builds an actual NDK stop handler, restart handler and import-free
worker loop. Compiler-produced optimized objects run natively. A stop signal
travels from the controller through PollRequest and the target's materialized
State into a real stack ucontext. The handler verifies/records live GPR/SIMD
roots, exact interrupted SP/PC, TLS, thread token and errno, posts an Android
semaphore, then waits in `sigsuspend` for a nested restart handler. It posts the
second acknowledgment and returns to the original loop. An unconditional first
wait explicitly handles a restart queued before the handler begins waiting;
the test fixture does not assume controller/worker scheduling order.

Both Linux and native Windows passed **over 300 checks and 16 stop/restart cycles**
with **12 translated traces / zero unsupported instructions**. The checks cover
normal loop completion after every cycle, coherent register roots physically
present in the stack frame, in-range handler SP/FP, exactly-once acknowledgments,
EINTR, nested frame return, virtual errno preservation and host fenv isolation.
These are NDK test handlers, not the game's actual collector handlers.
Three further runs on each host also passed. Exact protocol-check counts vary
with coalescing of extra poll notifications; acknowledgment counts remain exact.

```sh
python recomp/windows/test_signal_delivery.py --ndk /path/to/ndk \
  --lift /path/to/remill-lift-18 --remill /path/to/remill-src
# Add --windows for the native PE gate.
```

Production integration still needs pthread identity/lifetime hooks, truthful
siginfo identity, provider transition roots and interruptible waits. A provider
import boundary has a controlled host continuation; it is not an arbitrary
kernel interruption point. Parent Runtime State pointers do not enumerate roots
stored solely in native temporaries. No worker may park while holding a lock
needed by the collector or a handler. Actual IL2CPP suspension, collector root
retention/reclamation and engine integration remain required gates.

See the [signal policy](signal_host.md), [frame layout](../whole/signal_frame.md),
[poll contract](../whole/cooperative_poll.md) and [actual GC evidence](GC-SUSPENSION.md).
