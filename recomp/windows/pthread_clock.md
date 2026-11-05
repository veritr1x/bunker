# Focused clock resolution provider

`clock_getres` supports the explicitly qualified realtime (0) and monotonic (1) clocks. It delegates to the same native Winpthreads clock family used by the existing `std::chrono` clock sampling paths. Existing `clock_gettime` bodies and IDs 0, 1 and 7 remain unchanged.

The focused Windows gate uses genuine direct and function-pointer NDK callers, independent native resolution queries, NULL and error ordering, exact Android LP64 16-byte writes, unaligned/page-edge canaries, protected pages, and guest error checks and native error/floating-environment checks seeded immediately around the genuine registered import callback by a test-only `Runtime::AddImport` link wrapper. Runtime dispatch clears exception flags before callbacks; that scaffolding is excluded from the query guarantee. Existing Pthreads::Run setup is outside that query contract. An actual static NDK/Bionic executable runs under QEMU/Linux for ABI and calling-contract checks; its kernel resolution values are not a Windows-resolution oracle. The reference has a genuine aligned, used TLS canary and does not fake Bionic TLS.

The acceptance receipt records actual checks and artifacts. Concurrent changes to output page protection are outside the qualified copy scope. This gate does not replay the full pthread campaign or execute the original game.
