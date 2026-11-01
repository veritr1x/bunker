# Native Windows host gates

These adapters support the ARM64-to-x86_64 recompilation path. They do not yet
boot the real Unity player, initialize its graphics/audio host, or run the game.
Unsupported JNI methods and unavailable translated modules fail explicitly.

Logging snapshots its configuration under its provider lock, then invokes
output/log/stream/error/allocator callbacks without that lock. Callbacks may
run concurrently and must synchronize their own shared host state. The
eight-check callback gate joins worker formatters, replaces a sink from a
callback worker, and verifies exception recovery on Linux and native Windows;
the existing formatter, logging and ARM64 variadic reference gates also pass.

`Class.getClassLoader()` and three-argument `Class.forName` use the explicit
class catalog. The host keeps stable application and Android `BootClassLoader`
objects; a null loader selects bootstrap lookup. This follows Android13's
[Class.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/Class.java)
and [ClassLoader.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/ClassLoader.java).
Unknown names, wrong reference types and unconfigured loaders fail explicitly.
Metadata-only classes reject initialization requests; `MarkClassInitialized`
is reserved for classes whose actual initialization effects the host supplies.
There is no Java bytecode interpreter, array-class synthesis or custom Java
class-loader execution. NDK-translated direct, V and A callers cover lookup,
loader identity, errors, local frames, globals and attached-thread ownership.
Run `prepare_class_loader.py --ndk ... --lift ...`, then
`test_class_loader.ps1` on Windows.
The 109-check gate also verifies callbacks can join another attached JNI thread:
external object handlers run outside the host registry lock, with receiver and
callback lifetimes retained, then their results are validated under the lock.
Object-returning calls produce a fresh caller-local reference. Returning a
cached global or local from a host callback preserves that original reference
when the caller deletes its result; foreign-thread local returns are rejected.
`Object.toString`, initialized host `Throwable` messages and `String.toString`
follow the Android13 contracts, including virtual object-method dispatch,
localized-message overrides and null-versus-empty messages. Default object
identity hashes remain stable. Unimplemented Java overrides and uninitialized
throwable state fail explicitly. Primary implementations are
[Object.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/Object.java)
and [Throwable.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/Throwable.java).

## Verified behavior

- `jni_host.*`: NDK-compatible JavaVM/JNIEnv pointer tables backed by guest
  marker addresses, checked native registration, explicit class/method/field
  metadata, strings, reference frames, pending exceptions and thread attachment.
- `libmain_test.cpp`: the real game `libmain.so` returns JNI 1.6 from its
  translated `JNI_OnLoad` and registers the two actual `NativeLoader` methods.
- `module_registry.*`: registered translated modules only; `dlopen`, `dlsym`,
  `dlclose`, per-thread `dlerror`, load generations, data resets and ordered
  constructors/finalizers. No raw ARM64 code is executed through Windows APIs.
- `loader_test.cpp`: the real `NativeLoader.load` and `unload` run against a
  clearly synthetic translated Unity fixture. This verifies module plumbing,
  cached loads and lifecycle calls, not actual Unity initialization. A missing
  optional `JNI_OnLoad` symbol succeeds as the original libmain specifies;
  unavailable modules and unsupported JNI versions produce fatal diagnostics.
- `filesystem.*`: virtual mounted paths, guest fd/FILE registries, fixed
  Android AArch64 `stat`/`off_t`/`long` layouts, file/stdio operations, private
  and shared file mappings, anonymous mappings, protection changes and guest
  thread-local errno. Windows CRT structs and FILE pointers do not escape.
  Legacy `__sF` uses the NDK-verified 152-byte opaque FILE stride; standard
  streams are actual owned duplicates, so guest close preserves host logging.
- `android_context.*`: configured Activity/Context metadata exposes
  `getApplicationInfo`, `sourceDir`, `nativeLibraryDir`, `dataDir`, package/SDK
  fields, `getPackageName`, `getApplicationContext` and a typed `getAssets`
  object. Java AssetManager streams and other Java services remain unsupported.
