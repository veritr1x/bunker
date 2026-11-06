# Genuine Firebase default App lifetime

The Windows SDK service appends four exports after its existing eighteen
markers. Their original stripped IL2CPP P/Invoke stubs establish the native ABI:

| Export suffix after `Firebase_App_CSharp_` | Native signature | Original stub |
| --- | --- | --- |
| `FirebaseApp_AppSetDefaultConfigPath` | `void(const char*)` | `853751b4..85375244` |
| `FirebaseApp_CreateInternal__SWIG_0` | `void*()` | `85374f94..85375008` |
| `FirebaseApp_NameInternal_get` | `const char*(void*)` | `85374efc..85374f94` |
| `FirebaseApp_ReleaseReferenceInternal` | `void(void*)` | `85375008..85375088` |

Name and release extract the native pointer from the original HandleRef before
the native call. The name stub converts the returned C string and frees that
exact allocation. The service retains the existing original string-callback
ownership path. Every nonnull native create result adds one owned reference;
only live owned handles reach name/release. The last release revokes that
handle. Revoke rejects live Apps before clearing native callbacks. Bookkeeping
capacity is reserved before native creation. App calls reject callback reentry,
and the existing foreign/asynchronous callback guard remains unchanged.
This is the SDK's current raw-pointer/refcount identity profile, not an
unforgeable capability. It does not prevent ABA if the native SDK later reuses
the same address for another App. Callers must retain/release their real native
references; no universal stale-handle protection is claimed.

`PlatformInformation.get_DefaultConfigLocation` at `853b012c` dispatches its
cached main-thread delegate. That delegate's exact body at `853b0478` calls
`UnityEngine.Application.get_streamingAssetsPath` (`84910918`), without appending
a filename. `Config.resolve_config_path` optionally maps an exact qualified
virtual asset directory to its owned native directory. With no resolver, the
original path is forwarded unchanged. The resolver changes paths, never the
packaged configuration values. Bounded diagnostics print path lengths and the
native create result, not configuration contents.

The qualified APK already contains `assets/google-services-desktop.json`.
The fixture extracts its exact 3,632 bytes (SHA256
`d8acf3a75a2839815783e185bcd51523febc4560ebe988b1ec529e9e4880ea9b`)
and passes the extraction directory to the genuine pinned Firebase 9.6.0 DLL.
No project, application identifier, API key, JSON field or dependency status is
invented or rewritten.

`work/firebase-app-lifetime-qualification2/acceptance.json` (SHA256
`6e9f4f107d9c4c2fba6412fa7dc0dff9dde6c41103bdffebb0b816f052498e4a`)
passes 1,102 positive-profile checks and fifteen actual NDK entries. These
include actual SDK file hashing, two genuine native App references, three name
calls, two releases, and four translated allocating string callbacks/frees.
The remaining reference's name is queried after the first release. Both direct
and volatile function-pointer callers execute. One path remains unchanged;
the other is mapped from the exact virtual streaming-assets folder. Forged and
last-released handles, live-App revoke and callback-reentrant mutation reject
before native use.

A separate missing-directory process passes 1,064 checks and nine NDK entries;
the real DLL returns null and reports its actual missing-configuration errors.
The unchanged older callback/ABI fixture is compiled with the new service and
passes 1,055 checks, 58 NDK calls and 43 installed imports. The native dependency
result stays `7`. Its existing fifteen test callback replays remain explicitly
synthetic routing checks. The foreign-callback child also passes. Q1 is retained
as a fixture-only `-Wmisleading-indentation` compile failure, preceding any SDK
test execution.

In runtime14, the missing config-path export and its ANSI fallback resolve to
zero at log lines 22964/22967. Recorded exception landings then include
CreateAndTrack, CheckDependenciesInternal and TranslateDllNotFoundException.
The later landing `8382b1dc` belongs to the exact generic FDE
`8382b144..8382b278`, not the nearest preceding nongeneric method. Static
registration maps generic pointer index 27161 to generic table row 70656,
method specification 57148, metadata method 41034:
`Firebase.Dispatcher.<>c__DisplayClass5_0<bool>.<RunAsync>b__0`. It is the
dispatcher task's exception-completion handler. Existing diagnostic bytes do
not capture the managed exception payload's type/message, so their exact text
and this failure's direct responsibility for the black image are not claimed.

Original `CheckDependenciesInternal` returns zero through its ordinary success
path after a successful default App creation/disposal. The native Windows
`CheckAndroidDependencies` result is only used by its exception fallback and
is forwarded unchanged. This implementation does not force Available.

AppOptions overloads, Futures, dependency repair and asynchronous guest callbacks
remain outside this cohort. Fixtures use translated test callbacks, not the
original game's managed reverse-P/Invoke handlers. No original game run or
visible frame is established by this component qualification.
