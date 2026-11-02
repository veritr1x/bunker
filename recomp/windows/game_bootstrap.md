# Natural dual-engine frame diagnostic

This new isolated diagnostic registers the original Unity and refreshed IL2CPP
modules in one Runtime. It starts the original Unity constructors, JNI_OnLoad,
initJni and actual HWND/UnityMain lifecycle. Only the original nativeRender path
may request IL2CPP through the real application ClassLoader, native-library
catalog, dlopen and exported API loader. No manual IL2CPP initialization,
preinitialization, copy helper, ICall installation or collector callback runs.

Inputs are the accepted 59626-head/470-object Unity cohort (the 16-case additive
object plus the exact 128-definition USHLL replacement) and current
397058-head/3105-object IL2CPP cohort. Preparation checks their original hashes,
ELF constructor/finalizer arrays, disjoint executable ranges, exact union of
456684 COFF definitions, direct closure, and all 222 real Unity API requests.
All prior artifacts remain in place. Final preparation requires an explicit
accepted committed host containing AndroidContext::BindUnityPlayer.

`game_bootstrap_prepare.py --plan-only` makes a fresh static plan without
freezing providers or executing guests. Omit it and provide `--host-commit` only
after the parent accepts the Java/PID/provider checkpoint. Build with
`game_bootstrap_build.ps1 -BuildDirectory <fresh-build>`, then run
`test_game_bootstrap.py --build <WSL-build-path> --profile default|init|surface|frame`.
The frame profile retains the same real worker/window across observation
timeouts. Logs and data are unique per fresh profile; no prior variant is erased.

Each module owns its exact constructors and reverse finalizers. Merely registering
IL2CPP executes nothing. The catalog and providers stay alive through all guest
callbacks. A host-owned Unity handle is the only handle the harness closes;
guest IL2CPP handles and reference counts are observed, never forced to zero.
Remaining UI TLS callbacks owned by modules are retired before JNI/global
teardown and end at an explicit retained-module boundary. The exact installed
LibC free callback can remain until actual ReleaseCurrent: its provider and
allocator state outlive the thread and its body accesses no guest module globals.
No key is cleared, deleted or manually freed to force this path. Guest PLT aliases
and every other callback remain module-owned. Each teardown barrier rechecks the
real UI values, including after global finalization; no query recreates a thread
after ReleaseCurrent. The import audit itself outlives worker draining/Pthreads.
If natural code already finalized a module while a module-owned callback survives,
callbacks stop with an unproved-lifetime diagnostic.

The original IL2CPP 825b0544 wrapper preserves actual execution and callbacks.
GNU `--wrap=sub_825b0544` covers both external direct calls and runtime-table
references. The accepted defining shard has no same-object calls to the helper;
the only external direct caller is original 825af208 at BL 825af2c4. Only the
`__real` symbol points to the unchanged body, avoiding recursive interception.
It owns each real 256-byte SP+8 environment using a unique invocation generation
and a per-thread nested stack, forwards real NonlocalJumps, and forgets precisely
that object when its original Entry returns, before the outer caller resumes.
It does not rewrite the trailing raw global, inspect fake saved fields, install a
synthetic collector callback, or treat that raw value as a surviving root.

Signal policy and semaphores share actual registered UI/UnityMain lifetimes and
owned stacks/masks. Nonzero signal delivery is rejected before queuing because
these cohorts do not poll for suspension. Guest-created workers have no invented
SignalHost registration; reaching such a thread-signal context is a named fatal
boundary until real lifecycle hooks exist. Every unknown import/signature/entry
is fatal. Remaining unsupported traces (Unity 1342, IL2CPP 101) retain their real
failure behavior. Passing a bounded process does not establish stop-world GC,
Java constructor completion, a rendered image or a playable game.

The actual Unity constructor at 700d9044 registers installed LibC::free as a
void(void*) TLS destructor. Its exact marker is admitted alongside translated
callbacks; pthread_create starts remain translated-only. Earlier component
gates supplied a translated-only predicate, so this real KeyCreate returned
EINVAL rather than registering the destructor. No arbitrary import callback is
admitted. A terminal normal-return profile record is required for acceptance;
a guest exit(0) cannot establish successful harness teardown.

## Executed checkpoint

`work/windows-game4` froze host 673bedb and the exact union above. Its standalone
Windows executable SHA256 is
`369a05d1806cb113c6b451d2ad1db345055871f7a199561156a10616643318f7`.
The constructor/JNI profile passed its terminal record with 417 original Unity
constructors, 42 native bindings and two reverse finalizers. InitJni returned
without a Java exception. Surface handoff/detach observed two fromSurface, two
acquire and four release calls. Init/surface both ended at the labelled exit7
retained-module UI TLS boundary, not a complete teardown pass.

The real frame entered original nativeRender7043a0c4 after an actual HWND focus
event and read-only real audio-volume observation. Immediately before entry,
IL2CPP constructors and references were both zero. Unity reached Dynamic Heap
allocator startup, then FindClass android/provider/Settings$Secure failed at
LR70ab5478; ExceptionOccurred observed it at LR70ab524c; unsupported JNIEnv slot172
(NewObjectArray) stopped the process. No nativeRender return, natural IL2CPP load,
engine initialization, rendered image or game completion was established.
Every profile reverified all accepted objects, frozen source/support, native
images, APK, ANGLE and executable after execution. Earlier game1/2/3 variants
remain untouched, including the game2 compile failure and game3 callback guard
failure. The final linked caller825af208 disassembly confirms an actual call to
__wrap_sub_825b0544; the body itself was not reached in this frame.
