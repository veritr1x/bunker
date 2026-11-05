# sched_yield host port

The Android LP64 import returns a signed 32-bit status. A successful yield leaves
guest errno unchanged. Windows performs one real `SwitchToThread` call: its false
result means no other ready thread ran, not a yield failure. Linux uses native
`sched_yield` and reports an actual native failure through the existing guest
errno sink. The Windows port makes no Linux scheduler-policy or fairness claim.

The focused gate uses one NDK-compiled direct/function-pointer caller in actual
static Bionic under QEMU and in the translated Windows fixture. It checks repeated
calls on the main thread and two real native workers, guest errno, signed status,
State1200/SIMD/high cells, and opaque Memory64 identity. A test-only registration
wrapper measures native errno, LastError, and floating environment at the genuine
provider callback, excluding Runtime scaffolding. No game, priority changes,
timing/fairness assertion, sleep fallback, or scheduler emulation is involved.
