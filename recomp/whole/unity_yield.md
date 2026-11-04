# Unity contention-loop YIELD

The original function `703835a0..70383620` reaches `YIELD` at `703835e4`
(`3f2003d5`), followed by the original `B 703835f4` at `703835e8`.
The previous decoder rejected YIELD, leaving an invalid-instruction hypercall
and `__remill_error` at the advanced PC `703835e8`.

The local Remill commit `dc553cc7ce8cc85cda729648ce737fcaf4b77871`, directly
after `ed9800253c4b3eaa35f034240dafbb33eeb2273a`, changes two files:

- `TryDecodeYIELD_HI_SYSTEM` accepts the decoded instruction as ordinary
  fallthrough.
- `YIELD_HI_SYSTEM` selects the existing `DoNOP` semantics, preserving the
  architectural state, memory token and exclusive reservation.

Arm permits implementations to treat this scheduling hint as NOP. See the
[Arm employee explanation](https://community.arm.com/forums/f/compilers-and-libraries-forum/5694/usage-of-yield-instruction-in-arm-v8)
and [Arm's discussion of waiting and backoff](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/multi-threaded-applications-arm).
This repair makes no scheduler, delay or fairness guarantee.

`build_unity_yield_overlay.py` relifts only the complete selected function,
splices it into the retained 128-function shard at global object index129,
then instruments and compiles it. The other127 functions retain exact raw IR,
polled IR, complete native bytes and relocations. All other module text,
State types, existing helpers and direct guest-reference closure are checked.
The selected replacement preserves the original branch, retry loop, lock
operations, helper call and return. No runtime error fallback is changed.

`test_yield.py` executes the exact original16-byte interval
`703835e4..703835f4` on the NDK-built ARM reference through QEMU, and executes
raw and polled Windows/Linux projections of the complete candidate target.
The projection redirects only the private entry edge and inserts a capture at
the original continuation; its exact inverse recovers the full target.
The original branch skips the BL/MOV instructions, preserving their affected
register sentinels. Sixteen flag/register/vector patterns compare all800
architectural snapshot bytes, all1200 host State bytes, the opaque64-byte
memory token and64KiB each of data/stack canaries. Native x18/TLS are validated
locally before normalizing those platform-owned values for comparison.

Held evidence under `recomp/work`:

- `yield-preparation1/acceptance.json`: isolated source snapshot/build.
- `yield-identity1/acceptance.json`: exact two-source inverse, all1264 old
  compiled semantic functions and1424 selectors preserved, one YIELD selector
  added, and ten old/new YIELD/NOP/WFE/WFI/SEV decoder controls.
- `unity-yield-overlay1/candidate.json`: one-function replacement;127 unchanged
  neighbors and native projections.
- `yield-qualification1/acceptance.json`: sixteen records on each of ARM,
  Linux raw/polled and Windows raw/polled, with identical architectural digests.

These checks qualify the reached YIELD/branch interval. They do not execute
the complete lock function or its platform helper, acquire the game's lock,
scan/reclaim the original heap, or establish a rendered frame. Cohort selection
and the subsequent game launch are separate steps.
