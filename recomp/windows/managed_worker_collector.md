# Creator-certified managed-worker collector waits

`game_collector_delivery.h` admits a separate managed-worker role alongside the existing finalizer role. It provides bounded admission for managed-worker wait sites observed in original runtime 5 and runtime 6. It does not identify that worker as a finalizer or assume its unlogged managed task name.

## Creator and wait certificates

Both roles require the observed original creator call: return address `0x82556a64`, thread entry `0x82556a94`, and the creator record's function at `+0x10` equal to `0x82557c80`. Their payloads distinguish them:

| Role | Payload owner | Payload function | Payload argument |
| --- | --- | --- | --- |
| Finalizer | Nonzero | `0x825c3ed0` | Zero |
| Managed worker | Nonzero | `0x8258aa94` | Nonzero |

The role is captured by the actual Pthreads creator lifecycle and retained for that worker lifetime. A different creator, wrapper, function or payload remains unqualified.

| Role and phase | Import PC | Original return address | Additional certificate |
| --- | --- | --- | --- |
| Managed event timed condition | `0x7ffc60000028` | `0x82550574` | Actual provider deadline pointer and X2 both equal SP |
| Managed event untimed condition | `0x7ffc60000020` | `0x825505d8` | No deadline; X2 is unrestricted because the API has only two arguments |
| Managed NativeCond timed condition | `0x7ffc60000028` | `0x82550164` | Actual provider deadline pointer and X2 both equal SP |
| Managed NativeCond untimed condition | `0x7ffc60000020` | `0x82550174` | No deadline; X2 is unrestricted |
| Existing finalizer untimed condition | `0x7ffc60000020` | `0x825505d8` | Existing zero-X2 contract and original global finalizer event identity retained |

The event helper has a `0x70`-byte frame with FP equal to SP plus `0x60`, and mutex equal to condition minus `0x28`. The NativeCond helper has a `0x50`-byte frame with FP equal to SP plus `0x40`; its condition and mutex are independent pointers, with no event-offset assumption. All arguments must match the real provider context. Managed events are dynamic and are not equated with the finalizer's global event. Managed condition polling uses the separate controlled ordinal `UINT64_MAX - 4`; the finalizer keeps its previous ordinal.

## Original stop/restart and physical roots

The roles share the existing original collector protocol. Admission requires the real current worker/native thread, TLS, normal stack bounds and signal mask; a single active Runtime frame with no opaque parent continuation; and enough normal stack space for both signal frames. This profile requires a fresh disabled alternate signal stack.

A managed wait at an unknown return address, inside an opaque scope, or inside actual nested Runtime frames may complete ordinarily when no signal is pending. It publishes no live collector certificate or acknowledgment; any stale outer wait certificate is cleared until a fresh fully qualified checkpoint republishes one. A stable creator/lifecycle/original-registry certificate authorizes a real managed-worker send independently of receiver admission. No old wait State is retained or selected outside its provider scope. Unsupported blocking and retiring contexts still reject sends before Queue; a known pending request entering an unsupported wait fails closed. Classification starts with the known caller address, so bad FP, TLS, import PC or arguments at an otherwise eligible known site still fail strictly rather than being silently treated as ordinary. The finalizer retains its strict existing behavior.

Only the original coordinator's certified stop/restart send paths authorize registry inspection and delivery of signals 30 and 24. The original handlers publish the record epoch/frame and perform their own semaphore posts. Before those posts, the adapter checks that all 31 interrupted general registers and all 32 Q registers are physically present in the original scan range. Transport wakes request polling; they do not signal a guest condition or acknowledge collection.

The Pthreads provider retains its real copied absolute deadline and pinned mutex control. Its optional trailing `WaitHooks::finish` callback runs at two real retirement boundaries, outside provider locks with the original State/arguments and resource pins live: after the wait decision before condition-ticket removal, and before each free-mutex ownership claim. The latter rechecks ownership after the callback; another thread winning the mutex returns the waiter to genuine reacquisition.

