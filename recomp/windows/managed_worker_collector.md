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

A managed wait at an unknown return address, inside an opaque scope, or inside actual nested Runtime frames may complete ordinarily when no signal is pending. It publishes no live collector certificate or acknowledgment; any stale outer wait certificate is cleared until a fresh fully qualified checkpoint republishes one. The original coordinator still rejects a stop send to a target without that full live certificate. Classification starts with the known caller address, so bad FP, TLS, import PC or arguments at an otherwise eligible known site still fail strictly rather than being silently treated as ordinary. The finalizer retains its strict existing behavior.

Only the original coordinator's certified stop/restart send paths authorize registry inspection and delivery of signals 30 and 24. The original handlers publish the record epoch/frame and perform their own semaphore posts. Before those posts, the adapter checks that all 31 interrupted general registers and all 32 Q registers are physically present in the original scan range. Transport wakes request polling; they do not signal a guest condition or acknowledge collection.

The Pthreads provider retains its real copied absolute deadline and pinned mutex control. Handler duration counts against that original deadline, and the waiter genuinely reacquires its mutex. The extension does not reset a timeout, fabricate a wait phase or change condition notification behavior.

## Qualified scope

The source-only whole-file inverse and syntax evidence is `recomp/work/managed-worker-collector-source-preparation2/source-proof.json`. The admitted header SHA-256 is `5c039166efaec2be6bc3725210f4e56d18e0549c518b2f6967de3beba8e72fd0`. The source proof SHA-256 is `fe1adb97e12dc8d2b2ac76fb15a7a9d5c873231a736cb004a175060741252fb4`. Original worker/phase provenance is recorded in `recomp/work/firebase-runtime5-worker-provenance1/acceptance.json` and `recomp/work/runtime6-managed-wait-boundary1/acceptance.json`.

The completed native gate is `recomp/work/managed-worker-collector-qualification7/acceptance.json`, SHA-256 `3c57d34f6bf34773d68cf7053abaf278d2f646f34e6dd40324e9699db5e977a9`. The reproducible fixture/controller are `game_managed_worker_collector_test.cpp` and `test_game_managed_worker_collector.py`. Its **640 checks** cover:

- Five qualified profiles: managed event timed/untimed, managed NativeCond timed/untimed with independent buffers, and the retained finalizer profile. These perform seven original stop/restart cycles, fourteen original posts and fourteen physical GPR/Q frame checks, including real deadline expiry and notification/mutex reacquisition.
- Three ordinary zero-GC waits: unknown caller, opaque scope and actual nested Runtime frames. Each completes with no pending signal, collector sends or posts.
- Interrupted FPCR/FPSR, status and TLS checks, plus 26 native-environment checks at the actual production checkpoint boundary.
- Eleven fail-closed subprocesses covering creator function/owner/argument/wrapper, event and NativeCond FP/TLS, timed request pointer, and actual coordinator sends after unknown-caller or opaque-context deferral.

The fixture owns its initial registry, creator-shaped payload and interrupted helper-shaped State. It executes retained original coordinator/handler code and genuine Windows Pthreads waits; it does not execute the complete managed trampoline/helper, heap scanning/reclamation or the game. Only the four exact managed return sites and retained finalizer profile receive collector admission. Ordinary completion grants no admission to arbitrary workers, compiler poll sites, unsupported root contexts or asynchronous native callbacks. This gate establishes neither game startup completion nor a visible first frame.
