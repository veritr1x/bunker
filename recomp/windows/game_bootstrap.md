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

The preferences adapter is constructed after the actual Context and before
guest workers/modules. Its backing is the real per-user Windows package store;
construction performs no storage access. Only original getSharedPreferences and
apply calls cause reads/writes. Native observations record store labels, entry
counts, persistence status and the public Unity version marker, without logging
saved values. CheckPersistence rejects any recorded write failure after callers
quiesce, including JNI/module/global finalization and final TLS retirement before
normal completion. The adapter outlives workers on an attached Host thread.
This wiring requires a new executed checkpoint to qualify original initialization.
See [the storage contract and component evidence](shared_preferences.md).

The reached sscanf import uses the same accepted typed LibC implementation.
Its disjoint diagnostic marker forwards the actual X0/X1/X2 arguments, catches
host exceptions before translated continuation, and logs LR, assignment count,
the assigned value and actual Android errno. It reads output only after a real
assignment and supplies no parsed value or fallback. Other formats retain the
named unsupported boundary. See [the exact parser contract](libc_sscanf.md).

The setlocale observer likewise forwards real W0/X1 through the accepted LibC
implementation at a disjoint marker. Invalid categories are rejected before
the observer reads a name pointer. Its log records the actual result and LR;
the predicted call at LR8254d0b4 would establish public il2cpp_init entry, without
establishing inner initialization or its return. No host init call is inserted.
The Windows locale, pthread-binding, EGL-error and automatic-frame containers
use qualified native thread storage; see [the lifetime repair](passive_thread_storage.md).

The Dup observer forwards the original signed descriptor through the accepted
FileSystem implementation once, recording its actual result, LR and Android
errno. Its marker is separate from mmap/sscanf/setlocale and it performs no
extra descriptor/path/stat operation. This observation does not establish the
original pathname. See [the bounded duplication contract](filesystem_dup.md).

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

A later read-only inventory of that same game10 DataRoot qualifies the natural
physical Managed copy. The runner created an empty unique directory before the
original process; no host copy or repair populated it. Its files/il2cpp tree
contains exactly all24 original APK Managed members, totaling24570231 bytes,
with exact byte/CRC/SHA parity and no extra files. Metadata is23317064 bytes,
SHA256 `7ae75b594082b3a603a82f68d497d6c3aea30881b94496b2c11d8de71f8321d2`.
The original startup can reach the terminal sscanf after physically copying;
the log alone does not identify which of four buildDate scan sites called it.
No helper return, unity.ver write, later copy-stage cleanup or IL2CPP init is
claimed. The independent read-only supplement
`work/game10-managed-readonly/acceptance.json` has SHA256
`dcefccb34c52a195ac50f0c824d378dc60196de1d42fde16620b89339d72aeee`;
the original frozen game audit remains unchanged.

`work/windows-game11` freezes ccf8c84 and executable SHA256
`657e01c77bc2a8f326478597a1e0e81302cd405dbf1ff9e6ddaa09eb6f36c8b3`.
Its default profile fails during setup before any original constructor:
AndroidAssets and the new preferences adapter both declare
java.util.NoSuchElementException. No preference read/write or game startup is
claimed, and the other profiles were not started. The focused preferences
fixture omitted configured APK assets, so it missed this composition. Canonical
exception ownership and a combined setup regression are required before the
next natural attempt. Frozen inputs and all original objects are reverified.
The failed-setup audit SHA256 is
`2b7043f43b00e97da5760294a85cc97e79f7fec70968a9286e8e9f997b90866f`.

`work/windows-game12` freezes 5bb1bee and executable SHA256
`6bc22d01fa78fd4da4a7f567b0b0d26382496ab9eea17e05b3bed95aaad18310`.
Canonical NoSuchElementException ownership resolves the setup collision. Its
constructor/JNI, initJni and surface profiles pass normal completion and full
post-run input verification. Both frame attempts stop earlier than game10:
the actual read-only audio observer returns unavailable/0x80070490 before
nativeResume/nativeRender. No preference opening, sscanf execution or new
IL2CPP initialization is claimed. Both complete attempts, including their data
directories, remain under attempts/frame-audio-unavailable1 and2.

Independent native queries observed the LG TV active briefly, then reproduced
zero active playback endpoints/all three playback roles unavailable while
capture remained active. Services stayed running; no OS setting, volume or
provider changed. The exact external cause is unproved. A bounded15-minute
notification watch also ended without availability and stopped cleanly.
The two-attempt audit game_audio_boundary_audit.json has SHA256
`66c3c3277b3aac1d4836697bb383dc119a322ef77e7902d19a85ed1666d71b63`.
Read-only device evidence is in work/audio-endpoint-game12-audit and
work/audio-watch-game12. A fresh real frame requires an available endpoint.

`work/windows-game13` freezes319fda9 and executable SHA256
`7e3c0fcc684a2f7810e8e435b096904c13779f117bc2e90e049053b01b01fd4a`.
All three non-render profiles pass and every profile revalidates frozen inputs
and original objects. With the actual LG TV endpoint available, the frame
enters original startup. Its real preferences backend observes v2 and legacy
stores absent, then writes one integer marker1 to v2 with RegSet/RegFlush status0.
No production registry query, reset or host migration is used.

Both original sscanf calls return1/value638477124699603280. All24 Managed
members still match the APK exactly, and the sole extra cachefile unity.ver is
the eight-byte little-endian value50c1eee68f53dc08. Original Unity naturally
loads IL2CPP, executes its nine constructors and resolves all222 exports.
The actual setlocale6/empty call returns C.UTF-8 at LR8254d0b4, establishing
public il2cpp_init entry beyond lookup. Its next fatal is IL2CPP's unimplemented
dup at LR82553f20 with guestfd0x402. Initialization and nativeRender have not
returned; no metadata execution, GC, managed code or rendered image is claimed.
Native success preserves prior errno2, which is not an error for the successful
scan/locale calls. The normal CheckPersistence/teardown barrier is not reached.