For managed workers, a per-owner claim spans sender validation through actual signal Queue and Notify. Retirement takes the same claim. If no request is pending it withdraws the live wait certificate; if a queued request won, it releases the claim and runs the real qualified checkpoint/original handlers before retrying retirement. The claim is never held across guest delivery or `sigsuspend`, so the restart sender can proceed. A finish callback can withdraw admission without retiring the owner. A later genuine managed-worker send may queue for the next certified context; it cannot run against the withdrawn State. Actual owner retirement or an unsupported blocking phase still rejects sends before Queue, without an acknowledgment.

Handler duration still counts against the original absolute deadline. The actual timeout/notification decision and mutex reacquisition are retained; no timeout resets, synthetic phases or guest wakes are introduced. Ordinary unqualified waits and the legacy finalizer do not acquire new collector admission from this callback.

The finish callback and the appended mutex selector default empty, preserving old two- and three-member aggregate source initializers. `WaitHooks` is a changed C++ layout/value interface, so all consumers must be rebuilt together; old compiled consumers cannot be mixed with the new provider. Guest State/wire layouts and translated guest objects remain unchanged.

## Fresh mutex contexts between waits

Runtime 10 reached a genuine stop request after a managed worker had returned timeout 110 and left its old condition-wait scope. The former active-wait requirement rejected that timing before Queue. Stable worker ownership and sender certification are now separate from the strictly scoped receiver State/checkpoint. Real queued 30/24 bits and transport hints can persist between supported providers. No compiler trace/backedge becomes a delivery site and no host acknowledgment is generated.

Three original `pthread_mutex_lock` sites have fresh controlled admission:

| Return address | Frame | Additional actual argument certificate |
| --- | --- | --- |
| `0x8255045c` | `0x70`, FP = SP + `0x60` | Event mutex X0 = X19 = X21 + 4 |
| `0x825bf1cc` | `0x60`, FP = SP + `0x50` | Queue mutex = original global `[0x879a78c0]` + `0x20` |
| `0x825bf018` | `0x60`, FP = SP + `0x50` | Same original queue-mutex identity |

All three require observed import PC `0x7ffc60000030`, the same real entered managed worker/native thread, a single current Runtime State, no opaque continuation, owned normal stack/TLS, disabled alternate stack and the existing signal-mask/physical-root checks. `WaitPhase::MutexLock` has no condition or deadline pointer. Only the actual current provider invocation can publish its State; provider exit withdraws and clears it.

The optional fourth `Pthreads::WaitHooks::admit_mutex` selects this path. Default, nonadmitted and try-lock paths retain the ordinary mutex implementation. A selected lock pins the real mutex control and a real waiter/channel through the complete operation; destruction remains busy while enrolled. Checkpoint/finish/generation/wait callbacks execute outside provider locks. Real mutex unlock and collector notification wake the same generation channel. After a finish callback, ownership is rechecked before the provider makes its genuine claim; competing ownership sends the target back to waiting. A transport wake never returns a fake lock success or signals a guest condition. There is no new timeout or reset of an earlier condition deadline.

Managed sender validation holds a shared owner/context and the per-owner claim through original record/epoch/caller checks, actual Queue and Notify. TLS/retirement and unsupported blocking-phase transitions take the same claim. Receiver delivery still requires fresh admission and the original 30/24 handlers and posts. A late known bit remains queued when no fresh original stop epoch is certified; unknown eligible bits fail atomically without consuming known bits. No pending bit or signal info is discarded to make shutdown pass. An actually retiring owner with pending delivery is explicitly unsupported.

The creator wrapper `0x8258aa94` can invoke arbitrary managed callbacks, so this is not a universal progress guarantee for all running workers. Queue-only deferral to a later condition wait would be insufficient when a stopped thread owns an intervening mutex; the controlled contention checkpoints address the audited three-site family. Unknown blocking operations remain fail-closed. The new focused gate is separate from the historical Q9 evidence below and must qualify changed roots after a completed timeout, a genuinely contended fresh mutex, two original posts and real unlock before successful acquisition. No new game/frame claim follows from this implementation.

## Qualified mutex extension

