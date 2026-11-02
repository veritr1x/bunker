# Reached Java initialization support

Native8 reached three concrete Java requirements during normal nativeRender
initialization: Context.getContentResolver, android.content.ServiceConnection,
and UnityPlayer.initializeGoogleAr. The evidence uses original APK SHA256
`9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209`
and original Unity SHA256
`3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f`.

## Resolver identity and ownership

Android13 ContextImpl.getContentResolver returns its context-owned resolver.
The host now creates one typed ContextImpl$ApplicationContentResolver per
configured Context, derives it from ContentResolver, and returns fresh JNI local
references to the same object. Its state retains the configured application
package without a shared-pointer cycle back into the Context object.

The actual native getter wrapper at original `abab40` caches the getContentResolver
method ID, invokes it, and puts a real NewGlobalRef in its reference-counted
holder. Its static consumers include `417980`, `417b24`, and `41a5f4`; the last
stores the lazy resolver holder and registers original cleanup callback `419c78`.
These are original instruction windows, not invented FDE extents. The supported
result is identity and ownership. ContentProvider queries, Android ID/settings
values, observers, and service binding results are not manufactured; subsequent
unsupported APIs remain explicit requirements.

The lifetime gate removes all Activity/player/static/local edges and destroys
the Context wrapper while retaining only a native JNI GlobalRef to the resolver.
The resolver stays alive; deleting that last GlobalRef clears its weak reference.
An attached native thread observes the same real object identity.

## ServiceConnection metadata

ServiceConnection is a genuine interface, with all four Android13 callbacks:
onServiceConnected(ComponentName,IBinder), onServiceDisconnected(ComponentName),
onBindingDied(ComponentName), and onNullBinding(ComponentName). No implementing
class or live Android service is invented. The interface has a null JNI
GetSuperclass result, Class.isInterface is true, and the supported assignability
graph allows an interface reference to Object but not the reverse.

Host::DefineInterface preserves existing DefineClass behavior by default.
Interface AllocObject, NewObject forms, NewInstance, and NewHostInstance cannot
manufacture an instance. Abstract callbacks have no fabricated body. The two
platform default methods have empty original source bodies, but this change
only supplies their metadata; it does not invent a callback receiver or invoke
them. Other interface/class catalogs are unchanged.

## Exact disabled AR branch

The actual DEX UnityPlayer.initializeGoogleAr code_item `553ef8` always returns
false at `553f56/553f58`. Before returning it may create GoogleARCoreApi and call
its native initialize/resume methods, only when m_ARCoreApi is null,
currentActivity is non-null, and getTangoEnabled returns true. GoogleARCoreApi's
constructor at `54f5dc` only invokes Object.<init>; its initialize/pause/resume
methods are native declarations, not empty Java implementations.

getTangoEnabled code_item `553eb8` uses mContext.getPackageManager(), the actual
package name, getApplicationInfo(package,128), inherited ApplicationInfo.metaData,
and Bundle.getBoolean("unity.tango-enable"). It catches java.lang.Exception and
returns false. A fresh AAPT parse of the exact APK reproduces all 16 complete
application metadata entries and proves this key is absent.

Call `context.BindUnityPlayer(player)` once after creating and validating the
typed player/Activity, before native initJni(Context). This ports only the proven
initial mContext/currentActivity/m_ARCoreApi binding facts from the original
constructor. It sets currentActivity to the actual configured Activity, evaluates
the live PM/Bundle lookup, and returns the actual disabled-path result. It does
not exploit unset constructor fields, run or mark the whole Java constructor or
class initializer, create an AR object, or skip a native call from an enabled
path. Enabled AR stops decisively at its still-unimplemented original native
side effects. Rebinding cannot reset a player's existing context/AR state.

Host::BindBooleanMethod attaches this body to the existing nonnative APK method
declaration. It cannot replace a native method or an existing implementation;
the existing DefineBooleanMethod duplicate-declaration rejection remains.
Method handlers reference the Host, not the AndroidContext C++ wrapper. Host
must outlive the wrapper and its Java/native callbacks. Java fields and JNI
references retain their normal object ownership.

The existing unity_bootstrap.cpp now makes that one integration call before
original initJni. It is separately compile-checked against the accepted generated
Unity headers. The new dual-engine harness uses the same API. No new frame run
is implied by this wiring or by these focused gates.

## Validation

Frozen support source is committed `1600a28`, with only the four JNI/Context
provider files and the new fixture/test overlaid. Actual NDK API24 callers test
interface hierarchy/type/lookup and AllocObject rejection, resolver identity and
lifetime, and the AR method. Missing/false/nonboolean metadata and actual APK
metadata profiles follow the disabled branch. A separate expected-fatal native
process proves enabled AR cannot silently return false.

Windows and Linux each pass:

- Java initialization: 141 checks, 80 completed NDK fixture calls across four
  profiles; enabled AR separately reaches the explicit failure boundary.
- Existing JNI host: 36 checks; Android Context: 14; PackageManager: 155.
- Existing callback-frame ownership: 464 checks; constructor frames: 362.

The union fixture has 28 strict translated roots, no unsupported traces, and no
unresolved direct targets. NewObject interface rejection is additionally checked
as a host boundary; no Android-device behavior for invalid constructor IDs is
claimed. The core liveness and constructor/callback regressions retain actual
NDK direct, V, A, and stack-spill callers.

Evidence stays ignored: `work/java-native8-audit/` contains original DEX/native
windows and fresh manifest absence proof; `work/java-init-candidate4/acceptance.json`
contains source/fixture/toolchain/binary hashes and all test results. Earlier
candidates are preserved. The separate bootstrap syntax check records its own
wiring source/object/generated-header hashes. No completed frame or playable
game is claimed.

Primary Android13 contracts:
[ContextImpl](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/app/ContextImpl.java),
[ContentResolver](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/content/ContentResolver.java),
[ServiceConnection](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-13.0.0_r1/core/java/android/content/ServiceConnection.java).
