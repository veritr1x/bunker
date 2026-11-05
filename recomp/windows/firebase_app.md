# Firebase Unity 9.6.0 Windows SDK

`prepare_firebase_sdk.py` prepares the official Windows x86_64 Firebase App DLL and its package license using only Python's standard library. Supply the already downloaded archive; the script performs no network requests or installation. The package is listed in the [official Unity SDK archive](https://developers.google.com/unity/archive), with the exact [Firebase App 9.6.0 download](https://dl.google.com/games/registry/unity/com.google.firebase.app/com.google.firebase.app-9.6.0.tgz).

From the repository root, choose a new output directory:

```powershell
python recomp/windows/prepare_firebase_sdk.py --archive recomp/work/firebase-windows-sdk1/com.google.firebase.app-9.6.0.tgz --out recomp/work/firebase-sdk-prepared1
```

The script requires archive SHA-256 `0e356342d3fccabc032ba2578c0874e4e03a82b18f02ea83d1f2c0d8efde88b5`. It reads only these exact regular-file members into fixed output filenames, validates sizes and hashes before creating output, rejects duplicate selected members and existing output directories, and never unpacks archive paths or links:

| Archive member | Output | SHA-256 |
| --- | --- | --- |
| `package/Firebase/Plugins/x86_64/FirebaseCppApp-9_6_0.dll` | `FirebaseCppApp-9_6_0.dll` (10,628,608 bytes) | `f85bb9f82d79176d3d5da322780d437c023191370e608c45723ad6d83c4d1a12` |
| `package/LICENSE.md` | `LICENSE.md` (11,560 bytes, unchanged) | `3ddf9be5c28fe27dad143a5dc76eea25222ad1dd68934a047064e56ed2fa40c5` |

`preparation.json` records the local archive, source URL and prepared file identities. Preparation does not load the DLL or modify Windows certificate stores or SDK configuration. Keep the license alongside the DLL.

The runtime adapter uses the real Windows SDK as its native provider; it does not represent an Android ELF or claim Android `JNI_OnLoad` execution. Guest callback dispatch must use the original translated reverse P/Invoke entries. SDK extraction alone establishes neither adapter qualification nor successful game initialization or a visible frame; those require the separate component and original-game evidence.

## Typed adapter and runtime selection

`FirebaseAppService` in `firebase_app.h/.cpp` exposes 18 typed exports from the exact DLL above. Its `Module::Kind::TypedService` has explicit Firebase library aliases, no Android address image, no ELF constructors and no `JNI_OnLoad`. The closed export set covers the three SWIG callback registrations, logging and callback-enable controls, polling, dependency checking, Play Services initialization, library-version registration and the default app-name getter. It does not expose the rest of the SDK by forwarding arbitrary addresses.

The caller supplies an absolute DLL path, verifies its SHA-256 before loading, and verifies the actual loaded module path against the same hash. Runtime selection is optional and restricted to the explicit muted first-frame collector profile. Append these two arguments to its existing 11-element native argument vector, giving 13 elements including the executable:

```text
--firebase-app-dll C:\absolute\path\FirebaseCppApp-9_6_0.dll
```

The full argument shape is:

```text
bunker-game-bootstrap.exe <native-dir> <qualified-game.apk> <fresh-storage-dir> --frame-gate <width> <height> <ANGLE-dir> --mute-audio --collector-delivery --first-frame --firebase-app-dll <absolute-DLL-path>
```

Without that option the service is absent. This option grants no unverified DLL fallback, Android SDK emulation or general game profile.

## Callback and ownership boundary

The SDK stores real retained C++ trampolines for eleven exception delegates, three argument-exception delegates, the string delegate and the log delegate. Guest callback addresses are validated translated entries and executed through the supplied runner on an admitted guest thread. They are never cast to native function pointers. Input C strings are copied into temporary guest-visible buffers through the shared-memory protocol.