- `file_guest_fixture.c`: actual NDK-compiled ARM64 callers retrieve the
  configured JNI sourceDir and read a real APK ZIP-member range through the
  Windows adapters. fd, stdio and mmap CRCs match the original bytes; sparse
  files exercise offsets and metadata above 4 GiB.
- `pthread_host.*`: Android-sized opaque mutex/condition/rwlock registries,
  recursive/errorcheck/static initializers, realtime/monotonic condition waits,
  once, generation-checked TLS keys, and native Windows workers. Start routines,
  once callbacks and TLS destructors execute translated traces through
  `Runtime::Run`. Workers have separate guest State, stack with inaccessible
  guard pages and TLS storage; stable tokens do not alias reused OS thread IDs.
  Native and actual NDK-translated callers verify contention, broadcasts,
  destructor rounds, join results, explicit exit, detach and interrupted once.

## Commands on this machine

Run preparation from WSL with the existing `recomp/work/tools` Python environment
(pyelftools), built Remill lifter and Android NDK. Run the PowerShell scripts
with the installed MinGW compiler. Input APKs and all generated binaries,
reports and payloads belong under ignored `recomp/work/`.

```text
python recomp/windows/inventory.py --lib-dir <extracted-libraries> --apk <game.apk> --out recomp/work/windows-jni/inventory.json
python recomp/windows/prepare_loader.py --libmain <libmain.so> --lift <remill-lift-18> --cc clang-18 --cxx clang++-18
python recomp/windows/prepare_files.py --apk <game.apk> --ndk <NDK-root> --lift <remill-lift-18> --cxx clang++-18
python recomp/windows/prepare_pthreads.py --ndk <NDK-root> --lib-dir <extracted-libraries> --lift <remill-lift-18> --cxx clang++-18
```

```powershell
python recomp/windows/prepare_zlib.py
recomp/windows/test_jni_host.ps1 -JniHeader <NDK-jni.h> -LibMainDirectory recomp/work/windows-libmain -LibMainLibrary <libmain.so>
recomp/windows/test_loader.ps1 -BuildDirectory recomp/work/windows-loader
recomp/windows/test_files.ps1 -BuildDirectory recomp/work/windows-files
recomp/windows/test_pthreads.ps1 -BuildDirectory recomp/work/windows-pthreads
```

The file preparation command compiles an independent layout probe with the
actual AArch64 NDK and records its values in `ndk_layout.json`. It also records
the APK SHA-256, asset offset/length/CRC, package, target SDK and launch Activity
from the APK and `aapt`; metadata is not guessed from desktop conventions.

## Real game boundary

The inspected 3.7.1 APK is `com.square_enix.android_googleplay.nierspww`, version
code 152, minimum SDK 24, target SDK 33, with
`com.google.firebase.MessagingUnityPlayerActivity` as its launch Activity.
`libunity.so` has 344 direct imports and 417 initializer entries. Its
`JNI_OnLoad` is at RVA `0x43a950`, attaches the current thread and invokes nine
registration/setup helpers. The inventory finds 51 native-method table
candidates; this is an inventory count, not proof that every table is active.

None of the inspected native libraries imports an `AAsset*` function. Unity
instead imports file/stat/mmap and zlib operations, and contains
`assets/bin/Data`, `jar:file://`, and `ApplicationInfo.sourceDir` references.
The current resource gate therefore follows that actual file path rather than
adding an unused native asset facade.

Remaining host work includes real Unity constructors/bootstrap and its full
JNI class/service catalog, directory/statfs APIs, networking/signals,
graphics/window/audio/sensor hosts, and resource decompression integration.
The file adapter deliberately rejects unsupported mapping features such as
destructive `MAP_FIXED`, partial unmaps, anonymous shared mappings, and symlink
`lstat` rather than claiming POSIX behavior it does not implement. Directory
mounts currently inherit Windows case handling. Only mounted paths are exposed.

