# Unity snapshot with corrected indexed arithmetic

The accepted paused-startup cohort is now `whole-unity-fmla-fmul-indexed`:
**59,610 traces, 469 AMD64 objects, 1,343 unsupported traces**, and no unresolved
direct targets. It includes the validated indexed FMLA and FMUL semantics.
The earlier estimate/shift/TRN cohort and every previous executable remain
preserved in separate directories.

Static comparison with the previous 1,345-unsupported cohort verifies:

- Identical original ELF, bases, image span, executable ranges, seed entries,
  imports, exports, 417 initializers and two finalizers.
- Exactly the same complete trace set, without newly unsupported entries.
- The two removed unsupported heads are `0x705ee5b4` and `0x7091bce0`.
  The latter is the original matrix leaf now separately tested on ARM64,
  Linux and Windows across finite and nonfinite/FZ inputs.
- AMD64 machine headers and SHA-256 for all 469 objects, exact ownership of
  all 59,610 definitions, and closure of 20,979 distinct direct guest targets.
- Identical canonical recursive State field layout, sizes and alignment.

Native Windows startup was built from frozen host commit
`32edc699341f6d88b1c193e6df675952f226cd53`. It includes the owned JNI callback
frame fix. Later constructor-factory and graphics additions have their own
unit gates and are not attributed to this frozen executable.

All three separate executions exit zero: constructor/JNI, actual initJni, and
paused UnityMain surface attach/change/detach. Each observes 417 constructors,
42 original ELF/DEX-verified bindings and two finalizers. The surface gate
again observes two fromSurface, two acquire and four release calls.

| Artifact | SHA-256 |
| --- | --- |
| Original Unity ELF | `3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f` |
| Lifter | `78e33b4cc37e8b2d34e7b6f2adf2a549ccc2590199f8c41a9758a039e09a5a54` |
| Semantics | `098d2e4b3214af9b3e4a7a39053acf44bc04ab94527b549874fd7d69710bab1e` |
| Recursive State layout | `ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d` |
| Native executable | `bd194887bebf6337dc3e624c15aa8b76606e5688415408938b6be5aa34fc7669` |

Ignored evidence is `work/unity-indexed-fp-lineage/result.json` and
`work/windows-unity-native4/parity-acceptance.json`, including full object,
source-archive, manifest, command and log hashes. Prepare/build entry points
remain `unity_bootstrap_prepare.py` and `unity_bootstrap_build.ps1`; explicit
exploratory mode is still required.

A later host-only refresh at `a187d003fcbb11731b865663a9755334f3363125`
also passes all three executions with the same 417 constructors, 42 bindings
and two finalizers per process. It includes constructor-factory JNI frames,
process clock/sysconf, setvbuf and full supported-GL forwarding. All engine
objects and generated link metadata retain their accepted hashes. Its executable
is `96884fe5614c6d9dc5d0288b0f7970d3efd1e4ececbe4a92db3335e27d5d7bad`;
source archive is `14db0ff27f96936bd3ecc5029952f4cd1c396d0a5c9f5c2270100071671cde24`.
Evidence is `work/windows-unity-native5/parity-acceptance.json`. These paused
checks do not exercise the new GL draw forwarding or claim a game frame.

This remains an unpolled diagnostic snapshot. These three startup checks do
not execute nativeResume/nativeRender, IL2CPP initialization or a game frame.
Ordinary FMUL and remaining unsupported instructions retain their documented
boundaries. The separate original API-loader gate still uses its older,
independently frozen mixed Unity/IL2CPP cohort.
