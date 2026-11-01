# Isolated Java native-library path catalog

JavaNativeLibraries installs only ClassLoader.findLibrary(String)String using
Host::DefineObjectMethod. It returns configured absolute guest paths for the
actual configured application-loader identity. It does not open a library,
resolve exports, touch the host filesystem or call LoadLibrary on ARM64 bytes.
The caller must mount/register the corresponding real translated modules.
No central JNI/context/bootstrap/module/runtime wiring is included.

Config includes the application loader reference, a real application jclass,
and explicit logical-name/absolute-guest-path entries. Construction requires
an attached thread with no pending Java exception. The class's builtin
getClassLoader must match the supplied loader and differ from the bootstrap
String class's loader. Newly made ClassLoader instances, bootstrap loaders and
invalid/stale class references cannot manufacture that binding. Constructor
identity checks never clear or replace a preexisting exception.

Logical names and paths preserve UTF16, including valid surrogate pairs. Config
rejects null code units, unpaired surrogates, path syntax in names, duplicate
names, nonabsolute paths, empty/dot/traversal segments, Windows separators/drive
syntax and APK zip-path syntax. Each basename must equal lib+logical-name+.so.
This is an explicit resolved-path catalog, with no automatic search, filesystem
existence claim, APK-member extraction or fallback to another native runtime.

For the application loader, unavailable names return null without an exception;
a null/cleared-weak name raises NullPointerException. Base, bootstrap and other
loader identities preserve default null behavior, including null arguments.
JNI validates receiver/argument types, reference ownership and JNIEnv thread
identity before this handler. Normal Java virtual dispatch remains in Host;
this component does not replace another class's override or an existing base
findLibrary handler.

The primary Android13 rules are:

- [ClassLoader](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/ojluni/src/main/java/java/lang/ClassLoader.java):
  the base findLibrary implementation returns null.
- [BaseDexClassLoader](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/BaseDexClassLoader.java)
  delegates to DexPathList.
- [DexPathList](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/dalvik/src/main/java/dalvik/system/DexPathList.java)
  maps the logical library name and returns a found path or null.
- [System](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/ojluni/src/main/java/java/lang/System.java)
  specifies NullPointerException for null mapLibraryName input.

Exact fetched source files/hashes are preserved under ignored
work/unity-il2cpp-load-audit/primary. The catalog models this checked application
profile using the existing Host loader identity; it is not an Android class
loader implementation.

The loader is retained as Host::ObjectValue, not a creator-thread local handle.
Each lookup makes and deletes a temporary caller-local identity reference.
One immutable global String per configured path is owned for the installed
Host method's lifetime; Host clones it into the invoking thread's local result.
Deleting results, creator locals/globals or detaching the creator therefore
cannot invalidate the catalog.

Revoke and the facade destructor atomically disable the service. The installed
handler owns immutable shared state and never captures a raw facade pointer.
Revoke performs no JNI operation and does not delete a global which an
in-flight callback is about to return. Such a call may finish with its valid
path; subsequent calls return null. Retained path globals are bounded by the
configuration and released when Host tears down, rather than on revocation.
There is one installation per Host; duplicate method installation is rejected.
Failed installation rolls back its new globals. Host and its active calls must
have their normal externally coordinated lifetime.

test_java_native_libraries.py builds real NDK direct/V/A callers plus a V caller
whose argument is on the AAPCS64 stack. Native Linux and Windows gates cover
configured/Unicode paths, unknown names versus explicit revocation, base/other
loaders, null/type/stale/weak references, local-frame promotion, exact pending
exception identity, creator detach/global deletion, worker-local results and
512 concurrent lookups across revocation. Wrong/detached JNIEnv subprocesses
stop through the existing JNI host diagnostic guard. The fixture uses three
fully supported traces and no native library loading. Both native hosts pass
196 checks plus the 512 concurrent calls and two decisive JNIEnv failure gates.
Ignored
work/java-native-libraries-{linux,windows}/result.json records exact tested
component/shared-source and executable hashes.
