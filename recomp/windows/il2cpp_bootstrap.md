# Actual IL2CPP diagnostic bootstrap

The new il2cpp_* prepare/build/harness files execute the original library's
constructor and finalizer entries using existing statically translated Windows
code and checked host providers. They do not execute ARM64 bytes, skip actual
constructors, fabricate GC thread records, or rewrite library globals to make
the gate pass. This is an explicitly exploratory diagnostic, not a game launcher
or a claim of whole-library translation correctness.

The original libil2cpp.so SHA256 is
ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522.
Its existing Windows snapshot has 393,781 traces, 3,079 COFF objects, nine
constructors, two finalizers, 280 imports and an original guest base of 0x80000000.
Only liblog, libm, libdl and libc are DT_NEEDED dependencies. Undefined data
imports are __sF and environ, supplied by real providers. The harness resolves
167 imports and leaves 113 strong function imports as explicit fatal markers.
No unresolved weak imports occur in this image.

The first native run completed constructors 1–3 and stopped during constructor
4 at guest 0x82557e3c, the STXP instruction in trace 0x82557e34. This instruction
was unsupported in the old snapshot. The preserved first-stxp-evidence directory
contains the exact frozen host sources, metadata, failure log and executable.

The parent built one diagnostic overlay replacing shard-01066 only. All 128
original definitions were seeds; all 393,781 original trace heads were retained.
Validation independently audited the actual COFF symbols across every original
object, checked sole ownership of the replaced functions, identical fresh IR/COFF
definitions, zero added/deleted functions, zero new/missing direct targets, and
zero unsupported instructions in the replacement. Canonical recursive LLVM
State layouts agree in every field shape, offset, size and ABI alignment.
Independent positive/negative comparator tests cover renamed types, changed
fields at equal total size, packing, primitive alignment and opaque types.

The overlay object SHA256 is
aa0a093e440749296ff11cc5e6847da4b4bf654fbe0e0e6c76d259038c120c63.
The original object set/manifest remain unchanged. The composition still has
189 unsupported traces and mixes compiler snapshots; this is not a full refresh.
The raw executable image was independently reconstructed from the actual ELF's
executable load segments and matched byte-for-byte by SHA256.

The mixed executable completed all nine constructors in original order and both
real finalizers, exiting 0. The same executable also passed an opt-in direct call
to the actual parameterless GC signal initializer at RVA 0x25b3020. It checked
the actual default signals 30/24, installed dispatcher thunks, original-handler
table, SIGINFO/RESTART flags, empty acknowledgment semaphore and unblocked
current-thread mask. These are real initializer effects, not manufactured data.
SignalHost registration describes only the actual primordial host thread's
virtual signal policy; it is not a guest Boehm thread record.

That executable SHA256 is
eb0298114f943492db8e39c1109d75ffb162315b8e2b0337848dc43f65dc3ce2.
Evidence lives under work/windows-il2cpp-bootstrap:

- il2cpp_input_audit.json: original ELF relocations/dynamic lifecycle and header.
- il2cpp_link.json: copied object hashes and original compiler lineage.
- overlay-01066/overlay.json: ownership, closure, State ABI and fresh lineage.
- overlay-01066/parent-toolchain.json: exact parent lift/compile commands.
- overlay-01066/lineage-audit.json: source/raw-image/frozen-tool hashes.
- il2cpp_overlay_build_record.json: frozen host source hashes and native binary.
- il2cpp-nine-constructors-pass.log: constructor/finalizer success.
- il2cpp-gc-signal-init.log/result.json: actual signal initializer success.

The harness intentionally rejects signal delivery requests: this older full
image is not polled. Signal suspension/resumption, live GC scanning/collection,
il2cpp_init, metadata/domain loading and game execution remain separate gates.
Provider worker/signal lifecycle integration is also not assumed. No Unity/JNI,
graphics, shared compiler or runtime source was changed for this harness.

Preparation requires the complete original manifest and explicitly allows
incomplete instruction coverage only with --exploratory. The PowerShell builder
freezes host sources and verifies every copied object before linking. Its
OverlayMetadata parameter accepts validated overlays without replacing any
original file. The optional GcSignalInit run flag invokes initialization only;
the resulting library still executes both finalizers.

## Module lifetime and Unity export lookup profile

The optional --module-load-exports profile gives ModuleRegistry sole ownership
of the original nine constructor and two reverse finalizer entries. It opens the
registered /data/app/bunker/lib/arm64/libil2cpp.so alias with flags2 and resolves
all222 exact names requested by the original Unity API loader. Every result must
match the rebased original ELF export and registered translated entry. A repeated
basename open must retain the same handle, reach reference count2 and avoid
constructors; the nonfinal close must avoid finalizers. Final close executes
both finalizers once, rejects stale handles, and refuses reopening without a
real data-image reset. No reset is supplied.

This profile invokes no looked-up API body, il2cpp_init, startup-hook queue,
managed code or GC setup. It is an isolated IL2CPP module-provider gate, not
execution of Unity's Java ClassLoader/loader path or multi-module game startup.
Default and --gc-signal-init modes keep their previous explicit lifecycle
ownership and are regression-tested using the same new executable.

Preparation uses --module-exports-only --unity-library original-libunity.so.
It pins the audited Unity hash, proves the actual dlsym GOT/PLT/wrapper calls,
extracts222 literal names and contiguous result slots from its real resolver,
and checks the original IL2CPP ELF, manifest, supported trace entries and both
native APK members. It writes il2cpp_module_exports.h/proof.json sidecars only.
The original prepared header, metadata, objects and overlay remain untouched.

il2cpp_exports_test.py checks the real proof and rejection of changed source,
missing/mismatched/untranslated/unsupported exports. Build with
il2cpp_build.ps1 -ModuleLoadExports and the previously validated OverlayMetadata.
Separate module-exports source snapshot, build record, object, response file,
executable and logs preserve earlier artifacts. test_il2cpp_module_exports.ps1
runs all three modes and verifies hashes of the prior final-audit artifacts
before and after. The189 remaining unsupported traces and old unpolled mixed
snapshot are unchanged.

The native module-export profile passed all222 lookups and lifecycle/refcount/
stale-handle/reopen checks with exit0. The same new executable passed the default
and real GC-signal-initializer regressions, each with9 constructors/2 finalizers
and exit0. Twelve independent export-proof/rejection checks passed. Its SHA256 is
244b7f111af71b9941cf054d8d5b308a74b7712a97f6cbb5d0e3dbb2c46396e9.
The frozen host cohort provides170 imports and retains110 explicit strong
failure markers. All prior artifact hashes and all new frozen source hashes
were checked; later live provider changes are not attributed to this executable.
Evidence is il2cpp_module_exports_build_record.json,
il2cpp-module-exports-tests.json and il2cpp_module_exports_final_audit.json.
