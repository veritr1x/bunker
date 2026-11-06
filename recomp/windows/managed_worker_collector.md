# Creator-certified managed-worker collector waits

`game_collector_delivery.h` admits a separate managed-worker role alongside the existing finalizer role. This closes the original runtime-5 boundary where a collector stop targeted a managed worker that was waiting in the original IL2CPP condition helper. It does not identify that worker as a finalizer or assume its unlogged managed task name.

## Creator and wait certificates

Both roles require the observed original creator call: return address `0x82556a64`, thread entry `0x82556a94`, and the creator record's function at `+0x10` equal to `0x82557c80`. Their payloads distinguish them:

| Role | Payload owner | Payload function | Payload argument |
| --- | --- | --- | --- |
| Finalizer | Nonzero | `0x825c3ed0` | Zero |
| Managed worker | Nonzero | `0x8258aa94` | Nonzero |

The role is captured by the actual Pthreads creator lifecycle and retained for that worker lifetime. A different creator, wrapper, function or payload remains unqualified.

| Role and phase | Import PC | Original return address | Additional certificate |
| --- | --- | --- | --- |
| Managed timed condition | `0x7ffc60000028` | `0x82550574` | Actual provider deadline pointer and X2 both equal SP |
| Managed untimed condition | `0x7ffc60000020` | `0x825505d8` | No deadline; X2 is unrestricted because the API has only two arguments |
| Existing finalizer untimed condition | `0x7ffc60000020` | `0x825505d8` | Existing zero-X2 contract and original global finalizer event identity retained |

For both managed phases, the original helper has a `0x70`-byte frame with FP equal to SP plus `0x60`. The actual condition and mutex arguments must match the provider context, with mutex equal to condition minus `0x28`. The managed event is dynamic; it is not equated with the finalizer's global event. Managed condition polling uses the separate controlled ordinal `UINT64_MAX - 4`; the finalizer keeps its previous ordinal.

## Original stop/restart and physical roots

The roles share the existing original collector protocol. Admission requires the real current worker/native thread, TLS, normal stack bounds and signal mask; a single active Runtime frame with no opaque parent continuation; and enough normal stack space for both signal frames. This profile requires a fresh disabled alternate signal stack.

Only the original coordinator's certified stop/restart send paths authorize registry inspection and delivery of signals 30 and 24. The original handlers publish the record epoch/frame and perform their own semaphore posts. Before those posts, the adapter checks that all 31 interrupted general registers and all 32 Q registers are physically present in the original scan range. Transport wakes request polling; they do not signal a guest condition or acknowledge collection.

The Pthreads provider retains its real copied absolute deadline and pinned mutex control. Handler duration counts against that original deadline, and the waiter genuinely reacquires its mutex. The extension does not reset a timeout, fabricate a wait phase or change condition notification behavior.

## Qualified scope

The source-only whole-file inverse and syntax evidence is `recomp/work/managed-worker-collector-source-preparation1/source-proof.json`. The admitted header SHA-256 is `e2bda8d441a9aff22a2d53d8b5eddd755e758082786e238ffa451a1dc4a5c869`. Original worker/phase provenance is recorded separately in `recomp/work/firebase-runtime5-worker-provenance1/acceptance.json`.

The completed native gate is `recomp/work/managed-worker-collector-qualification4/acceptance.json`, SHA-256 `7aa563183156809ae919f4b9fcf885a9c54b01ff7123b053d5c9af637b8bb685`. The reproducible fixture/controller are `game_managed_worker_collector_test.cpp` and `test_game_managed_worker_collector.py`. Its **253 checks** cover:

- Two managed timed cycles: expiry against the original deadline and real condition notification followed by mutex reacquisition.
- One managed untimed cycle with residual X2 equal to 1, and one retained finalizer untimed cycle.
- Four original stop/restart cycles, eight original posts and eight physical GPR/Q frame checks; interrupted FPCR/FPSR, status and TLS restoration; and eleven native-environment checks at the actual production checkpoint boundary.
- Eight fail-closed subprocesses: wrong payload function, zero owner, zero managed argument, wrong creator wrapper, wrong wait return address, wrong FP, wrong timed request pointer and wrong TLS.

The fixture owns its initial registry, creator-shaped payload and interrupted helper-shaped State. It executes retained original coordinator/handler code and genuine Windows Pthreads waits; it does not execute the complete managed trampoline/helper, heap scanning/reclamation or the game. Arbitrary workers, compiler poll sites, waits and asynchronous native callback roots remain outside this admission. This gate establishes neither game startup completion nor a visible first frame.
