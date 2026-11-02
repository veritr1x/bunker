# Optional real worker lifecycle transport

`Pthreads::SetWorkerLifecycleHooks` installs one immutable opt-in hook set before
the first Create attempt, including an invalid attempt. The default has no
hooks and retains the existing callback policy. Hooks do not create collector
records, attach Java threads, enable polls or deliver signals.

The creator receives the actual reserved child token, allocated guarded guest
stack and TLS block. Native TID is zero until native launch. Its prepare callback
can register SignalHost(child,parent) now, so inheritance copies the creator's
mask before publication/resume. Child entry binds the actual Windows worker and
checks the actual native TID before any guest instruction. Tokens remain unique;
no Windows thread ID is used as a recycled virtual identity.

Prepare returns a passive shared lease. If it throws, explicit cancelled
retirement receives an empty lease and the same token, allowing rollback of a
partially prepared owner record. Later creation failures cancel the successfully
prepared lease. Callbacks and final lease destruction run outside the Pthreads
registry/once locks; cancellation revokes ownership before stack destruction.
Creation cancellation runs on the creator. An enter failure cancels on the
actual child before guest entry, then remains a fatal worker diagnostic.
The hook setter and first-attempt freeze are synchronized under the registry.

Normal return and pthread_exit converge on Finish: before_tls checks owners,
active once ownership is released, and all four TLS destructor rounds execute
with worker identity/stack/signal/nonlocal capabilities still alive. Explicit
normal retirement then revokes those capabilities before completion becomes
visible. The stack allocation remains owned until actual OS termination and
Join/detached reaping. pthread_exit uses _endthreadex and bypasses C++ unwind,
so retirement does not depend on an automatic destructor. Recursive/repeated
Finish is an explicit unsupported diagnostic. External UI/UnityMain lifetimes
remain separately owned and are not automatically hooked.

The optional fourth constructor argument validates TLS destructors. It defaults
to the existing translated-entry predicate. Only KeyCreate and TLS invocation
use it: Create, Once and public Run still require translated entries. This
allows a caller to prove the exact installed LibC::free(void*) marker while
rejecting arbitrary providers and free used as a worker start/once initializer.
Provider/module owners must outlive every actual destructor; hooks must not
dispatch signals inside an allocator or another provider's critical section.

`test_worker_lifecycle.py` creates a new frozen focused build from a committed
host plus only these held provider/fixture sources. Actual Android NDK callers
exercise normal return, pthread_exit, exit from once, nested workers, detached
workers, four reinserting destructor rounds, and actual installed free. The
coordinator uses real SignalHost registrations and declared stack jmp_buf
lifetimes, copying masks at creation, revoking automatic-object permissions
before TLS callbacks, and dropping saved contexts at retirement. A defined
prepare veto tests cancellation without forcing a kernel resource failure.
That veto calls Create directly from the host C++ test and catches there; no
C++ exception is allowed to unwind through translated nounwind code. Actual
NDK pthread_exit cases separately execute their real nonreturning API path.
Stale tokens/contexts, default validator behavior, role restrictions and hook
configuration freezing are checked, including16 actual setter/Create races.
Explicit attributes produce64KiB stacks; the nested attr=null child retains its
real default1MiB stack. The original unchanged pthread NDK fixture
and regression runner are also built against the frozen new provider.

These checks qualify lifecycle transport only. Existing game cohorts remain
unpolled; nonzero signals still require an independently qualified instrumented
joint cohort, same-worker delivery, and safe native-provider root/wait policy.