The pthread adapter covers the actual imported set. Nonzero `pthread_kill`,
`pthread_sigmask` and `pthread_atfork` return Linux `ENOSYS`; IL2CPP GC signal
suspension is still a blocker. Cancellation, process-shared primitives, custom
user stacks and scheduling policies are unsupported. Recursive condition waits
with depth greater than one return `ENOTSUP`. Guest TLS storage is not a full
Bionic internal thread/TLS image or ELF TLS loader. External native threads must
call `ReleaseCurrent()` before exit when guest TLS destructors are required;
created guest workers clean up automatically. Token tombstones last until host
destruction, while joined/reaped detached stacks and handles are released.
The provider also owns realtime/monotonic `clock_gettime` so absolute condition
deadlines share the same epoch; wire its `SetErrorSink` to guest errno. Pthread
functions themselves return positive Android errors without changing errno.
For host-driven calls use `Pthreads::Run`, or register an actual guest stack with
`AttachCurrentStack` before calling `Runtime::Run` directly. No raw guest code
pointers are cast to Windows callbacks.

Unity's actual JNI_OnLoad time-baseline path also calls `clock_gettime(7)`
(`CLOCK_BOOTTIME`). This uses Windows' real biased boot interrupt counter via
`QueryInterruptTimePrecise`, with the real `GetTickCount64` counter as a coarser
fallback. These clocks include sleep/hibernation as documented by Microsoft:
[interrupt time](https://learn.microsoft.com/windows/win32/sysinfo/interrupt-time),
[precise counter](https://learn.microsoft.com/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryinterrupttimeprecise),
[Windows tick time](https://learn.microsoft.com/windows/win32/sysinfo/windows-time).
The existing monotonic/condition epoch is preserved. Direct and actual NDK
callers verify boot epoch, progress, guarded 16-byte LP64 output and explicit
unsupported-ID errors; all 70 pthread checks pass. No suspend cycle was forced.

File and pthread adapters now participate in the runtime's tracked guest-memory
protocol. File paths/modes and write buffers are snapshotted; fd/stdio reads use
64 KiB bounce buffers and publish only actual bytes read, including an incomplete
final `fread` item. Stat and errno outputs use tracked writes. The file registry
is released during blocking I/O; an owned resource lock preserves its handle
and offset. No shared-memory lock crosses OS I/O or translated callbacks.
`FileSystem::SetError` is the tracked errno sink for other providers.

Pthread attributes, key/thread result outputs, opaque initializer/once words,
clock outputs and allocation lifetimes are tracked; timed waits copy their
deadline before blocking. Cross-thread gates verify real fd/fread ABA, same-value
stat/errno/key/join outputs, pthread attribute/mutex ABA, and that EOF/input-only
snapshots leave reservations intact. The suites pass 72 file and 65 pthread
checks, retaining the real APK and actual translated NDK caller gates.
Mapping allocation/unmap lifetimes invalidate monitored ranges. Concurrent
external OS writers and aliases of a shared file mapping remain outside this
address-based protocol; these tests do not claim that such backing-file changes
participate in guest exclusive reservations.

`prepare_pthreads.py` checks NDK public sizes, offsets, initializer words and
limits with an independent AArch64 object probe. Private attr flags follow
[Bionic Android 13 pthread internals](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/pthread_internal.h)
and its [condition implementation](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/pthread_cond.cpp).

## Actual Unity diagnostic gate

`unity_bootstrap.cpp` combines the checked providers, loads the original Unity
ELF as data, runs every one of its 417 constructors in order, then attempts its
real `JNI_OnLoad`. Preparation extracts the 138 Unity class declarations plus
the two AndroidGameSDK classes actually referenced by its nine registration
helpers, all from the original APK. It derives and verifies all 42 native
bindings against DEX declarations and verifies ELF/translation hashes. The executable independently
hashes its actual APK/Unity input paths before execution. Unsupported imports
abort with their name, guest address/return address and constructor progress;
missing data imports are refused rather than fabricated. Complete Android Java
inheritance and method implementations remain separate work.

```text
python recomp/windows/unity_bootstrap_prepare.py --translation <whole-unity-output> --library <libunity.so> --apk <game.apk> --aapt <aapt>
```

```powershell
recomp/windows/unity_bootstrap_build.ps1 -BuildDirectory recomp/work/windows-unity-bootstrap -Run -Apk <game.apk>
```

The default preparation rejects unsupported translated traces. Explicit
`--exploratory` permits a diagnostic run with incomplete instruction coverage,
retains reached-instruction aborts, labels its remaining unsupported traces,
and still executes every real constructor. `--metadata-only` and PowerShell
`-CompileOnly` check harness compilation while translation is running; neither
is execution evidence. A constructor/JNI-only pass would still not initialize
the game surface, graphics/audio host or gameplay lifecycle.

The first actual Windows diagnostic build linked 58,850 translated traces in
463 objects, with 2,419 unsupported traces explicitly retained for exploration.
It provided 163 of Unity's 344 imports and installed abort diagnostics for the
remaining 181 strong function imports. Constructors 1–52 completed; constructor
53 (`0x700bbe08` at base `0x70000000`) reached an unsupported indexed FP store
near RVA `0xbce50`. JNI_OnLoad has therefore not run yet. A deliberately wrong
APK was rejected by the executable's runtime hash check before constructor 1.

The next scalar-store snapshot linked 58,855 traces with 2,151 remaining
unsupported traces. With the verified static zlib provider installed, 168 imports
are provided and 176 retain explicit failure markers. Constructors 1–70 now
complete; constructor 71 (`0x700c0b20`) reaches unsupported pair-exclusive
`ldxp x10,x11,[x0]` at RVA `0x3830a0`, followed by `stxp` and a retry loop.
The log and translation manifest are preserved as `unity-bootstrap-ctor71*`
under ignored `recomp/work/windows-unity-bootstrap/`. JNI_OnLoad remains unrun.

The separate `whole/test_reg_stores.py` gate compares 69,632 complete-buffer
cases against ARM64 QEMU on both Linux and native Windows: all 32 source vector
registers, all four scalar widths, extension/scale modes, signed offsets,
unaligned addresses, SP and zero-index forms. Its 2,176 generated variants
include the byte-LSL decoder alias fixed after the Unity snapshot above.

The pair-exclusive snapshot retains 1,860 unsupported traces. Its actual Windows
run completes constructors 1–94; constructor 95 (`0x700c219c`) reaches unresolved
indirect target `0x7036ef74`. The five-entry signed jump table at RVA `0xecc468`
uses equivalent masked W/X index expressions and resolves to real code blocks
`0x36ef74`, `0x36ef60` and `0x36eed0`. Logs and the manifest are preserved as
`unity-bootstrap-ctor95*`; no constructor was skipped and JNI_OnLoad remains
unrun.

The masked-switch snapshot has 59,552 traces, 469 objects, 1,889 unsupported
traces and zero unresolved direct targets. The actual Windows run completes
constructors1–128. Constructor129 (`0x700c491c`) first required `getpagesize`;
after the checked native page-size adapter, it reaches unresolved indirect
target `0x708f27cc` from the signed table at RVA `0xf50540` / BR `0x8f27c8`.
`unity-bootstrap-ctor129*` preserves both diagnostics and translation metadata.
Every prior constructor ran; JNI_OnLoad has not run yet.

The joined-guard snapshot (59,558 traces, same unsupported count) gets past
that indirect target. Constructor129 next requests `madvise` with advice0
(`MADV_NORMAL`) at RVA `0x8f2cf8`; the unavailable import aborts explicitly at
return `0x708f2cfc`. `unity-bootstrap-ctor129-madvise*` preserves this run and
its exact link metadata. Constructors1–128 complete; JNI_OnLoad remains unrun.

`madvise` implements the evidenced advice0 (`MADV_NORMAL`): registered mappings
and other committed Windows ranges retain their normal/default paging policy.
It checks Android page alignment, length rounding/overflow and complete committed
range coverage; aligned zero-length calls succeed, errors set guest errno,
and success preserves errno. Every other advice returns `EINVAL` explicitly.
The check uses mapping provenance and
[VirtualQuery](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualquery),
including committed ELF/heap/stack pages owned by other providers. It follows
[Linux do_madvise](https://github.com/torvalds/linux/blob/v6.1/mm/madvise.c)
validation order. This operation does not write or discard bytes, change page
protection, commit reserved pages or invalidate guest exclusive reservations.
[MEM_RESET](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc)
is not used; discard/zero-fill advice remains unsupported.

With that adapter, the actual native Windows executable completes ALL417
constructors in order, returns JNI1.6 from the real Unity `JNI_OnLoad`, and
verifies all42 native addresses across the nine classes against ELF/DEX data.
The earlier1,889-unsupported snapshot stopped at teardown: finalizer
`0x700dd2dc` called `__cxa_finalize` with DSO `0x7123eac0` and encountered a
missing translated callback root. That diagnostic is preserved in
`unity-bootstrap-all417-jni42-finalize*`; the callback/ST1 snapshot below fixes
it. These remain exploratory gates and the game is not running.
The file suite passes103 checks including actual NDK advice callers, committed
CRT/image pages, reserved holes, protection preservation and a successful
cross-thread exclusive reservation across the non-mutating normal hint.

`unity_bootstrap_build.ps1 -Run -InitJni` (executable `--init-jni`) optionally
attempts the exact registered instance-native `UnityPlayer.initJni(Context)V`
after the full constructor/JNI verification. The default gate stops before
this entry. It uses typed host UnityPlayer/Activity objects in a local frame;
it does not execute or mark Java class initializers/constructors complete.
This is an isolated native-entry diagnostic, not the APK Java lifecycle or
game startup. Java services, missing method/field behavior and class
initialization still fail explicitly. Surface/render/resume are not invoked.
The first actual optional run reaches entry `0x70439db0`, then aborts in native
pending-exception formatting: `strncpy` at return `0x70ab521c` receives source0
and length256 after the unavailable `Object.toString()Ljava/lang/String;`
lookup/call. At that point the original Java exception had not yet been
captured; this secondary failure was not treated as a string-copy success case.
Evidence is `unity-bootstrap-init-jni-strncpy.log` and
`java-startup/latest-native-gates.json`.
The opt-in diagnostic now forwards the original JNI table handlers and records
new pending exceptions before native code clears/formats them. A trace-table
wrapper at `0x70ab5020` was bypassed by direct calls and was not used as proof.
The reached JNI wrapper proved the original missing class was
`bitter/jnibridge/JNIBridge`. Its exact APK declarations are now included
(141 classes); its Java proxy bodies remain unimplemented.

With the validated callback/ST1 snapshot (59,561 traces, 469 objects, 1,774
unsupported traces), the default native Windows gate exits0: all417
constructors, real JNI_OnLoad/42 bindings, JNI_OnUnload and both finalizers
complete. See `unity-bootstrap-callback-roots-default.log`.
The separate optional initJni diagnostic now gets past JNIBridge and string
formatting, then records `NoClassDefFoundError: java/lang/StringBuilder`.
Native initJni clears that exception and returns, but the harness rejects
the gate because it observed the unsupported Java operation. No lifecycle
completion is claimed. See `unity-bootstrap-init-jni-stringbuilder*`.

StringBuilder now implements only the three evidenced methods: default
construction, `append(String)` and `toString`. It preserves UTF16 units,
appends `null` as four characters, returns a fresh local alias from append,
and copies nonempty snapshots. Empty snapshots share Android13's constant
empty string. `prepare_string_builder.py` / `test_string_builder.ps1` pass66
native Windows checks using six actual NDK traces, including direct/V/A and
the va_list stack path. Uninitialized instances, wrong types, unsupported
constructors and other Java bodies fail explicitly. Contracts follow
[StringBuilder.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/StringBuilder.java)
and [AbstractStringBuilder.java](https://android.googlesource.com/platform/libcore/+/refs/tags/android-13.0.0_r1/ojluni/src/main/java/java/lang/AbstractStringBuilder.java).
The default native gate still exits0 (`unity-bootstrap-stringbuilder-default.log`).
The separate initJni gate now reaches the next missing service method,
`Activity.getIntent()Landroid/content/Intent;`, and fails on the captured
exception history (`unity-bootstrap-init-jni-getintent*`).

Activity.getIntent now exposes a configured MAIN/LAUNCHER launch with the
component package/activity taken from APK metadata. Extra/data properties are
absent by default. Explicit string, integer, boolean and null extras retain
their types: Bundle.getString uses its default for absent/null/wrong-type
values, getBoolean defaults to false, and containsKey preserves presence.
Intent.getExtras returns independent Bundle copies. URI/string/component
properties and Bundle string values retain their identities and lifetimes
through internal object-graph references, without extra native global roots.
Unconfigured objects, wrong payloads/types and unknown services fail explicitly.
This follows Android13 [Intent.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/content/Intent.java)
and [BaseBundle.java](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-13.0.0_r1/core/java/android/os/BaseBundle.java).
The real makeMainActivity factory sets no task flags; no package selector is
invented when its component is already explicit.

`prepare_context.py` / `test_context.ps1` pass83 native Windows checks through
seven actual NDK traces: object/boolean direct/V/A, two-argument register/stack
boundaries, APK component metadata, optional data/extras, type/ref errors,
cross-thread globals and object lifetimes after Context/frame destruction.
The optional real initJni gate now passes Intent lookup, then records the next
unsupported method, `AssetManager.open(String)InputStream`, for actual
`bin/Data/boot.config`. Exception history still fails the gate, preserving
`unity-bootstrap-init-jni-asset-open*`. The default gate exits0 again;
`unity-bootstrap-intent-default.log` includes both real finalizers.

The checked AssetManager/InputStream/Scanner bridge now reads boot.config from
the configured original APK through `ApkAssets`. It implements the observed
UTF-8 Scanner constructor, `useDelimiter("\\z")`, `next()` and close behavior,
including EOF, missing assets, wrong types, closed streams and reference
lifetimes. Other delimiters, charsets and malformed UTF-8 replacement remain
explicitly unsupported. `test_asset_java.ps1` passes65 native Windows checks
through11 actual NDK traces, covering direct/V/A constructors and methods plus
the exact149-byte APK resource with CRC32 `f53e2d64`.

The isolated real `initJni(Context)V` gate now exits0 with no pending exception
and zero original JNI exception events. All417 constructors, JNI_OnLoad/42
bindings, JNI_OnUnload and both finalizers also complete. Evidence is
`unity-bootstrap-init-jni-assets-success.log` and its translation manifest;
the separate default run is `unity-bootstrap-assets-default.log`. This remains
an exploratory native-entry gate with1,774 unsupported traces. The Java
Activity/UnityPlayer lifecycle, surface creation, rendering and resume have
not been executed, and the game is not running.

`unity_lifecycle.h/.cpp` ports the evidenced surface subset of UnityMain's FIFO
to a dedicated JNI-attached host worker. After real initJni succeeds, the
explicit post-init transition matches constructor DEX0x554a40. A nonnull surface
queues recreate then SURFACE_ACQUIRED; a change queues the changed notification
after those operations. Destruction queues SURFACE_LOST before recreate(null)
and waits for acknowledgment before HWND closure. Queued Java graph references
become fresh worker-local JNI references. Runner TLS cleanup happens before JNI
detach. The worker remains paused and never schedules render/resume.
`test_unity_lifecycle.ps1` passes 53 native Windows checks; the same test passes 53
on Linux. These use explicitly synthetic Runtime callbacks to test ordering,
thread/ref lifetimes and failures; they do not prove the real surface entries.

The separate optional harness flag `--surface-gate <width> <height>` (build script
`-SurfaceGate -ClientWidth ... -ClientHeight ...`) requires explicit landscape
client pixels and verifies the real HWND dimensions. The manifest specifies
sensorLandscape, without fixed pixel dimensions. This gate ports the native
surface-call sequence only: it does not claim the APK's View/splash UI, phone,
clipboard, camera and HFP Java constructor effects or Java class initialization.
The first real attempt reached missing `sigemptyset`, return address
`0x704233c8`, in temporary crash-handler setup. That earlier evidence remains
in `unity-bootstrap-surface-sigemptyset.log` and its translation manifest.
This combined harness keeps NativeWindows markers at `0x7ff440000000`, separate
from the module registry, native-window tokens and EGL marker/handle ranges.
The process-only signal adapter now supplies checked dispositions and pure
sigset helpers for this gate. Thread signal masks/kill retain their existing
owner, and sigaltstack remains unresolved. The next preserved diagnostic was
missing `setjmp`, return address `0x7043a04c`, in
`unity-bootstrap-surface-setjmp.log` and its translation manifest.

Normal setjmp saves now use the checked Android wire adapter, actual GetAttr
guest stack, lifetime-unique Self token, and compiler executable-section ranges
(the saved return address is interior code, not a trace head). WorkerEnter
registers/binds a virtual signal thread after JNI attachment and before startup
acknowledgment; its real parent-model mask is captured at Start. Runner TLS
destructors execute while those registrations remain live, then captured tokens
retire without calling Self again. The actual scope buffer is inside a verified
writable FileSystem-owned mmap with an epoch. This establishes the mapping's
lifetime, not individual Unity arena-subobject reuse. Unknown heap buffers fail;
longjmp control transfer remains explicitly unsupported.

The actual exploratory surface gate now exits0: all 417 constructors,
JNI_OnLoad/42 bindings, initJni, surface-created/change/notification/detach,
JNI_OnUnload and both finalizers complete. Exact original-provider observation
proves two guest ANativeWindow_fromSurface calls, two acquires and four releases
for one actual 960×540 HWND, with native detach acknowledgment before closure.
See `unity-bootstrap-surface-success.log` and its translation manifest. No EGL,
nativeRender or nativeResume was executed; 1,774 unsupported traces remain and
this is not a game-startup or Java-constructor-completion claim.

Read-only disassembly of the actual APK is preserved under
`work/windows-unity-bootstrap/java-startup/`. `startup-order.json` records exact
DEX method offsets/signatures: the Activity constructs UnityPlayer, whose
success path loads main/Unity, calls instance `initJni(Context)V`, creates the
SurfaceView/holder callbacks, then starts UnityMain's Looper/Handler thread.
Surface/state messages gate rendering. The Windows host has not yet executed
this Java lifecycle; calling render/resume immediately after JNI_OnLoad would
skip required setup evidenced in the APK.

The nine JNI_OnLoad helpers perform `FindClass`/`RegisterNatives`, with
`FatalError` on failure. They do not fetch additional framework fields or
methods or initialize camera/VR/display hardware. Beyond the Unity-prefix
catalog, the evidenced classes are `com/google/androidgamesdk/ChoreographerCallback`
and `com/google/androidgamesdk/SwappyDisplayManager`. Descriptor types Activity,
Context, InputEvent, Surface, Object and String were checked with the installed
SDK/JDK `javap`. This is declaration and registration support, not Java bytecode
execution; Java service side effects required by later native lifecycle calls
remain separate host work.

`libc.h/.cpp` provides Android-width allocation, memory/narrow-string functions,
C-locale character classification, LP64 integer parsing and the scalar math
imports found in Unity/IL2CPP. Windows `long` is never used as an Android long.
Aligned allocations are tracked so common `free`/`realloc` also accept them;
ordinary allocation uses the same CRT family as logging's `asprintf`.
`getenv`/`environ` expose only `SetEnvironment` configuration and subsequent
guest `setenv`/`unsetenv`, never the host process environment. The checked
[Bionic locale adapter](locale.md) supplies `newlocale`/`uselocale`/`freelocale`
with C/POSIX and C.UTF-8 aliases and per-thread selection. Wide strings,
long double, sockets and signal integration remain separate work.
Math uses the native host libm; it is not a bit-identical Android libm port.
Integer prefixes follow the targeted
[Android 13 parser](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/strtol.cpp):
base zero recognizes hex/octal prefixes, while `0b2` consumes just its initial
zero. Binary-prefix behavior introduced in Android 14 is deliberately absent.

Supply `LibC::Runner` through `Pthreads::Run` to execute guest destructor code.
`__cxa_finalize` filters DSOs, invokes callbacks in reverse registration order,
and marks each callback before invoking it so reentrant finalization cannot
repeat it. New registrations during callbacks are included. Plain `atexit`
callbacks receive no argument. The provider does not cast ARM64 callback
addresses to host function pointers. Wire `SetErrorSink` to `FileSystem`'s
thread-specific guest errno. Stack protector failure and `abort` report and
terminate. `test_libc.py` checks the actual NDK LP64 call ABI, allocator contents,
parse overflow/end pointers/errno, virtual environment, math and translated
reentrant destructor callbacks on native Windows and Linux.

`import_audit.py` compiles a native Windows probe and asks each provider's real
`Marker(name)` API about the exact inventory imports. It can also read complete
translation manifests with `--manifest`. It records source/binary hashes,
rejects stale probes, separates missing weak/strong imports, and writes
`work/import-audit/audit.json` and `audit.md`. A provider marker means import
ownership; checked unsupported flags, missing configuration, and unimplemented
platform services are still limitations. It does not claim complete startup
merely because an import has a marker.

`zlib_host.h/.cpp` owns Unity's actual `inflate`, `inflateEnd`, `inflateInit2_`,
`inflateInit_` and `zlibVersion` imports. `AndroidZStream` is the independently
NDK-probed 112-byte LP64 layout; native Windows `z_stream` is 88 bytes. Native
state stays in a sidecar. Guest 64-bit counters accumulate native counter
deltas, including dictionary-header early returns and native 32-bit wrapping.
Custom allocation callbacks execute translated code through the supplied
runner. Default callback pointers are private guest import markers, not native
function pointers. Set up `Zlib` with the same `Pthreads::Run` adapter as libc.

Run `prepare_zlib.py` to fetch the pinned official
[zlib 1.3.2 release](https://www.zlib.net/), verify its published SHA-256
`bb329a0a2cd0274d05519d61c667c062e06990d72e125ee2dfa8de64f0119d16`, and build
`work/zlib-native/libz-inflate.a`. Include headers from
`work/zlib-native/zlib-1.3.2` and link that archive after objects. The upstream
license is retained with the downloaded sources and recorded in `backend.json`.
The Windows executable does not depend on the MinGW `libz.dll`.

`test_zlib.py --apk ...` compiles callers with actual Android NDK headers and
compares their streaming records and output bytes with an ARM64-QEMU reference.
It covers zlib/raw/gzip wrappers, incremental buffers, corruption, truncation,
output exhaustion, dictionary-required status, allocation failures, callback
invocation, and LP64 counters. The inspected real APK's compressed
`assets/bin/Data/boot.config` is also inflated through translated callers with
default and custom guest allocators: 123 compressed bytes become 149 original
bytes with ZIP CRC32 `f53e2d64`. This resource gate does not establish complete
Unity startup.

LibC and zlib now use tracked snapshots/publication and invalidate complete
known allocation lifetimes. Zlib runs on private input/output buffers and mirrors
custom-allocated internal state, publishing changes before guest callbacks or
after backend calls. No shared memory lock is held across translated allocator,
free, or destructor callbacks. Environment strings, pointer arrays, exported
slots and parser/math output pointers are also published through tracking.
`test_provider_memory.py` checks cross-thread same-value writes, ABA, deep
allocation/free/realloc ranges and address reuse, callback-driven state, zlib
outputs and read-only controls. This verifies these providers' participation;
it does not certify every external host write or every game concurrency path.
