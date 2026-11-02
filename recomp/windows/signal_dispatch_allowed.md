# Atomic allowed-signal dispatch

`DispatchOneAllowed(token, allowed_bits, boundary)` intersects the allowed bitmask with pending/unmasked signals under the same SignalHost mutex before selection or consumption. Unallowed pending bits, complete Info and global NeedsPoll remain intact. Allowed0 does not dispatch; invalid/dead/wrong-owner statuses remain unchanged. No predicate callback runs under the mutex. Existing DispatchOne and Suspend use the all-bits default.

The focused test reuses the unchanged accepted Sender5 C++ stack/identity harness and its exact NDK core ELF/COFF/headers; no guest relift or instrumentation occurs. A new native import checkpoint calls the new API inside a materialized Runtime context and executes the actual existing NDK SA_SIGINFO handler through SignalDelivery. Queued24 remains intact while30 runs first;24 later receives its original complete sender Info. This is bounded component execution, not the game's collector protocol.

Direct tests cover allowed0, blocked masks, invalid/dead/wrong owner, default/all equivalence, standard-signal coalescing and concurrent queue/selection. The legacy signal/semaphore gate validates unchanged default DispatchOne/Suspend behavior. Source/old-input/tool hashes are frozen into a fresh ignored candidate. No game signal guard, GC record, pending acknowledgment or production root-admission policy is changed.
