# Socket wait collector composition

`GameSocketWaitCollector` brackets the actual descriptor import callable and
observes the socket provider's real copied request and readiness waits. It
adds no Runtime::Run, replacement State, pthread condition context or synthetic
syscall marker. `GameSocketWaitContext` is the distinct controlled phase at
ordinal `UINT64_MAX-3`.

The existing finalizer/ordinary-worker, Unity-wrapper-worker and attached-main
owners retain their original registry record, certified/begun epochs, pending
transport, delivery object and acknowledgment counters. Socket scopes add an
explicit branch rather than introducing a second epoch ledger or shadow poll
binding. This preserves late pending requests across socket provider calls.
The original condition, nanosleep and timed-futex branches remain separate and
require their existing independent regression gates after a production change.

An actual prepared worker or attached main lifetime must own the current native
thread and State. The provider's request identity must equal its retained native
request owner, and descriptor, operation, finite status and absolute deadline
must remain unchanged. Copied and Returned occur once; actual native wait
attempts produce Before/After observations. A handled interrupt before entering
the OS wait or expiration of the fixed deadline may instead produce Returned
without an invented After observation. Fast operations can copy and return
without any admitted checkpoint.

Before entering the slow poll path, the persistent owner verifies its genuine
original sender-certified epoch, stopped-world state, registry-lock witness
and matching original record. Ordinary flags2 use that record's real stack high;
main flags6 use the original main-stack global. Tokens, TLS, normal stack bounds,
frame space, signal masks and alternate-stack mapping ownership are checked.
Enclosing Runtime parents and opaque continuations are outside the profile.
The read-only admission callback accepts only the short-lived verified record
certificate and exact copied socket checkpoint. A transport hint by itself
does not clear reservations, consume signals or authorize delivery.

The actual original stop30 and nested restart24 run through the existing
SignalDelivery and original callbacks. Before each original acknowledgment
post, all31 interrupted GPR values and all32 Q registers must physically match
the genuine frame inside the original scanner's FP-to-high range. The adapter
does not create a GC registry record, change scan bounds, post on the original
semaphore, write collector epochs, or claim a collection completed.

Production admission additionally uses the pinned original Unity return-site
inventory for poll/select, connect, transfer and shared read/write operations.
An unknown lifetime or unlisted callsite gains no signal admission. The next
original-game run must report the actual socket caller identity and whether
its wait used an admitted phase; the earlier socket fatal did not record a
native TID or pthread token. Per-token/import identity logs sample the first64
calls and then every4096, preserving native errno, LastError and floating state.

Bootstrap supplies the shared descriptor import interceptor and wait observer
before provider installation. Notify, original sender, delivery, sem_post and
nested sigsuspend routing continue through the same persistent owners. The
provider decides syscall behavior from the genuine handled/restart result:
poll/select return EINTR after a real handled signal; transport wakes alone
cannot report interruption or readiness. All waits retain the original deadline
and descriptor/resource pins outside provider and guest-memory locks.

`test_game_socket_wait.py` freezes its provider-manifest hashes, collector source
closure, actual NDK caller ELF/translated objects and retained original collector
object in a fresh directory. Its labelled component fixtures exercise actual
NDK poll direct/indirect calls, real loopback readiness, two genuine original
stop/resume cycles per each of three actual lifetime modes, physical roots and
late requests across a Returned-to-next-wait transition. Negative controls use
the real copied observation to reject changed snapshots/deadlines, foreign
State/TLS/token, insufficient stack, unlisted production sites and nested Runtime
roots. A missing original sender certificate declines the actual slow poll with
the request and exclusive reservation intact.

Initial registry data and the NDK site policy are explicit TEST inputs.
Original Unity registration/trampoline, heap scanning/reclamation, game rendering
and real-game network connectivity are not exercised by this component gate.
The unchanged retained original coordinators and handlers perform the actual
acknowledgment posts and epoch transitions; loopback or component success is
not a first-frame witness. Final acceptance must bind the same five provider
source hashes used by the functional socket qualification.

The accepted component is `work/socket-wait-collector-qualification2`, receipt
SHA256 `02f9ca52206b5703a0cd8768462ea100ce8b8c5607087328eedbe69f8b5b78cc`.
It binds the same final five provider sources as functional socket
qualification6. Its three processes pass157 checks, six actual NDK poll calls,
six genuine protocol cycles, twelve original posts/physical root frames, and
twelve negative controls per role. The current-source legacy main-disabled,
main-enabled and worker-futex processes separately pass350 checks in
`work/socket-collector-regressions1`, receipt SHA256
`0d711835d0f01c5ad34587feead382af4588f4fddacf8e1eb3f2f39c40774a97`.
That regression cohort does not execute a standalone finalizer-condition
profile. The exact additive source inverses are recorded in
`work/socket-wait-source-preparation1/source-proof.json`, SHA256
`e1e2165c93b15501b6b4ad10bec8fe896c466c584af51b9f4d57e6938a456dcf`.
