The optional poll admission gate defers delivery before State PC normalization, reservation invalidation, handler execution or request completion. False and throwing decisions retain pending requests and restore the exact native errno/fenv, even when guest FPCR specifies a different rounding mode. Admission is bounded and read-only; it does not establish GC or provider-root safety.

The new fixture uses a direct C++ Runtime protocol trace to distinguish policy mutation from normal translated prologue PC stores. It verifies false/standard/nonstandard-throw decisions, stale entry PC versus authoritative context PC, whole-State identity, actual exclusive reservation survival, reentrancy suppression, coalescing/rebinding and requests arriving during decision/handler.

Actual instrumented NDK-assembled exclusive loops distinguish reservation survival on deferral from normal clearing on acceptance. A real ModuleRegistry invokes nested translated constructor/finalizer loops under its recursive lock. An explicit test opaque-depth policy declines there, preserving parent/child State and pending requests; the same worker admits after returning and unlocking. Independent registry readers and tracked writes progress during permitted handler parking. This proves the supplied policy is respected, not that production phases can be inferred safe automatically.

The runner freezes exact production overlays and new tests, instrumenter/tool hashes and immutable generated outputs. Existing cooperative-poll regressions execute unchanged once per host inside a fresh copied support tree, preserving previous artifacts. No original GC handlers, records, collection, provider-root enumeration or game integration is claimed.

The accepted `work/poll-admission3/acceptance.json` SHA256 is
`07d29f0e085a721010801f084011e858379301757d8bf2ce1945e5368aa9d3ee`.
Focused gates pass1270 checks on Linux and3148 on Windows, with two exclusive
profiles and two registry phases on each host. Counts can vary with concurrent
request coalescing. The unchanged cooperative-poll regression passes27349
checks and260 same-worker pauses per host, including four FPCR modes and
optimized IR/native hook retention. Earlier candidates remain preserved:
candidate1 exposed an overly strict captured-epoch test assumption; candidate2
passed focused tests but could not set up the legacy runner's tool layout.
Only candidate3 completes both focused and legacy runtime gates.