The current focused Windows gate is `recomp/work/managed-worker-collector-qualification12/acceptance.json`, SHA-256 `041760b89056e309fc2f465360bf3d3649159c148f0cbd2ee43dae16ebe35630`. It binds the held collector/Pthreads source triplet and completes **1,037 focused checks**, twelve original stop/restart cycles, twenty-four original semaphore posts and twenty-four physical GPR/Q root-frame checks, plus the retained ordinary-provider regression's **397 checks**.

Each of the three new `between-*` cases completely returns the prior real timed wait with result 110 and leaves that old context. A deterministic barrier then permits the original coordinator's genuine signal Queue before fresh mutex admission. The target changes its interrupted GPR/Q roots and enters a genuinely contended real mutex. Independent TryLock/Destroy checks observe the real busy mutex/control pin outside provider locks. The original stop/restart handlers perform their two posts, and only an actual owner unlock permits the new lock call to return 0. No prior wait result, old State or old root canary supplies this positive evidence.

Fifteen negative controls retain wrong creator/owner/context checks and add actual-worker-retired, unknown mutex caller, bad fresh FP and bad TLS cases. Unknown/opaque/nested zero-GC waits and the original finalizer profile remain covered. The test fixtures own creator-shaped input and helper-shaped State; retained original coordinator/handler bodies execute, but the complete original managed callback/trampoline, heap scanning/reclamation and game rendering do not. The earlier Q10/Q11 fixture failures are preserved separately; they did not change the held production triplet. This acceptance does not establish a generic asynchronous-stop mechanism, universal worker progress, game startup completion or a first visible frame.

## Historical qualified scope (before mutex extension)

The source-only whole-file inverse and syntax evidence is `recomp/work/managed-worker-collector-source-preparation3/source-proof.json`. The packet binds the collector header and both Pthreads source/header files. The collector header SHA-256 is `501b3ef49fbc149c9599b189da0bf27cb31cca34c9de5aba4e27a7f30f292c27`. The source proof SHA-256 is `4395078a459c71257028f31b753a836ab03c842622870882022db7f3384081e1`. Original worker/phase provenance is recorded in `recomp/work/firebase-runtime5-worker-provenance1/acceptance.json` and `recomp/work/runtime6-managed-wait-boundary1/acceptance.json`.

The completed native gate is `recomp/work/managed-worker-collector-qualification9/acceptance.json`, SHA-256 `eb590824c08a6661925b74799b49ac6abed63935002c5ba9691c8bb3bc940f24`. The reproducible fixture/controller are `game_managed_worker_collector_test.cpp` and `test_game_managed_worker_collector.py`. Its **853 focused checks** cover:

- Five qualified profiles: managed event timed/untimed, managed NativeCond timed/untimed with independent buffers, and the retained finalizer profile. Together with the two forced races, these perform nine original stop/restart cycles, eighteen original posts and eighteen physical GPR/Q frame checks.
- Deterministic sender-before-Queue barriers at both retirement boundaries preserve the real timeout result 110 and notification/reacquisition result 0. A retirement-first control rejects the actual sender before Queue.
- Three ordinary zero-GC waits: unknown caller, opaque scope and actual nested Runtime frames. Each completes with no pending signal, collector sends or posts.
- Interrupted FPCR/FPSR, status and TLS checks, plus 28 checkpoint and 24 finish native-environment checks, and twelve interrupted FPCR/FPSR checks.
- Twelve fail-closed subprocesses covering creator function/owner/argument/wrapper, event and NativeCond FP/TLS, timed request pointer, sends after unknown/opaque deferral, and the retirement-first sender.
- The existing actual-NDK Pthreads wait regression, executed once against the changed provider, passes 397 checks.

The fixture owns its initial registry, creator-shaped payload and interrupted helper-shaped State. It executes retained original coordinator/handler code and genuine Windows Pthreads waits; it does not execute the complete managed trampoline/helper, heap scanning/reclamation or the game. That historical gate admitted only the four exact managed condition-return sites and retained finalizer profile; its retirement-first rejection is superseded for still-live managed owners by the separately tested mutex extension, rather than being relabeled as a new positive result. Ordinary completion grants no admission to arbitrary workers, compiler poll sites, unsupported root contexts or asynchronous native callbacks. This gate establishes neither game startup completion nor a visible first frame.
