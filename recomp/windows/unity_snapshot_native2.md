# Refreshed native Windows Unity snapshot

The `whole-unity-estimate-shift-trn` cohort has **59,610 traces in 469 AMD64
objects**, with **1,345 unsupported traces** and no unresolved direct targets.
It replaces the old 59,561-trace/1,774-unsupported cohort for the isolated
paused-startup gate. The old objects and executable remain preserved.

All old entries remain present. The 49 additional entries are exactly the
proved post-setjmp continuation roots. Original exports, imports, image span,
executable ranges, 417 initializers, two finalizers and recursive State layout
match the old cohort. Every object was checked for AMD64 machine type and
hashed. This cohort includes the validated reciprocal estimates, right shifts
and TRN semantics. Continuation availability does not implement longjmp.

One formerly clean trace, `0x705ee5b4`, now contains an unsupported helper
inline. This was checked with controlled lifts: added roots move its shard
boundary, removing a declaration that previously kept matrix helper
`0x7091bce0` separate. The standalone helper IR is byte-identical in both
snapshots. Its indexed FMLA at `0x7091bd08` (`4fa01234`) is unsupported in
both. The old caller was therefore not transitively executable either.

The native host was frozen from Bunker commit
`1942e24f1864ad686fb5b3d0ab0155d718e95d66` before concurrent provider edits.
Three separate native executions exit zero:

- All 417 constructors, JNI 1.6, 42 original ELF/DEX-verified bindings,
  JNI unload and two finalizers.
- The same lifecycle plus actual `initJni(Context)` using the real APK.
- The same initialization plus actual UnityMain surface attach/change/detach,
  observing two fromSurface, two acquire and four release calls on the real
  HWND-backed token, followed by orderly teardown.

No nativeResume, nativeRender, IL2CPP initialization or game frame is executed
by these three checks. The separate first-frame gate remains unfinished.

Frozen artifact identities:

| Artifact | SHA-256 |
| --- | --- |
| Original Unity ELF | `3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f` |
| Lifter | `fef25d09fac991d0a767a1444faef252f7cfd7453e5a89740fddeca5eff31b00` |
| Semantics | `39e5659ea73f3a236475a8e8fefd83b175590e58827e86327483c584928abb83` |
| Compiler pipeline | `ed45c09b1f3e9b1aabd487822b0a15f3f4e531f7f477cd5b04bbe7b7aebd9c24` |
| State layout | `ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d` |
| Native executable | `374b9cf0e3ac944604206a2673c6ab0756737f874c58fc26f342aa6a0cced6f2` |

Ignored evidence is under `recomp/work/unity-native2-lineage/` and
`recomp/work/windows-unity-native2/`. `parity-acceptance.json` records commands,
exit codes, source archive and log hashes. Prepare/build entry points remain
`unity_bootstrap_prepare.py` and `unity_bootstrap_build.ps1`; use a separate
output directory and retain `--exploratory` because unsupported traces remain.

A second host checkpoint uses the same unchanged translated cohort with Bunker
`92bea353436f70bc82a4ff03068c25bf7fb36ab9`. It includes the rooted internal
storage service and context-owned GL error bridge. All three default/initJni/
surface gates again exit zero with 42 verified bindings and two finalizers.
The executable SHA-256 is
`d5b2679abf400f6fdcb73967c4d18814cd5432346044ebe338adfa29fd97c233`.
Source archive and full command/log hashes are in ignored
`work/windows-unity-native3/parity-acceptance.json`. This paused diagnostic
does not invoke nativeRender, exercise the new storage selectors from Unity's
boot body, or claim a GL/game frame; those adapters have separate direct tests.
