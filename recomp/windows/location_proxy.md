# Reached LocationListener metadata and exact singleton proxy

Actual game7a completed the original ServiceConnection and audio-focus factories and logged each supplied singleton Class[]. Its next original FindClass6 at LR70ab5478 raised NoClassDefFoundError for `android/location/LocationListener`. That listener's own factory Class[] remains uncaptured until a later natural frame. The following sigaltstack terminal boundary is separately owned.

[Android13 LocationListener implementation](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/location/java/android/location/LocationListener.java) has six methods:

| Signature | Android13 body |
| --- | --- |
| onLocationChanged(Location)V | Abstract |
| onLocationChanged(List)V | Default loop invoking the single-Location overload |
| onFlushComplete(I)V | Empty default |
| onStatusChanged(String,I,Bundle)V | Empty default |
| onProviderEnabled(String)V | Empty default |
| onProviderDisabled(String)V | Empty default |

Exact source SHA256: `26fe7c86cb205bb5bda94f3d1051528a8e951df2a84e49600a759d0beac54793`. The downloaded source/URL evidence is in `work/location-proxy-audit`. The [actual Location class](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/location/java/android/location/Location.java) has Object as its superclass and implements Parcelable. This scoped catalog adds only its required class identity/Object superclass for argument checking; it supplies no Location constructor, coordinate accessors, provider state or Parcelable operations. Existing List/Bundle/String metadata is retained without broader framework rewrites.

Original Unity4301c4 calls430260, loads the real listener wrapper through123d420 at4302c0, and invokes the original generic JNIBridge factory at430338 with one interface and unchanged native ownerx19. It retains the real returned proxy GlobalRef wrapper at+0x10 and registers its owner. Vtables120b3f8/120b488 lead to42f1b0/42f200 destruction of extra references followed by42f7a4 registry removal, actual proxy disable and wrapper release. The constructor next obtains LOCATION_SERVICE throughab9f18/getSystemService; no service object, permission or location value is fabricated here.

The proxy adapter adds a distinct application-loader HostLocationListenerProxy implementing only LocationListener. Old ServiceConnection and audio-focus classes preserve their exclusive type graphs. Factory handling keeps actual Class identity, exact ordered singleton snapshot, raw64 handle, JNIBridge app-loader provenance, recursive numeric guard and passive weak lifetime ledger. Mixed/duplicate/unknown profiles remain unsupported.

The exact APK JNIBridge handler attempts native/reflected-Method invocation first for every active callback. Platform defaults are only reachable through its later NoSuchMethodError/reflection fallback, so an empty Android default cannot shortcut that native call. All six active callbacks therefore remain explicit unsupported boundaries. Disabled handlers return only through the original zero-long void branch, including nullable JNI arguments; no List loop, coordinates, provider events, requestLocationUpdates, getLastKnownLocation, permissions, Java GC or native finalizer are supplied.

## Validation

The new Android NDK fixture checks genuine interface identity, null superclass, all six exact descriptors, noninstantiation and Location superclass metadata. It calls factory, disable and all six callback signatures through direct,V,A entries, including overloads and the mixed three-slot status call. Tests verify argument/jvalue canaries, null references, wrong Location argument rejection, absent Location constructor/coordinate methods, exclusive profile Class/array identity, immutable interface snapshots and genuine native GlobalRef/weak retirement. Labelled TEST native invoke/delete counters remain zero.

Twenty-two new subprocess boundaries require active failures for every signature and JNI form, mixed Service/Audio lists, duplicate Location list and enabled-unload ownership. Existing unchanged Audio217/six-negative, Service237/ten-negative, Context14 and Java141 gates run on both Windows and Linux. The runner freezes committed714daef support plus only the owned Context/proxy/fixture/test overlays. No live JNI core, FS, SignalHost or harness change is captured. Candidate directories and logs are preserved; acceptance hashes the exact executed source, fixture, translator semantics and binaries. Component tests do not claim a rendered game frame or an actual runtime Location Class[] capture.

Candidate1 passed on Windows and Linux: Location547, unchanged Audio217 and Service237, Context14 and Java141 checks per host. All22 Location, six Audio and ten Service expected fatal subprocesses passed per host. The49-trace NDK union has zero unsupported traces and unresolved direct targets. Frozen support commit `714daeff64880209eb9de33b99a7164ea237557d`. Acceptance `work/location-proxy1/acceptance.json` SHA256 `2e1ffd36e389d5d995f2401560846c8810737de6d2ed1642d91d4ace64f4964a`; fixture SHA256 `229e7b8f5ec84bf3022f7d2a1e0a1f46eb962c98838de57500d78fbc22e2231d`. The same original process/run was preserved across the agent turn interruption; no duplicate candidate was started or frozen source changed.
