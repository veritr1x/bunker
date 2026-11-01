# Native Windows host gates

These adapters support the ARM64-to-x86_64 recompilation path. They do not yet
boot the real Unity player, initialize its graphics/audio host, or run the game.
Unsupported JNI methods and unavailable translated modules fail explicitly.

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
guest `setenv`/`unsetenv`, never the host process environment. Locale objects,
wide strings, long double, sockets and signals remain separate unresolved work.
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
