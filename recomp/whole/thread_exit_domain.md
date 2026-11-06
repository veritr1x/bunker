# Worker exit after Runtime retirement

An installed `pthread_exit` import previously called native `Finish` while its
`Runtime::Run` was still active. The ordinary Unity worker collector correctly
rejected retirement because `CurrentExecutionState()` remained non-null. Normal
worker returns already reached `Finish` after Runtime retirement.

`ThreadExitDomain` permits an explicit terminal outcome only in a Pthreads worker
root and its known `pthread_once` initializer Runs. Every suspended Run must share
the exact domain, native thread, Runtime and Memory token, and be inside the
explicit guarded guest-call protocol. Ordinary or foreign Runs cannot grant this
capability. The request records the opaque exit result without restoring or
inventing architectural State.

The existing lifted call guards return through each native frame. The worker
shell consumes the outcome after all Runtime scopes retire, then runs the existing
`Finish`: abandoned Once initializers reset and wake waiters, TLS destructors run
on the owned guest stack, and same-worker collector retirement follows. TLS Runs
do not inherit a pending terminal outcome. Consumption checks both native-thread
and Runtime ownership. A changed Memory token fails closed.

The collector header and its quiescence/pending-delivery checks are unchanged.
This mechanism neither acknowledges signals nor relaxes collector retirement, and
does not use a C++ exception to unwind lifted guest code. Legacy unguarded exit
paths retain their previous behavior.

Qualification is split into reproducible components:

- `windows/test_thread_exit_domain.py`: real NDK guest calls through lifted guards,
  six native workers, normal/direct/volatile/Once/nested-Once/detached paths and six
  real TLS destructors; 110 checks. No guest statement after an exit executes.
  A queued real signal still rejects retirement. The old sources independently
  reproduce the original active-Runtime fatal.
- `whole/test_thread_exit_controls.py`: synthetic native traces exercise the real
  Runtime call protocol, ownership, nested domains, consumed outcomes and non-null
  Memory64; 113 checks and 18 negative controls. These are protocol controls, not
  original guest-function execution. The pre-fix foreign-Runtime consume failure
  is retained separately.
- Independent matching legacy fixtures cover pthread78, six-worker lifecycle566,
  and two original Unity worker GC cycles. Their accepted guest objects and the
  current collector header are linked byte for byte.

The current component receipts are under
`work/thread-exit-domain-qualification3` and
`work/thread-exit-controls-qualification2`. Source preparation is
`work/thread-exit-domain-preparation2/source-ready.json`, with exact byte inverses
against the selected observation build. To reproduce the primary fixture, run
`windows/test_thread_exit_domain.py --out <fresh-directory> --preparation
<preparation-directory>` under the configured WSL toolchain; the optional `--reuse`
uses matching compiled providers and recompiles changed sources. Then run
`whole/test_thread_exit_controls.py --out <fresh-directory> --qualified-workers
<primary-qualification-directory>`.

These component executions do not establish original-game shutdown success. That
requires the subsequent integrated executable and an actual game run.
