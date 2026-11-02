# Reached startup additions after the indexed-FP cohort

The accepted indexed-FP base remains 59,610 traces in 469 objects, with
1,343 unsupported heads. These additions preserve those artifacts; they are
explicit inputs to fresh diagnostics, not a full Unity retranslation.

## Original hash-tail case entries

The Native6 frame reached missing target `704fb338`. The containing original
FDE is `704fb0ac..704fb3fc`; this target is case 8 of a 16-entry signed-word
table, not an independent callback. `CMP X13,#15` and `B.HI` bound the index;
the table at `70f048f8` feeds `BR X13` at `704fb2d0`. The load reads the index
before overwriting X13. All case destinations remain inside the original FDE.

One additive object supplies exactly the 16 previously absent case heads.
It changes no original definition or object, has closed direct references and
the same recursive State layout. Its SHA256 is
`43598bdadbb1f295c3c6981e49225eb4be1f45c43c57a2849e151e489e9d40be`.
The resulting union has 59,626 heads in 470 objects. The frozen lifter and
semantics remain the indexed-FP base versions. Generic compiler recovery of
this pattern now passes the [snapshot-index proof gate](../whole/snapshot_jump_tables.md),
preserving all 692 old table proofs and recovering these 16 entries plus two
neighboring four-case tables. Existing engine artifacts remain unchanged;
their additive proof is still an explicit composition input.

Native7 passed that original dispatch and stopped at real `getpid`. Native8
includes the tested process-identity provider and reaches the next Java
requirements: getContentResolver, ServiceConnection and initializeGoogleAr.
Its executable SHA256 is
`48c257b3531e6d50f8e64e072bff7b81574468a676eb33dc98d985ac6413bdef`.
The real read-only audio endpoint observer succeeded (scalar 0, muted true);
it did not change machine audio settings. No nativeRender returned.

## Reached unsigned-widening replacement

The original Managed-copy component subsequently reached `USHLL v0.2d,v0.2s,#0`
at `70413eb0`, inside original ZIP enumerator `70413e00`. The unsupported
diagnostic reported the following PC, `70413eb4`.

After [unsigned widening](../whole/ushll.md) passed both-host ARM64-reference
gates, a fresh object replaced only base `objects/shard-00158.o`. It retains
exactly its original 128 definitions, has no unsupported traces or missing
direct targets, and matches the canonical 1,200-byte/alignment-16 State layout.
The replacement SHA256 is
`c451301af47e820e57ab76174d40bf7e6914d7ea12f749cef93d8775d2e1c9bb`;
the preserved old object is
`d3cd0947f7b2cfd875c7093e954d4f61cbb559c3e19143c6560e0977e8f15c96`.

The replacement uses lifter
`fa80a8edb3f33d1815ad4b256d7eaa9d1625889adfd6ff59044be0b1cc6277ad`
and semantics
`9524e65b09c51e5b62d1a2f2fae631da9cb6f8ddda5fa3af6401947986cae802`.
Other original objects retain their accepted earlier semantics. Only unsupported
head `70413e00` is removed, leaving 1,342. No trace heads change. The replacement
does not depend on the additive hash cases; each composition is checked explicitly.

The [copy component](unity_managed_copy.md) using this replacement copied and
verified all 24 original Managed files and completed its owned teardown.
It did not execute normal engine initialization or IL2CPP initialization.

## Evidence and next integration

Ignored evidence is retained in `work/unity-4fb338/additive-proof.json`,
`work/windows-unity-native7/`, `work/windows-unity-native8/`,
`work/unity-ushll-overlay/overlay.json` and
`work/windows-unity-managed-copy5/managed-final-audit.json`.
Earlier artifacts are preserved and rehashed by the newer gates.

The new [natural dual-engine diagnostic](game_bootstrap.md) composes both Unity
additions with the [current full IL2CPP cohort](il2cpp_snapshot_current.md).
Its 456,684 heads/3,575 objects have closed direct references; IL2CPP constructors
remain lazy until requested by original code. A static composition or component
pass does not establish a completed game frame, collection or managed execution.

Its first executed corrected variant, `work/windows-game4`, passes constructors
and JNI registration. initJni and the paused surface handoff return, then record
an explicit TLS teardown boundary. The actual frame reaches Settings.Secure and
JNI NewObjectArray after the earlier Java fixes. IL2CPP has zero constructors
and references immediately before that nativeRender. See the natural diagnostic
document for exact source/executable hashes and retained failure variants.