Only synchronous callbacks inside the current SDK-call owner's import are admitted. Different guest threads may enter sequentially; overlapping imports from another thread fail explicitly. Same-thread callback/import reentry is allowed except during exclusive callback registration. Brief state locks reserve these operations, and no adapter mutex remains locked across the DLL call or translated runner. Native errno, last-error and floating-point environment are preserved; the native environment is suspended while the guest callback runs.

Trampolines are `noexcept`: a callback failure is captured, returns only the signature's null/void fallback, and is reported after the native call returns by `Invoke` or `CheckHealthy`. MinGW exceptions do not unwind through the MSVC DLL. A callback from an unowned or foreign native thread fails this boundary. The bootstrap checks health after rendering as well.

The original string reverse-P/Invoke thunk allocates the returned C string through the guest allocator. The native Windows default-name getter tail-calls that callback without replacing or freeing its result. The adapter passes the resulting allocation unchanged to the original IL2CPP P/Invoke caller, which copies it into managed storage and frees it through the guest allocator. It never substitutes a temporary input buffer or a managed object address.

The service admits one generation per process. `Revoke` requires import/callback quiescence and unregisters the native callback slots; the verified DLL remains loaded until process exit. A revoked service cannot be replaced with a new generation that might receive an old cached trampoline. This finite profile does not admit App creation, Future creation, outstanding asynchronous SDK work, credentials, messaging delivery or a token result.

## Evidence and limits

Candidate 5's source freeze and strict MinGW `-Wall -Wextra -Werror` syntax receipt is `recomp/work/firebase-startup-java-audit1/source-manifest5.json`. The focused actual-NDK/native-SDK component fixture is `firebase_app_guest.c`, `firebase_app_test.cpp` and `test_firebase_app.py`.

The completed component gate is `recomp/work/firebase-app-qualification10/acceptance.json` (SHA-256 `2c65229aabfd85ae4fcf459e52a6bbcfbd7c721599294f472f296e54c2e040be`). It records **1,051 checks, 58 actual NDK calls, 43 installed service imports and 18 translated TEST callbacks**, using the exact official Windows DLL and candidate-5 source bytes. Three genuine SDK default-name calls cause three translated allocating string callbacks; all three resulting C allocations are consumed and freed by the translated caller.

The other **15 callback invocations are deliberately artificial routing replays**: the fixture transparently observes and forwards the SDK's registered native pointers, then explicitly calls all eleven exception pointers, three argument-exception pointers and the log pointer during a genuine default-name callback. This proves typed routing, including the eleven-argument AArch64 registration, without claiming the SDK generated those exceptions or logs.

The gate compares the real native dependency result **7** unchanged, validates logging and callback-enable state against the DLL, checks complete installed-import errno/last-error/floating-point preservation, and exercises same-owner reentry, rejected overlapping imports/registration, real callback-slot unregistration and revoked imports. A separate process invokes an observed callback outside a guest-owned SDK call: no translated callback runs, the `noexcept` trampoline records failure, and health checking plus later imports reject that pending failure. No MinGW exception crosses the MSVC callback boundary. This component gate executes translated TEST callbacks, not the game's original managed reverse-P/Invoke bodies.

The read-only original allocation/free proof is `recomp/work/firebase-string-ownership1/acceptance.json` (SHA-256 `dc3920a2243d6b910d120693d69e293f95150751ad4c9cc57333d4bd02d538c1`). The selected-header audit confirms all 17 original Firebase.App reverse-P/Invoke entries are already selected, including the string and log thunks. These static proofs do not claim original callback execution.

The real Windows SDK's `CheckAndroidDependencies` export returns integer **7**; the adapter preserves that result. It does not manufacture an available dependency status. The original Android managed startup can require further App/Future operations depending on its platform and exception paths; those operations remain outside this closed adapter until separately supported and qualified. Neither SDK extraction nor this finite adapter establishes successful Firebase initialization, a notification token, completed game startup or a visible frame.