The aggregate audit SHA256 is
`59e491e13b34458bc42dd7fb1a6f5bc0f886842a4915b73762bdf1411806da3a`.
Read-only storage proof work/game13-storage-audit/result.json has SHA256
`58c7be3e67758bd1264e343efb635182df54a7e05cf75d4231d839d95ef0af62`.

`work/windows-game14` freezes0a5bdf2 and executable SHA256
`e89d3b9d64311f298ef5c47ba01cd73bb27374d7b5f1f5b0f70c785d49e502a3`.
The qualified Dup provider is linked, and constructor/JNI, initJni and surface
profiles pass. Its frame attempt stops before resume/render at actual audio
unavailable/0x80070490, so it supplies no natural Dup/init evidence. The complete
attempt remains under attempts/frame-audio-unavailable1. The audio-boundary
audit SHA256 is
`5df3d37aba5bfc30600bc5b107c5e91e9b7b0c5c9f0004701c9df1257ce838d1`.

Read-only power diagnosis found34-minute input idle against an AC900-second
display timeout, with no display-required request. This suggested a possible
HDMI power interaction but did not establish causality. A separate controlled
helper then held a checked display+system request on a dedicated native thread
for120 seconds, observing only the real frozen audio provider. No endpoint
returned and no game process was launched. The same thread successfully cleared
its request, joined and stopped the observer; aggregate execution state returned
from0x3 to0x1 and the helper exited. Persistent power/audio settings were never
changed. Its reported result2 is distinct from the unavailable .NET OS-exit
code. Evidence is work/audio-power-game14-controlled/REPORT.md, SHA256
`8feb13d6fde368ccf32fb96235c2fe3ebc99e21df109eab08a2e49537275fa1b`.
All temporary requests/helpers are retired.

A subsequent read-only query found the LG TV endpoint available. The same
frozen Game14 executable was retried with a fresh data directory. The real v2
preference store is now present with one entry; original startup writes its
integer marker with status0. No legacy read is observed on this path. Both
original scans return638477124699603280, the24 physical Managed files still
match the APK, and unity.ver retains the exact eight-byte value.

