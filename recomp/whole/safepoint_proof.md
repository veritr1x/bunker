# Isolated cooperative State materialization proof

This experiment is opt-in and independent of `compile.py`, the production
runtime, and the shared Remill build. It does **not** implement virtual signals,
synthetic signal frames, collector root scanning, GC suspension, or safe parking
inside arbitrary host providers.

`test_safepoint.py` lifts an import-free ARM64 loop using a frozen compiler
snapshot. A standalone LLVM 18 tool instruments trace entry and natural-loop
backedge blocks in the emitted IR, before Clang 18 `-O2`. The current Remill
optimization stage only inlines semantics; the instrumented input has not
undergone State-eliminating native optimization. Optimized IR and native-object
disassembly are retained in `work/safepoint-{linux,windows}/guest`.
The isolated tool supplies the exact existing runtime implementations of the
loop's boolean flag/compare identity helpers; `-O2` must remove those calls.
Thus their opaque declarations cannot accidentally supply another barrier.
Only explicit poll hooks remain as native calls inside the hot loop; tracked
stack/output accesses and floating operations occur before or after that loop.

The fast check is a separately compiled, side-effectful runtime-private function
reading a thread-local binding and atomic request epoch. The slow call explicitly
passes `State *` with unrestricted memory effects. Neither hook is pure,
speculatable, inlined, or linked with LTO. This conservative fast-call barrier
may force substantial register spills and State traffic even without a pending
request. There is no fast-path performance claim.

The controller supports one bound worker and one coordinator in this test.
Release/acquire request epochs and parked/resumed acknowledgments prevent an
immediate next request from being lost during resume. The original worker copies
its complete State before acknowledging, then releases the private controller
mutex while waiting. The coordinator successfully performs tracked guest-memory
reads and writes while the worker is parked. No provider or guest-memory lock
is acquired by the poll path.

The test pauses once at entry and 64 times inside the import-free loop for each
of four FPCR rounding modes. It checks all 31 GPRs, all 64 SIMD lanes, changing
GPR and SIMD pointer roots, exact loop counters/PC/SP/NZCV, TLS registers and stack
contents. Slow work intentionally disturbs host errno and fenv; both must be
restored. A real guest FADD after the resumes independently checks rounding, and
the final guest code uses the preserved pointer roots. Initial SIMD sentinels
include NaN payloads to detect accidental floating-point conversion of bits.
Both Linux and native Windows passed **27,325 checks and 260 pauses each** with
LLVM 18 `-O2`, including the strengthened hot loop with identity-helper calls
removed. Each materialization request must acknowledge within the test's
three-second deadline; this is a regression bound, not a real-time guarantee.

Run from WSL with the repository's Python environment and LLVM 18:

```sh
python recomp/whole/test_safepoint.py --lift /path/to/remill-lift-18 --remill /path/to/remill-src
python recomp/whole/test_safepoint.py --lift /path/to/remill-lift-18 --remill /path/to/remill-src --windows
```

This proves the tested materialization barrier and same-thread pause/resume
protocol. General compiler poll coverage, irreducible loops, blocking-provider
phases, nested execution/lifecycle, signal-mask semantics, reservation clearing
on actual signal interruption, and synthetic ARM64 frame/root visibility remain
separate requirements described in [GC-SUSPENSION.md](../windows/GC-SUSPENSION.md).
