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

The host explicitly selects the Android13 framework compatibility
profile: Build.VERSION.SDK_INT is 33. This selection is independent of the APK's
targetSdk and Windows identity; unported API bodies still stop explicitly.
Only the reached integer field is supplied, with no invented RELEASE,
INCREMENTAL or device properties. Original helpers resolve SDK_INT through
JNI144/150, and the native startup compares it with API21 before its OBB path.
[Android13 Build.java](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/Build.java)
is pinned in `work/android-api-profile-audit`, SHA256
`77d6b4a7fef0ac88197bd269a2a9c1c4e37d20a3fa026b3b0654930187147e95`.
The selected field is set and read back through the real JNI static-field table;
the game8b natural profiles qualify setup and the recorded startup boundary below.

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

Virtual alternate-stack registrations use actual writable FileSystem mappings
and their allocation generations. Registration itself holds no active mapping
lease; bounded signal-frame delivery must acquire a physical lease first. Fresh
virtual threads start disabled. The harness supplies no invented prior ART stack
and does not clear installed metadata when original code unmaps its storage.
The original sigaltstack call log records the actual translated SP, LR, result
and configured tuple. Installing this provider does not enable production
signal delivery or collector polling.

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

`work/windows-game5` includes the accepted reference arrays and read-only secure
settings backend (host c85b5e6). Its actual frame next reaches the unimplemented
JNIBridge.newInterfaceProxy(J,Class[]) factory; no later IL2CPP load or returned
nativeRender is established. Executable SHA256 is
`d1b3065e1bacbb5a2e0c41817108e04304f31a1d61b4b869f4900c39684cf7a9`.

`work/windows-game6b` qualifies the exact provider-free TLS policy described
above, with host 610492e and executable SHA256
`c46544f71aac590606b9ff98e66d6d09070d4bbd642f47414140bf014fe0c80a`.
Default, initJni and paused surface profiles each pass terminal completion,
417 constructors/42 JNI bindings/two reverse Unity finalizers, zero IL2CPP
constructors/references, and full post-run frozen-input verification. The real
key19 free callback remains owned until actual runner retirement; no TLS value
is cleared to bypass it. Surface handoff still observes 2+2=4 reference calls.
This variant executes no nativeResume/nativeRender. The earlier game6 compile
failure is preserved; game6b is a fresh immutable source/build variant.

`work/windows-game7a` freezes host 11d2dca and executable SHA256
`b7ce26fae2c22a31a37b9072d8c6a5ede5730233aabcf4edd43ed6081df7b610`.
Default, initJni and paused surface profiles again pass normal terminal
completion, with all inputs reverified after each run. The real frame now creates
both singleton interface proxies from original native handles and actual
Class[] arguments: ServiceConnection, then
AudioManager$OnAudioFocusChangeListener. The next missing Java class is
android/location/LocationListener. Original Unity then calls sigaltstack at
LR7040ee3c, where this immutable variant stops at its unknown import boundary.
Its aggregate audit is `work/windows-game7a/game_final_audit.json`, SHA256
`a8772c687ca5b13e7f5605557f5021fcf6c86c0ca3677ba97258011c9826efd4`.
IL2CPP constructors/finalizers remain zero, nativeRender has not returned and
no game image has rendered. Earlier game7 and all other variants are preserved.

`work/windows-game8` freezes host bac1ecb and executable SHA256
`dae0f5932345fbc43e9ce1c3517d594d47208edb07f803f8ddc6af6f7ca2f35c`.
Default, init and surface again pass normal completion. The actual frame logs
all three supplied singleton Class[] profiles, now including LocationListener,
and the original sigaltstack query at LR7040ee3c returns zero with the genuine
disabled tuple. No stack installation or signal delivery is claimed for this
game run; those remain separately qualified component behavior.

