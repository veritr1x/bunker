# Original Unity API-loader diagnostic

This NEW variant preserves combined1756d78 and its executable/input directory.
It uses that gate's exact original Unity/IL2CPP objects, validated01066 overlay,
union trace table, frozen1942e24 providers and isolated checked getClass method.
It performs no translation or live-provider/source substitution.

After417 Unity constructors, actual JNI1.6/42 native registrations and initJni,
the real findLibrary helper returns its NativeString. The same guarded40-byte,
tag0x49 object remains alive while original703b7650 consumes it in X0; W0 bit0
is the actual boolean result. The real destructor700e0044 runs once afterward.
IL2CPP is registered but NOT host-opened before that call: actual guest dlopen
owns its nine constructor effects.

Pristine preconditions are READ-only:222 zero API slots starting712bbfd0,
zero handle712bc6c0, zero path-cache pointer712b97c0, and the actual empty
queue7127ef90 including count7127fb90/active7127fb98/dirty7127fba0.
Nothing is cleared or injected. Unknown JNI-cache objects/virtual cleanup at
head7130da68 stop the first profile before the API-loader; only an actually
empty cleanup closure is accepted. Both queue and JNI closure are checked
afterward. RegisterModules, il2cpp_init, GC, managed bodies and the UnityTLS
API setter remain prohibited.

The original ModuleRegistry is installed into a private dispatch table; the
real runtime forwards its four libdl markers through a diagnostic journal.
The provider implementation is unchanged. The journal requires actual
dlopen1(flags2, the helper's exact path), dlsym222 in original order, dlerror444,
nine constructors and refcount1. Every published guest slot must equal the
original ELF export. This executes the original Unity loader, rather than the
earlier host Open/Symbol verification loop.

Cleanup evidence corrected an earlier audit label:70384aa0 initializes an
empty tree; it is NOT a destructor. Factory36c1e4 allocates, calls that
initializer and publishes the pointer without registering an atexit destructor.
The real close helper70384764 takes the cached handle in X0; its return is
ignored. It actually calls dlclose, then70384c94 erases the node, runs the real
NativeString destructor and frees the node. Both roots are in the original
accepted trace/object set.

Original JNI_OnUnload runs first while both modules/providers remain live.
Its nine wrappers use JNI FindClass/UnregisterNatives/FatalError. The final
virtual cleanup list is required empty immediately before and after it.
Real70384764 then must cause exactly two reverse IL2CPP finalizers/refcount0
and an empty tree, followed by the two Unity finalizers and TLS cleanup.
The persistent empty-map allocation and unchanged stale top handle/API slots
are explicit process-lifetime state. No zeroing, reset, reopen, subsequent
API/cache use or map-destructor support is claimed.

Prepare with unity_api_loader_prepare.py --base-build <approved combined workdir>
--out <NEW workdir>; it refuses an existing output directory and verifies the
approved executable/input/source hashes and all required loader/cleanup roots.
Then run unity_api_loader_build.ps1 -BuildDirectory <NEW workdir> -Run and
test_unity_api_loader.ps1 -BuildDirectory <NEW workdir>. The new workdir records
the exact base lineage, immutable object/source hashes, executable, real
pre/post observations, libdl journal results and retained-state boundary.

This is a mixed, unpolled snapshot diagnostic. Passing it establishes actual
loader/empty-queue publication and checked cleanup. It establishes no whole
boot, audio/frame, nonempty startup-hook dispatch, IL2CPP initialization or GC.

The Windows gate passed with executable SHA256
27aebf55092e792f548e714cab17faab193a39bfc38fdfc2e85eb2cfdbfb90ef.
All24 lifecycle/lineage/input checks passed, including wrong-module/APK
rejection before constructors. The final slot snapshot is taken immediately
after the helper and before the loader. Actual JNI_OnUnload7043ab34 returned
while IL2CPP remained live/refcount1. The first passing executable/log/inputs
before that guard-timing strengthening are preserved under first-pass names.
