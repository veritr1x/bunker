# Opt-in compiler/runtime cooperative polling

Build `poll_instrument.cpp` against LLVM18, then pass its executable through
`compile.py --poll-instrument`. The compiler freezes and hashes this binary
alongside the lifter/semantics, records `cooperative_polls` in the manifest and
keeps instrumented/uninstrumented shard caches separate. Default engine builds
are unchanged. Link `cooperative_poll.cpp` for instrumented objects.

```sh
python recomp/whole/build_poll_instrument.py --out /path/to/poll-instrument
# Add --poll-instrument /path/to/poll-instrument to the usual compile.py command.
python recomp/whole/test_cooperative_poll.py --lift /path/to/remill-lift-18
# Add --windows for the native PE gate.
```

The pass adds opaque predicates at trace entries and the source blocks of DFS
backedges. Removing those edges makes each CFG component acyclic, including
irreducible loops and disconnected components. Slow paths explicitly escape
the State pointer. Old effect/argument assertions on translated definitions,
declarations and direct call sites are removed. Four exact boolean identity
helpers are inlined to avoid accidental opaque barriers in the loop proof.
The predicate is conservative and can force register spills even when false;
performance optimization is future work. LTO/state-elimination pipelines have
not been validated for this contract.

`PollBinding` surrounds `Runtime::Run` on the actual target worker. A shared
`PollRequest` accepts monotonic requests from other threads. A delivery receives
the captured epoch, static trace/site identity, materialized State and the
active Runtime State chain, innermost first. Requests arriving during delivery
remain pending. Acknowledgments survive rebinding; throwing callbacks retain
the request. Bindings are exclusive and nested bindings restore their parent.
Nested guest calls made inside a callback do not recursively deliver the same
binding. No memory lock is held during callbacks. Explicit delivery clears the
exclusive reservation; fast checks do not.

Entry delivery uses the real incoming `program_counter` argument before
Remill's prologue PC store; stale caller State.pc is not reported as the
interrupted instruction. GPR/SP/FPCR edits can affect resumed execution;
PC redirection is explicitly rejected because it would require changing the
compiled continuation. Callback errno and host fenv disturbances are contained,
with guest rounding reapplied from the resumed FPCR. A nested Runtime call
retains all parent State pointers, including roots absent from the child.
Native provider temporaries are **not** enumerated by that chain.

The exact Game17 source cohort has now been mechanically instrumented without
relifting or refreshing its mixed frozen semantics:3575 objects,456684 trace
entries and122086 cycle-cut blocks. Every original per-object head/error set
and reachable State graph is unchanged, and actual new COFF symbols close the
same79436 direct targets. Static acceptance is
`work/game17-polled-cohort1/acceptance.json`, SHA256
`0a5e6b164855d7c745962ec744d2e7bf1c7209a679065cc117c0575446d9687d`.
Original objects, IR, caches and tool snapshots remain intact.

Game19 links that complete new cohort and passes default/init/surface profiles.
Its separate muted frame retry repeats original resume/master mute, nine IL2CPP
constructors and the actual finalizer condition-wait observation, then reaches
the unchanged nonzero signal30 guard. No PollBinding is installed; this qualifies
insertion/link/startup compatibility through that boundary, not production
suspension or GC roots. See [the game audit](../windows/game_bootstrap.md).

`PollBinding` also accepts an optional read-only admission policy. Its borrowed
context contains the materialized State, a const State chain, the captured site
and epoch, and the authoritative `program_counter`. At a trace-entry site the
State's PC still precedes Remill's prologue update; admission must use that
separate PC field rather than assuming State.pc already names the entry.
Returning false or throwing defers the request without invoking the handler,
acknowledging the epoch, clearing an exclusive reservation, or editing State.
Native errno and the exact native floating-point environment are restored on
that path. A later admitted poll on the same worker handles the pending request.
The policy must be bounded and read-only, without locks, parking or guest calls.
An absent policy retains normal delivery. This option does not publish provider
roots, make a native wait interruptible, or enable production signal delivery.

The gate runs production compiler objects and verifies optimized IR/native hook
retention, coherent loop State, same-worker delivery, nested roots, reservation
invalidation, epochs, failed callbacks and FPCR changes. Separate LLVM fixtures
check irreducible/dead cycles, stale attributes and duplicate instrumentation;
cache checks exercise mode changes and repair. Runtime exclusive regression
checks remain passing on both hosts. Linux and native Windows each pass
**27,349 checks / 260 same-worker pauses**, plus **97 exclusive runtime checks
and five rejection cases**. The loop exercises all four guest rounding modes.

This is not enabled on Unity/IL2CPP snapshots and is not signal delivery or GC
suspension. Production integration still requires signal policy, real target
stack frames/return context, provider transition roots and interruptible waits.
Callbacks must not park while a caller holds a lock needed by the collector or
handler. Merely being in a provider or a nested callback does not establish
that it is safe to collect.