Natural public initialization now executes dup(1026), returning1000 at
LR82553f20, followed by a successful23318528-byte file mmap at LR8255410c and
four262144-byte anonymous mappings at LR825b255c. Successful calls preserve
errno2; it does not indicate failure. The fd alone does not establish the
mapped pathname. Original initialization then stops at PRFUM PLDL1STRM,
[X20,#-0x70] at825ae0c8 (wordf8990281). The reported unliftable address825ae0cc
is the next PC, where the ordinary LDR is supported. The same original
function contains five unsigned-immediate PRFM sites requiring qualification.

The three non-render profiles pass and all four profiles reverify their
frozen inputs and original objects. Aggregate game_final_audit.json SHA256 is
`a298be3a48811d90819dc599ecd644ee9a0657a872e9234f0f314c3e7f596d08`.
Read-only storage result work/game14-storage-audit/result.json has SHA256
`bf9bc87d4c3c3c1000994173ebe1412f32a966a847a4cb5ce1607df67e3a4453`.
The earlier unavailable-audio attempt remains unchanged. Initialization,
collection and nativeRender have not completed; no rendered image or managed
execution is claimed. The new prefetch lifter is not part of this Game14 run.

`work/windows-game15` freezes hostc8014f3 and executable SHA256
`b13c4afbfa9713e17e0d47d7cfb928a13614c4579f113cfa6d51daf8f645ea7a`.
It replaces only IL2CPP shard01082 with the qualified PRFM/PRFUM implementation
described in [the prefetch gate](../whole/prefetch.md). The joint cohort keeps
456684 heads/3575 objects, all79436 direct targets closed, and the same State
ABI. Other3574 objects retain their existing frozen semantics. IL2CPP's static
unsupported-head count falls from101 to98; this is not a full-library refresh.
The pre-run acceptance SHA256 is
`1ad7cf34c7c64ed19fc9ff4b01ed03d1558f052d628b35948680651a154e2229`.
It closes the build-time pending qualification without rewriting frozen inputs.

All three non-render lifecycle profiles pass and every profile revalidates
frozen inputs and original objects. With the actual LG TV endpoint available,
original startup repeats its real preference read/write, scans, locale, Dup and
mappings. It passes the prior prefetch boundary and creates an additional guest
worker: token0x7ffa00000003, entry0x82556a94, with no synthetic SignalHost binding.
It then stops at the missing libil2cpp.so bsearch import, PC0x7ffc00000400,
LR0x82577480. Worker creation does not establish collector completion, signal
binding or stop-world correctness. Initialization and nativeRender have not
returned; no rendered image is claimed.

Read-only comparison again finds exactly24 Managed members/24570231 bytes
matching the APK and the same eight-byte unity.ver. Its result SHA256 is
`47fd64931db8b8830e31b018e9e35cdaa0b10b2fde545870504264f0603b9cf6`.
The Game15 aggregate game_final_audit.json SHA256 is
`18e4ded9a625bce754ec1953e382db14111d59c9a297521817be7e3a1805700e`.

The optional `frame-muted` runner profile adds `--mute-audio` to the frame
command. It omits the Windows hardware-volume observer and its Java handler,
so a missing HDMI playback endpoint no longer blocks this diagnostic before
resume. On UnityMain, immediately after the original nativeResume returns,
it requests the game's registered nativeMuteMasterAudio(true) using the same
JNI environment/player. It reports the returned request, checks exceptions
and then permits the normal nativeRender call. No volume event, endpoint or
successful audio device is invented. The default `frame` profile retains its
real observer and audio prerequisite.

This is an explicitly different diagnostic lifecycle. Master mute is not a
backend-disable operation: later original resume/initialization code can reset
the gain, and output remains unqualified. The mode allows current non-audio
startup work while the TV is off; later audio initialization and actual output
need their own checks. Use `frame` again when HDMI playback is available.
The new mode still requires the normal graphics/window prerequisites.

`work/windows-game16` freezes6bc0f27 and executable SHA256
`6eed62d3e807e7c788c6dd3462e9892177327ab09f87f5b6c47a0ace83948cbd`.
The three non-render profiles pass. Its first muted attempt omits the volume
observer, then faults during original master mute before nativeRender or any
IL2CPP constructor. Native logging and the sole separate debugger replay locate
the read violation at float bits0x3f800000. FMOV is correct; FCSEL at7043a78c
misinterprets selected scalar bits as a pointer. The compiled then-current
semantics also has this bug, despite a source comment suggesting raw bits.
The preserved muted-boundary audit SHA256 is
`4e6d62aa58c4471e3a7669721e5dd1bd4bf7badb8c014ba1689104582dc987be`.

A separate normal-audio Game16 attempt includes the qualified Bsearch provider
and reaches the intentional signal30 guard at LR825b2d1c, target worker3. There
is no per-call Bsearch observer or metadata-completion claim. All24 Managed
members and unity.ver still match their inputs. The combined Game16 audit
SHA256 is `be4576c1dc77dea7436317f660492d82f05f146de33f9b23cc711b75a7a04bc1`.

`work/windows-game17` retains the same host and replaces only Unity shard00168
using the qualified numeric FCSEL source carriers. Existing Unity USHLL and
IL2CPP prefetch overlays remain. All456684 heads/3575 objects and79436 direct
targets are preserved, with no duplicate/missing heads and the same State ABI.
The executable SHA256 is
`7d410819899f43c5dee9ea296cec141ce4c85eded1687a05f7c494d0efaf6747`;
pre-run FCSEL acceptance SHA256 is
`2cd0fa670cf1dbf1d54361e929757ec76cecb5dc1355223fdc1f715695aa119d`.
See [the scalar-select qualification](../whole/fcsel.md).

Game17's three non-render profiles pass. Its muted attempt returns from the
original master-mute request on UnityMain after nativeResume, creates no
hardware-volume observer, and naturally executes all9 IL2CPP constructors and
the222 export lookups. Scans, locale, Dup, mappings, all24 physical Managed files
and unity.ver remain qualified. Startup reaches the same intentional signal30
rejection at LR825b2d1c. No signal is queued/delivered and no suspension,
collection, completed initialization or returned/rendered frame is claimed.
The actual unavailable-endpoint condition was not measured in this run;
observer omission, not a fabricated device, removes its volume prerequisite.

Game17 aggregate SHA256 is
`67cd9cf1cc02317acdad2854cefb92ab6e3418144c11ad164204d76e6d25349c`;
read-only storage result SHA256 is
`779ea337d7e720ec3f7d5a6d54497695bd160926116a8348669b07bb89a4b814`.

`work/windows-game18` freezes observer hostf2c080a and the same guest objects
as Game17. Its executable SHA256 is
`287fa3c4d93f1170becdaa3bf4ce0928356efe1471d072e135e30f7307eae875`.
Three non-render lifecycle profiles pass; the muted attempt again returns
from the original mute request and reaches the unchanged signal30 guard.
Audio backend initialization, persistent gain and execution with no playback
endpoint remain unqualified. No HDMI volume observer is created.

Creator-time observations, made before the child can free its payload, identify
the actual worker3 user callback0x825c3ed0 with argument0. Same-thread worker
lifecycle and import wrappers record mutex-lock returns followed by entry into
pthread_cond_wait at LR0x825505d8. The condition address is0x28 beyond its mutex,
matching the original finalizer wait object's offsets. An outstanding ENTER
does not prove the exact physical blocking state or current State at signal
request time. These wrappers dispatch the original provider with the same
State; no signal binding, queue, polling or suspension is enabled.

All24 Managed files/24570231 bytes and unity.ver match the original inputs.
The read-only storage audit SHA256 is
`b54ddb70c9f1e4de21c44ab1c4d46e8cb57a799e969d01a49d1535fc22da7ce0`;
the Game18 aggregate SHA256 is
`5f75085d0c8e2f20ecefdc31dbdbbf0eeae3b2a1173f150d1dc1fb0f4c94a9f1`.
Initialization, collection and nativeRender have not completed.

The native build script can now consume an optional `cooperative_poll_cohort`
descriptor with `acceptance_path` and `acceptance_sha256`. It validates the
proof hash, exact ordered3575-object selection, closed456684-head set, qualified
input-plan/poll-instrument hashes, Windows target and preserved-IR contract
before linking `whole/cooperative_poll.cpp`. Omitting the descriptor preserves
the existing link. This does not install a PollBinding or enable signal delivery.

The actual PowerShell guard AST passes14 bounded positive/negative cases,
including absent metadata and rejection of mismatched contracts/objects. Its
source SHA256 is
`4306003b138a1f665c88bbd4057065531ed9c0257e8ff7a811383373e93af6db`;
`work/game19-cooperative-build-guard/acceptance.json` SHA256 is
`f39b0451febbe67b36627cf8fe95e807f833d98b94c6d224fc61a3dc4acaa2e5`.
These use explicitly synthetic object labels and do not qualify a native link.
The new full cohort is being built separately from the hash-verified original
IR inventory; full-cohort and actual native startup qualification are pending.

That pending cohort qualification is now closed by Game19. All3575 exact
original raw IR modules were copied into a new cohort, instrumented with the
qualified716410d1 poll tool and compiled for Windows. No recovery or relift
ran. All456684 unique heads, the per-module unsupported sets (1440 total),
the shared State graph and all79436 closed direct targets remain unchanged.
There are122086 cycle-cut blocks. The static cohort acceptance SHA256 is
`0a5e6b164855d7c745962ec744d2e7bf1c7209a679065cc117c0575446d9687d`.

Game19 freezes hosta7a0463 with inputs SHA256
`da35bb827d9cf868a422938bd2a72a61f265468fe701008f964fb43205d4df05`;
native executable SHA256 is
`1ed9301388db6e4beadbf0bfe467c59aee9b4cb6bc43aaf5b694f8be0edf95e3`.
Default/init/surface profiles pass. The first muted frame attempt could not
obtain actual HWND focus and stopped before resume or IL2CPP constructors;
its log, runner output, audit and data directory remain preserved under
`attempts/frame-focus-unavailable1`, index SHA256
`43e9ab63ef47de20844d195d62f9a0d84b18ce0043d2bc7f035af3b209321b8d`.

A separate fresh retry receives real focus, returns from original resume and
master mute, naturally executes all9 IL2CPP constructors and repeats the same
actual finalizer callback/condition-wait observations before the signal30
guard at LR825b2d1c. All frozen inputs are reverified before/after execution.
The frame log SHA256 is
`50e072328fc40865da8a9c2a02bbde293341d5428c120bdf673c3d725d7b3b25`;
aggregate SHA256 is
`e8f5625dcc7dc2ace948c11fdb9efa393e5c679f9058e2bf6b3c2377a5551f43`.
All24 Managed files and unity.ver again match their original inputs; storage
audit SHA256 is
`c7dbde7f92fcdb9c0b22aa690ddfbb4618be419a88ac896b29c4ce1e945144de`.

Poll hooks are present but unbound. No nonzero signal is queued, collector
record synthesized, worker suspended, collection/init completed, nativeRender
returned or rendered image claimed. The first opt-in collector profile and
composed worker/wait/frame behavior remain separate, unqualified work.

Game20 freezes the reviewed opt-in collector source5a6a7c2 over the unchanged
Game19 polled cohort. Its inputs SHA256 is
`6f692f83a846e1b695d42ab08d67f3226d9ac680caf9ba0bc6be43403816cf70`;
collector-capable executable SHA256 is
`a7a4d87d3aeeba6a6a2aa661fe5c9a297623dd55f5d351f2d267287a4e0b1d3e`.
Default/init/surface controls pass. Standard muted startup, after two preserved
focus-unavailable attempts and a fresh real-focus retry, still reaches the
unchanged nonzero signal30 guard. Build capability alone enables no delivery.

The separate first `frame-muted-gc` attempt returns resume/master mute and
executes all9 IL2CPP constructors, but reaches the old unsupported PRFM at
825af89c (F9800001) before any worker or collector request. The diagnostic
reports its next-PC825af8a0. The containing head825af884 belongs to old local
shard01083/global selected index1553. Its caller scans heap-filtered pointer
candidates; actualX0/scanned range was not captured, so a particular changed
mmap is not asserted to cause the branch. No signal is queued or handled.

Both frame attempts have exactly24 APK-identical Managed files/24570231 bytes
and matching unity.ver. Metadata file size is23317064; its mapped extent is
23318528. Physical summary SHA256 is
`0129fd62e481a46acd51ceef626e820eb3ce9fcf7dad5b392b18e3f620a3eb87`.
The opt-in frame log SHA256 is
`b75d118199741fad051e2e93cec0e30167102091be63f7b22c1a6383859a925c`;
Game20 aggregate SHA256 is
`0f43bd64f2fefb7632e974326a7e129693f286c056b4568fcd40a3c3c8fdeceb`.
This qualifies control isolation and preserves the incomplete runtime result;
original stop/restart handlers, root frames and acknowledgments remain unrun.

Game21 freezes hostff6c86b and the qualified sparse-prefetch v2 cohort. Only
selected object1553 changes; all456684 heads and79436 closed direct targets
remain. The cohort has1439 unsupported heads and122089 cycle cuts. Its input
SHA256 is `c0acea4f97433b29f7f3a5bfcf5123db091ac28700df2fef0c8ec30eab32a96d`;
the native collector-capable executable SHA256 is
`2b1aef8ffc40cd5b8dbb08fe1e2faad726d35ccf5072a197dd67a5e2fc493ec7`.
Default/init/surface controls pass, and standard muted startup retains the
signal30 guard. Both frame profiles return from the original focus callback,
resume and master mute, then execute all9 IL2CPP constructors. The endpoint
volume observer remains omitted; no TV power-state or audio-output result is
inferred from the failed cursor/screenshot capture.

The separate collector run now creates the captured original finalizer,
observes its actual condition-wait checkpoint and sends original signal30 at
epoch4. The actual pthread_kill provider returns0. Execution then stops at
the ordinary wait-mask check before any original handler or physical signal
frame runs. The delivery boundary repeats that check after SignalHost has
already installed the action mask; a phase-aware check must validate the
saved interrupted mask and the current installed mask separately. No guest
mask should be changed to bypass this diagnostic.

There are zero original handler returns, posts, frame checks or collector
acknowledgments in this attempt. Both outputs again contain exactly24
APK-identical Managed files/24570231 bytes and matching unity.ver. Frame-GC
log SHA256 is
`54db68d4931a5deae77ea9227b487d3e401c55c37ed5a9332ac858c5e5eb5203`;
aggregate SHA256 is
`44922616c66243110f97daf8713f6f57376178b128c6e2552602630ba50f9179`.
Initialization, collection and nativeRender return remain incomplete.

Game22 freezes the qualified phase-aware mask fix at host91c4b67. Its inputs
SHA256 is `905d3ac4455ec1511fe8ecaecf2bae73eeaeb062a7261b786985ed745b445071`;
executable SHA256 is
`f1f01efa652b4ca30a8c8f02704960414574024fb44d9ade62b6c6e29d2a4360`.
All3575 guest objects and generated headers remain identical to Game21.
Default/init/surface pass, and standard muted startup retains the signal30
guard. Both frame profiles receive the original focus callback, return from
resume/master mute and execute all9 IL2CPP constructors.

The explicit collector profile completes its first original E4 stop/restart
handshake. The saved wait mask is80000000; the selected current mask equals
the original action maskfffffffffffbbed9. Actual original30 and24 sends return0.
Both original handlers execute at the qualified finalizer condition wait.
Before each of the two real sem_post calls, all31 GPR and32 Q-register bytes
are verified in the physical interrupted frame above the original published
FP. The nested restart handler and sigsuspend return, then the outer stop
handler returns with actual_posts2 and observed record epoch5. These are
original-code observations; no host collector record, epoch or acknowledgment
is generated. The post logs precede the original epoch stores, so the later
observed record5 is recorded separately.

Startup continues through another mmap and then stops at unsupported
`readlink`, callerLR82554214. Original code constructs `/proc/<actual PID>/exe`
and reads4096 bytes into a prezeroed4097-byte buffer. It needs the real process
image, with forward-slash separators for its original dirname/basename logic.
Returning a shared-library or APK path would misidentify the executable.

Both frame outputs retain the exact24 APK Managed members/24570231 bytes and
original unity.ver. Physical summary SHA256 is
`b0d8741a6ac72ed14135c8888f10fd52cc1e02d9b7a9587b4c34af4d84ead732`;
aggregate SHA256 is
`29e97b009d4eca63698f1d71b7b0daa602e7d50f7d5d89eb6f0151685f6b3651`.
This qualifies one bounded original finalizer handshake. General roots,
repeated cycles, retention/reclamation, initialization return, a rendered
image and a playable game remain unqualified. The fatal boundary also prevents
completed persistence checks and normal worker/TLS/module teardown.

Game23 freezes the qualified native process-image query at host40a290b. Its
inputs SHA256 is
`1005b0f05af576d8e861319fc6d191feb2d8932c8d0c13c199b3ea2c7bdbfca1`;
executable SHA256 is
`3b60d9024d4a5b77a05fda0b21262d06836e5f61c6bc74f99a49e71d0bc567c5`.
The3575 guest objects and headers remain identical. Default/init/surface pass;
standard muted startup retains its guard, while the explicit collector run
again executes one genuine E4 stop/restart cycle with two original posts and
physical register checks, returning with record5.

Startup advances beyond the old readlink boundary; returned pathname bytes
are not directly logged. The next actual calls are Unity's dlsym("end") at
LR70432a7c, returning raw7cb1e78, and unsupported dladdr atLR70432a8c. Original
code uses a32-byte Dl_info, stores its base field only on success and otherwise
stores0. Both raw and Bionic-biased end87cb1e78 are outside logical PT_LOAD
ranges; the biased address is exactly the final segment's exclusive endpoint.
The actual64K-rounded mapping includes padding beyond it, which is not valid
ownership evidence. Android's dlsym bias also affects later backtrace filtering
and two real IL2CPP GLOB_DAT relocations; a new explicit policy is being
qualified rather than forcing a successful dladdr result.

The original natural call graph places this helper after the public
il2cpp_init call returns. This is static-path inference, not a direct return
observation; the returned value and successful initialization remain unproved.
No backtrace callback execution or returned nativeRender is claimed.

Both frame outputs again match the24 original Managed files and unity.ver.
Physical summary SHA256 is
`a2ea2a00c08ad286083d40d273675ab5856bc0aea56ebe87fc21764e5dd50310`;
aggregate SHA256 is
`f4e65904540b2f1f546e55fba95bc144b73997d2fac47c2ca1ee9d4775bb6a6e`.
General GC/roots, retention/reclamation, completed initialization, a rendered
image, gameplay and normal persistence/worker/module teardown remain open.

Game24 freezes the qualified ELF metadata, dladdr and Bionic absolute-symbol
policy at host9c2e899. Inputs SHA256 is
`0e21eb0bccd84f5430a8782ef0bfd64ad595fbc2a72b361b9505fa6f2623db10`;
executable SHA256 is
`b3f67f42e93155c315a5b4756bc48779bf88e0fb2ad8b648bfb58350a55a62da`.
All3575 guest objects and generated headers remain unchanged. Default,
init and surface pass; standard muted startup retains the nonzero signal30
guard. Both frame runs return from the actual focus callback, resume and
master mute, without creating the HDMI-dependent hardware-volume observer.

The separate collector run reaches a different, earlier boundary:
unsupported `usleep`, LR825b394c, with W0=3000 microseconds. One genuine E4
signal30 request and its actual pthread_kill return0 are logged, followed by
the selected saved80000000/current=actionfffffffffffbbed9 mask check. The
concurrent physical-frame line is incomplete. There is no complete physical
frame record, original semaphore post, restart24 request or handler return in
this run; Game22/23's completed bounded cycles remain separate evidence.
Neither dlsym("end") nor dladdr is observed in Game24, so their component
qualification must not be presented as an executed game-path result.

Collector log SHA256 is
`aba6f314226a3a9981d63dd911e1afd4fc8e4928fed97ec1a09cf0c66a94d01f`;
standard muted log SHA256 is
`59c7da99777f6fadad1a38614fa32c727fcc9dee3dada9be1cc29216c1f33c79`.
The next provider must implement a real interruptible timed delay, preserving
the signal-delivery guards and actual collector acknowledgments. A forced
success or synthetic acknowledgment would bypass the original protocol.
Audio backend initialization remains enabled and unqualified; master mute
allows current startup tests to continue while HDMI is unavailable. No
nativeRender return, successful initialization or rendered image is claimed.

Both frame outputs retain24 APK-identical Managed files/24570231 bytes,
metadata23317064/version24 and original unity.ver638477124699603280. The
independent audit rehashes8370 frozen inputs and preserves both terminal
physical output sets. Aggregate SHA256 is
`559f4f66495d34ac2f240f67c6c8db97456c86efd5b2eade83d62a621790ba9c`;
read-only report `work/game24-runtime-boundary-audit/REPORT.md` SHA256 is
`c570d219ecb35c6ee22cffd0e438af0503bba2e9b6fc9e31c77765e5229195f9`.

Game25 freezes the qualified interruptible delay at host54678aac. Input SHA256
is `aa2870e4d287c1687b669755e640b5e4029062441b67ac1e4bfe20c2342042b6`;
executable SHA256 is
`2e52ea2416e94a126b94709c954c80f82a4b492dbc34071f03ffcfb08947d14e`.
The3575 guest objects,456684 heads and v2 cooperative contract remain unchanged;
the separate complete CMHI candidate is not selected. Default/init/surface pass,
and standard muted startup retains the signal30 guard. Both frame profiles
return original focus/resume/master mute without a hardware-volume observer.

The collector attempt again completes its original E4 stop/restart handshake:
30/24 sends return0, both physical GPR31/Q32 checks precede two real semaphore
posts, and the outer handler returns with observed record5. No usleep call or
return is logged in this schedule. The new provider is component-qualified;
this particular original handshake does not exercise the retry-delay path.

Original dlsym("end") now returns Bionic-biased87cb1e78 at LR70432a7c, and actual
dladdr at LR70432a8c returns0. That is the original segment's exclusive endpoint,
so no owner is fabricated from reservation padding. The unchanged helper's
static call graph supports only the prior bounded public-init-return inference;
its actual result and successful initialization remain unobserved.

The next fatal import is Unity syscall, PC7ffc00000110, LR702ad510,
X0=62hex(98), X1=186001b72b0. Original FDE702ad480..702ad584 statically supplies
FUTEX_WAIT_PRIVATE/op80hex, a dynamically loaded expected word in W3 and null
timeout. W3 and the calling virtual/native thread are not captured. A new
worker token4/entry70383624 is observed after dladdr, but interleaved logs do
not establish its role or identify it as the syscall caller. The final text
fragment is incomplete. A real futex provider must preserve compare/enrollment,
wake counts and the existing signal/root admission limits.

Both terminal frame outputs match the24 original Managed files/24570231 bytes,
metadata23317064/version24 and original unity.ver638477124699603280. The new
audit independently rehashes215 delta/build/seal files, including181 new
snapshots, and links unchanged object/header/module metadata to Game24's full
audit and the new builder/runner complete input checks. It does not repeat or
claim a fresh8370-file physical rehash. Aggregate SHA256 is
`2636716e899cfd9650c50947c2b2880487c97f90eb1edaf420ee38569b22a43b`;
report `work/game25-runtime-boundary-audit/REPORT.md` SHA256 is
`265a1056b8823766538dd77d681c7a78c5aa591aa62ba73a0a1d81e2866e90fd`.
General GC/roots, retention/reclamation, initialization, nativeRender return,
an actual image, gameplay and normal shutdown/persistence remain open.

Game26 freezes the private futex provider at host4137c3bb. Input SHA256 is
`8439c46c0d5d53117abe66f9dbf81123f647871054e22723df152fb3c82a8ad1`;
executable SHA256 is
`cfab26a5462f45216b02b428b69ff459ae7d25acca2ceb3c0d796d8717317579`.
The3575 guest objects/456684 heads and v2 cooperative contract are unchanged;
the complete CMHI candidate remains unselected. Default/init/surface pass.
Standard muted startup retains the nonzero signal30 guard; the separate
collector profile completes the original E4 stop/restart with both physical
register checks, both original posts and observed record5. Both muted frame
profiles return focus/resume/master mute without a hardware-volume observer.

Original dlsym("end") again returns87cb1e78 and dladdr returns0. Worker4,
entry70383624/native TID1197904, then enters the actual futex dispatcher:
number98, op80hex, expected word0, null timeout. The owned stack contains
saved caller702f161c at SP+24 under LR702ad510. This establishes the syscall
caller identity, rather than inferring it from adjacent interleaved output.
No syscall return, wake, explicit enrollment or physical-blocking outcome is
recorded before a different thread reaches the fatal getpriority import.

JNI lookup leaves NoClassDefFoundError for android/os/Process. Unity then
calls getpriority with which0 and who1197904 at LR70438a80, matching worker4's
native TID; the query's calling thread is not logged. Original FDE70438a4c
first invokes static Process.setThreadPriority(II)V through70438d44, then
unconditionally verifies native priority. The actual requested enum/nice is
not observed. The next provider must share one real owned-thread service
between JNI and native query, preserve Android errno/exception behavior and
explicitly bound its Windows scheduling translation.

Both frame outputs retain24 APK-identical Managed files/24570231 bytes,
metadata23317064/version24 and original unity.ver638477124699603280. The
independent delta audit checks220 new files/192 snapshots and links unchanged
guest artifacts to the prior full proof; it does not replay all old objects.
Aggregate `work/windows-game26/game_final_audit.json` SHA256 is
`4f4a8222c06a3f57eb88845581ad8c63fbc70e4f6ff6399919cee2f855aad757`;
report `work/game26-runtime-boundary-audit/REPORT.md` SHA256 is
`378c272b069f09cd0ea7f3b4b3d66c8ad3c3332c06fd5cd1bac76c0ec74aa050`.
No public initialization result, nativeRender return, image, gameplay, general
collector safety or normal persistence/teardown is claimed.

Game27 freezes the owned native priority/JNI provider at hostbc438ce66. Input
SHA256 is `b2788343fc48c65cacc1bb0b764fc0e2ed124f8a7c6e894129bc5fda1f96cc1f`;
executable SHA256 is
`c6d5e51878ff228563d4632b54e80b6db178056570d022d7b340f0473e5c97fe`.
The3575 guest objects/456684 heads, v2 cohort and State/header contracts are
unchanged. Default/init/surface pass and standard muted startup retains the
signal30 guard. Both frame profiles return actual focus/resume/master mute
without a hardware-volume observer. The collector profile again completes
the bounded E4 cycle with both physical register checks, both original posts
and observed record5; dlsym("end") returns87cb1e78 and dladdr returns0.

Worker4 enters the existing private futex syscall98 with expected0/null
timeout from native TID1321820, owned stack bounds and saved caller702f161c.
There is still no observed futex RETURN/wake or explicit blocking outcome.
The original Process.setThreadPriority callback now observes caller1322936,
target1321820, nice0 and return error0. Actual getpriority(PRIO_PROCESS,
1321820) at LR70438a80 returns0/errno0. No missing Process-class exception
occurs. These records do not expose the setter's before-query value or prove
whether native SetThreadPriority was invoked, omitted or changed a level.
The equal-priority shortcut is a source-consistent inference, not an observed
branch. Actual native changes/readback are separately component-qualified.

The next syscall ENTER is token2/native TID1322936, number122, target1321820,
length4 and pointer2377a60f980 at LR70438a10. The existing futex-only dispatcher
correctly rejects it. Original FDE7043890c..70438a4c stores a four-byte affinity
mask at SP+60, maps zero toFFFFFFFF and ignores the syscall return. A dynamic
wrapper and a fixed-1 wrapper share the same child entry, so this run cannot
establish actual mask bytes or wrapper selection. No sched_setaffinity
operation/return or native scheduling change is observed.

Both terminal frame trees retain24 APK-identical Managed files/24570231 bytes,
metadata23317064/version24 and unity.ver638477124699603280. The delta audit
checks317 new/bounded files and inherits Game26's full proof without replaying
old guest objects. Aggregate `work/windows-game27/game_final_audit.json`
SHA256 is `8e2c3819ee3a680bbbc099c95145680eb37408004ada3dbb0162ac624c564adc`;
report `work/game27-runtime-boundary-audit/REPORT.md` SHA256 is
`400f6ac0044ced18e78596d6de3b3fa15f7bf2b561fbbc6bb4180140dd23304a`.
No public initialization result, nativeRender return, rendered image, gameplay,
general collector safety or normal persistence/teardown is established.

Game28 freezes the qualified native affinity provider at host4f7db3e1. Input
SHA256 is `fb62b0cf1f0521c9459a41bd1f701b3000a5328147a18f54b5769766638341da`;
executable SHA256 is
`c4213257a98172dc50fa8d4fa6915705f238bc2923f01c3b48d006b61ea5bbc9`.
All3575 guest descriptors/456684 heads, v2 cohort, State and four headers remain
unchanged. Default/init/surface pass, standard muted startup retains signal30's
guard, and the collector profile completes the bounded E4 cycle with two
physical register checks, two original posts and observed record5. Both muted
profiles return original focus/resume/master mute without a volume observer.

The collector run now observes17 real SetThreadAffinityMask calls. Each actual
four-byte snapshot isFFFFFFFF; native process/system/effective masks areFFFF,
and native previous/readback masks areFFFF. Every call reports native_set1,
readback_valid1, result0 and actual syscall return0/errno0. These are real native
operations on already equal effective masks, not evidence of a changed mask.
More workers start. Thirty-four complete priority setter records and33 complete
native query records are logged (17return0,16return10); the final getter line is
incomplete and supplies no complete additional result.

Seventeen untimed futex ENTER records have no corresponding RETURN/WAKE; no
enrollment/blocking/wake result is inferred. Worker token15hex/native TID1344644
then enters syscall98 at LR708f2f14, uaddr1ec40012590, op80, expected0 and nonnull
timeout1ed1ea50ef0, equal to its actual SP. The existing untimed-only provider
rejects that shape. No timespec bytes, timeout duration, timed wait outcome or
application role is logged. Original FDE708f2ec8..708f2f20 converts a uint32
millisecond input to16 bytes of relative seconds/nanoseconds; its largest input
is49.7 days. Static callers do not identify this particular dynamic input.

Both terminal frame trees retain24 APK-identical Managed files/24570231 bytes,
metadata23317064/version24/mapped23318528 and unity.ver638477124699603280. Both
read an existing one-entry v2 preference store and perform original version
marker writes/status0; final CheckPersistence is not reached. The independent
audit checks297 bounded inputs/build artifacts and links the unchanged old
guest proof without replaying its physical COFF files. Final aggregate
`work/windows-game28/game_final_audit.json` SHA256 is
`a0d4719a6ec58b48f5b79eb4d0e21a3049a21c25fa0a6f405e5b554bdbf540c3`;
report `work/game28-runtime-boundary-audit/REPORT.md` SHA256 is
`775ae0d1bebdd4dd2f4be26e6dca1f9d1f5cb10199b6df6de312d62e78ca7e89`.
The returned public initialization result, nativeRender return, actual image,
gameplay, general collector safety and normal shutdown/persistence remain open.

Game29 freezes relative timed private WAIT at hoste040d70d. Input SHA256 is
`864d57d6d045eb7f44303e3af8432f389f9a6bf64ce33d27c8130d85b8a9ed93`;
executable SHA256 is
`d39f4bf9eca96e9a6bc17c6235ba9e2be79f422e4653f7dcdfabf9c6bb8cd802`.
Guest objects/456684 heads, v2 cohort, State/header contracts and all prior
non-futex providers remain unchanged. Default/init/surface pass. Standard muted
startup retains the signal30 guard; both frame profiles return focus/resume/
master mute without a hardware-volume observer. The collector profile retains
its bounded two-post/two-physical-check E4 cycle and observed record5.

Nineteen real affinity operations/readbacks return0, with requestFFFFFFFF and
native process/system/effective/previous/readbackFFFF. Thirty-five complete
priority setter/query pairs report18level0, onelevel1 and16level10. Seventeen
untimed futex entries have no RETURN/WAKE. Two additional timed entries from
native TIDs1367524/1367564 copy actual4294967s +295000000ns snapshots, with valid
active-monotonic deadlines4408240276570800/4408240283775500. This confirms the
parse/deadline witnesses, not ticket enrollment, physical blocking or return.
There is no timed RESULT before process failure.

The final original-run record is native exceptionC0000005 at7ff6ddc600db during
the frame stage, constructors417/417. The canonical run exits native5. Its
exception logger supplies only the instruction address, not the actual loaded
module base, access kind, accessed address, register context, native TID or
active guest State. The PE is ASLR-enabled, so its preferred140000000 base
cannot normalize that address. The last logged worker/main activity does not
identify the faulting thread. Read-only wait ownership review found no concrete
defect; no wait-provider or translation cause is assigned from these artifacts.
Any later exact-executable debugger replay uses separate fresh data/evidence.

Both terminal frame trees retain the24 APK-identical Managed files/24570231
bytes, metadata23317064/version24 and unity.ver638477124699603280. Preference
reads see the existing one-entry store; version writes return status0. Final
persistence/teardown checks remain unreached. The independent audit checks1976
bounded pins, including1910 new snapshots, and inherits the unchanged old
object proof without physical COFF replay. Canonical aggregate
`work/windows-game29/game_final_audit.json` SHA256 is
`fc1f75a9399124b4338011a8f1dcd7c45c3eed010895fb59f8de5878ca6ea6fa`;
report `work/game29-runtime-boundary-audit/REPORT.md` SHA256 is
`6e2e54fbabb7a3afec6ac81555b5a2c9a5f29d29c1cda0dd1d8106ca79d87d00`.
No public initialization result, nativeRender return, image, gameplay, general
collector safety or normal shutdown/persistence is established.

Game30 freezes the EXT sort repair at host2d127bb04. Input SHA256 is
`5b40e5c06b6ca1fb163d7ee66d940768bae1ca1daf89037f88d91c29862fa2a6`;
executable SHA256 is
`4ebd473283f9b2226132aaaa3467c7f80a68e2744ce7a3e3bc7350c7f08f5e86`.
The v3 cohort retains the existing prefetch repair and replaces only Unity
shard78, with only the complete original sort FDE changed. Its other127 raw,
polled and native function bodies remain identical. Other3574 guest-object
descriptors, original ELF/APK bytes, State and providers are unchanged.
The corrected instruction removes one semantic loop:456684 heads,
122088 cycle cuts and578772 poll sites. Component and original-prefix
evidence is in [the EXT/sort audit](unity_ext_sort.md).

Default/init/surface each return native0/controller0. Standard muted startup
retains the signal30 guard at LR825b2d1c. The collector profile returns
native3/controller1 at `recomp: unresolved indirect target at 0x70b5b648`.
No native exception record or returned nativeRender is observed. The error
does not identify the active caller, thread, LR, table index or a returned
original sort call; those are not inferred from neighboring worker logs.

Static original/selected-code audit identifies70b5b648 as executable Unity
.text inside FDE70b5ae80..70b5c138. Original BR X15 at70b5b644 uses a bounded
ten-entry signed-offset table at70fd0134. Its five unique destinations are
70b5b488,70b5b4b0,70b5b4bc,70b5b648 and70b5b674, all absent from the selected
catalog. Selected shard386 retains the original table load/add and
`__remill_jump` dispatch. This establishes missing continuation coverage,
not a PLT import or permission to route an internal case to the FDE prologue.
Read-only target proof `work/game30-indirect-target-audit1/proof.json` has
SHA256 `67218fa4852147b98ee60a42a0456c2ae139051d8ea19ee660b1bb985cd9ea74`.

The collector run again records the bounded E4 cycle: two physical register
checks, both original posts and observed record5. Nineteen real affinity
operations/readbacks return0;35 priority pairs report18level0,onelevel1 and
16level10. Seventeen untimed and two timed futex entries have no observed
RETURN/RESULT/WAKE. Both timed copies are4294967s +295000000ns, with actual
deadlines4414098153472500 and4414098160526600. No wait enrollment, physical
blocking, expiration or return follows from these copy records.

Both terminal output trees contain24 APK-identical Managed files/24570231
bytes, metadata23317064/version24 and unity.ver638477124699603280. Original
one-entry v2 preference reads and version-marker writes/status0 are observed;
final persistence checks remain unreached. The incremental audit checks98
fresh pins and preserves the old1910-snapshot map without copying/replaying
those snapshots or old COFF files. Canonical aggregate
`work/windows-game30/game_final_audit.json` has SHA256
`8f51c5216b33194ed6d83ff224d0047f4cfc291d72ceb92c6161c6b9bf6f4b7f`;
report `work/game30-runtime-boundary-audit/REPORT.md` has SHA256
`a66cb4e117d4535dce18ece6bad8e4fa829ba6ec26df579c52f9a33669ac128c`.
Public initialization result, nativeRender return, image, gameplay, general
collector safety and normal shutdown/persistence remain open.
