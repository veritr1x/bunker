# Optional actual worker signal lifetimes

`WorkerSignalLifecycle` supplies the four existing Pthreads worker hooks. The
caller takes them once, optionally composes ownership/observation checks, and
installs them before the first Create attempt. It registers each real child on
the creator, so mask inheritance is captured before native launch; child pending
signals and alternate-stack registration start fresh. Actual child entry binds
the policy to that native worker. This does not create GC records, attach Java,
bind cooperative polling or deliver signals.

The passive context retains the actual signal-thread reference, wake channel
and an initially unused PollRequest through all guest TLS destructor rounds.
Before-TLS marks the context finishing; genuine TLS callbacks can still borrow
a same-worker Use guard. Normal retirement drops the signal token only after
those callbacks and after all Use guards return. An active guard prevents
retirement, including an attempted pthread_exit through a future active signal
frame. Ordinary pthread_exit with no guard remains supported: its committed
termination path need not unwind Runtime's native scopes before the retire hook.
Guard release on another native thread, or counter underflow, is fatal without
provider cleanup. Use destructors only release passive ownership/counters.

Cancellation handles creator-side creation failure and actual-child enter
failure, including an empty lease after partial preparation. The token ledger
precedes registration; no unknown or failed unowned registration is dropped.
SignalHost calls execute outside the adapter ledger lock. Context and shared
state destructors call no providers. The caller must perform real Shutdown,
then CloseAfterShutdown before destroying the adapter/SignalHost. Captured
closed hooks reject future preparation before touching SignalHost; parent UI
and UnityMain registrations remain separately owned.

Lookup and AcquireUse take the adapter mutex. They cannot be called from the
lock-free PollBinding Admission policy. Capture a context/use before that phase
and let admission read already-published owner-local metadata. This adapter
does not prove provider root publication, safe wait interruption, original GC
deregistration, late-stop ordering or collector correctness.

The isolated Windows gate uses an actual NDK-built worker, nested child,
pthread_exit and TLS destructor reinsertion through four real rounds. It checks
creator-time mask timing, child pending zero despite parent pending, disabled
alternate stack, real SP/TLS/token/native identity, final TLS before ESRCH,
foreign/stale Use rejection and retained passive context behavior. A genuine
Shutdown-to-NDK-Create failure checks rollback. The separately labelled native
host preparation-throw test never unwinds C++ through lifted LLVM. Fatal child
enter cancellation, active-use exit and foreign release are separate named
native abort subprocesses. Immutable candidates preserve exact sources and
tool/artifact hashes; no game or original collector execution is claimed.
Captured closed base hooks are also invoked after their original adapter and
SignalHost have been destroyed, using actual retired worker metadata; the closed
guard must reject before dereferencing the expired provider dependency.

The accepted `work/worker-signal-lifecycle4/acceptance.json` SHA256 is
`2cbb01b03b7388712bcac9427811f01134c72d2867c6e651abf66df7903b2080`.
The actual Windows run passes270 checks over15 translated heads/two objects,
four real workers and three separately observed native abort boundaries.
Independent review revalidates every executed input and confirms the frozen
support uses the earlier Pthreads implementation, excluding new wait overlays.
Composition with the new wait transport and the real game remains pending.
Earlier candidates remain preserved:1 is a fixture compilation error;2 excludes
a valid top-of-stack SP;3 captures a constructor-local mask by reference past
its lifetime. Candidate4 captures that mask by value and completes the gate.