Original Java diagnostics next record missing Context.LOCATION_SERVICE,
android/os/Build$VERSION and Context.getObbDirs()[Ljava/io/File;. The terminal
boundary is the unimplemented actual APK method
AssetPackManagerWrapper.init(Context). All four profiles reverify frozen inputs
after execution. Aggregate audit `work/windows-game8/game_final_audit.json`
SHA256 is `aa3defdf89901451cd44d706c3ad6b4617660fdf064e304129594c8d3fa8c951`.
IL2CPP remains uninitialized/unloaded on this path; nativeRender has not returned.

`work/windows-game8b` freezes host f6e472a and executable SHA256
`6f29aca6dd84cb7ca622ceb9f06fd797d48f095bd0fcf5122663d09c5b66eea9`.
All three non-render profiles pass normal completion and full post-run input
verification. The frame no longer raises the earlier LOCATION_SERVICE or
Build.VERSION lookup errors. It now records missing getSystemService and
getObbDirs, then stops at the same AssetPackManagerWrapper.init boundary.
All three proxy requests and the successful disabled sigaltstack query remain
captured. Aggregate audit SHA256 is
`599dc5b4121faaccf38a30d8a801014eb8a16f1a57661bb57aed10eddcf512b9`.

An independent audit explains the query-only behavior: original mmap at
7040ee68 requests flags0x20122, including MAP_GROWSDOWN. This frozen FileSystem
rejects the valid growth bit with EINVAL, so original Unity returns false before
installing its stack. That checkpoint does not qualify original stack setup.
New host wiring logs actual mmap arguments/results through the unchanged typed
provider bridge; it adds no guest allocation or successful fallback.

The next combined host includes typed JNI reference-array results, verified OBB
getters and the exact APK's missing-PlayCore wrapper branch. Its explicit mount
profile supplies zero Android external volumes, independently of APK file names.
The wrapper profile requires the exact runtime-verified APK and complete closed
code-catalog proof, including all four DEX containers and split metadata.
The subsequently accepted native stack-growth profile and game9 execution below
qualify the original allocation and installation. These gates do not establish a
returned frame.

`work/windows-game9` freezes host 3eddad8 and executable SHA256
`9c0c1b16458e15e12cbeb558a72b9a3764dc319db5086c949e4a535917ad2991`.
All three non-render profiles pass normal completion and full post-run input
verification. The frame retains the three original singleton proxy requests.
Original mmap at LR7040ee6c returns real 262144-byte storage for flags0x20122;
original sigaltstack at LR7040ee98 installs that same address and returns zero.
This qualifies installation, without claiming an in-game downward-growth fault
or signal delivery. The explicit Windows profile and its separate fault tests
are documented in [the growth contract](growdown_memory.md).

Startup passes the earlier AssetPackManagerWrapper.init boundary by original
flow. It next reports missing Runnable and MODE_PRIVATE, then reaches a null
strlen input at LR70432174 in the original package-name getter after the pending
field exception. No preferences store is opened. MODE_PRIVATE and the exact
Runnable singleton profile have since been supplied for a fresh natural run.
getSystemService remains unported. IL2CPP remains unloaded and nativeRender has
not returned. Aggregate audit SHA256 is
`bc5bd9a66ee5022f4df30ba1a33bc80fef8728d12b31ae5a1c125b825026f2bc`.

`work/windows-game10` freezes host 11cc5b2 and executable SHA256
`5c913e1814184f3d2529e108ddbe851a4566cec58167a4d9429ae3606703abae`.
The three non-render profiles pass normal completion and all frozen inputs and
original objects are reverified after every profile. The frame repeats original
stack installation and captures two additional genuine singleton Runnable
Class[] requests. The MODE_PRIVATE and null-strlen failures are gone.

After original Java catches report missing getSystemService, runOnUiThread,
getSharedPreferences, View.OnSystemUiVisibilityChangeListener and Handler,
startup continues. Original Unity dlopen at LR70384720 naturally requests
libil2cpp.so through the application library catalog. All nine actual IL2CPP
constructors execute; all 222 subsequent dlsym results match the frozen original
export proof in exact order. No host loader or initialization call is inserted.
The next fatal boundary is Unity's unsupported sscanf import at LR709bede8.
IL2CPP initialization, nativeRender return, signal delivery and a rendered image
remain unqualified. Aggregate audit SHA256 is
`8ae2475ec3ad51de8dbd9e2ece6cc28ef3ee4b433a1aacd51268e947150a8be2`.
