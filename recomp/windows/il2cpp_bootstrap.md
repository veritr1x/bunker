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
