# Closed Java native-library loading

JavaNativeLoader supplies the original UnityPlayer instance loadLibrary(String)Z
body through its existing checked Boolean binder. It resolves the actual
receiver class loader, requires the configured application loader, and obtains
the path from the existing ClassLoader.findLibrary service. Only the explicit
logical-name/canonical-guest-path catalog is eligible. A path result alone never
means that a native library was loaded.

ModuleRegistry opens the real registered translated image and owns its original
constructors. An optional original JNI_OnLoad executes through the supplied
same-thread guest runner with the real JavaVM and null reserved argument. The
manager caches success/failure per configured path and application loader;
repeated Java loads do not acquire another native reference or replay OnLoad.
Same-thread recursive loads return the in-progress result, while other threads
wait for completion. Registry, JNI, guest-runner and diagnostic calls execute
outside the manager mutex.

Adopt records independently completed startup without opening/replaying it.
ModuleRegistry::IsOpenHandleFor verifies exact live path/handle identity, even
when two images export the same address. A nonzero expected_onload provides an
additional original-entry pin. Version0 is allowed only for a proven absent
optional symbol; otherwise a supported actual completed JNI version is required.
Bootstrap must adopt Unity's already executed OnLoad before binding this method.

Original DEX load errors return false with severity6 diagnostics; normal success
returns true. Unknown modules cannot fall through to Windows LoadLibrary or raw
ARM64 execution. A preexisting Java exception remains pending and causes no
load. The lower operation preserves a fresh OnLoad Throwable and caches failure. The
Unity wrapper catches UnsatisfiedLinkError and Exception with actual type tests,
clears the caught object and logs it; other Errors retain the same pending object.
No failure is disguised as success. Host/translated execution exceptions fail closed.
The owner diagnostic callback supplies this port's actual load-failure sink;
this component does not install a fictitious System or Java bytecode runtime.

The installed handler retains shared immutable service state and JNI loader
identity. Revoke disables later calls, but neither facade destruction nor
failure closes a native image with possible registrations/TLS. ModuleRegistry,
Host and runner dependencies must outlive installed callbacks and active work;
finalization belongs to the external coordinated module owner.

The focused component builds a real NDK ELF with constructors and normal,
bad-version, recursive, concurrent and pending-exception OnLoad entries, plus
an ELF with no OnLoad symbol. Original NDK direct/V/A JNI callers exercise the
bound method. Declared test modules deliberately share function addresses to
prove handle identity is not inferred from an export pointer. Host hooks only
control scheduling; original NDK constructor/OnLoad/JNI bodies execute. Tests
are a bounded host qualification, not ART conformance or an original game run.
