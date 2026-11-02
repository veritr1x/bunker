# First supported JNIBridge proxy factory and disable

JniInterfaceProxy binds the actual APK's existing newInterfaceProxy and
disableInterfaceProxy declarations. It supports the first ordered singleton
ServiceConnection[] profile. Factory logging records the real full64-bit handle,
actual JNIBridge application loader and all actual class names before profile
validation. Framework ServiceConnection remains bootstrap-visible; visibility
does not require equal interface/factory loaders. No service or native callback
runs during factory/disable.

The real generated proxy extends reflect.Proxy (Serializable) and implements
ServiceConnection. It owns the original handler, loader and ordered class
snapshot through real object edges; caller-array mutation cannot change its
type. The handler has a recursive monitor and opaque handle. Disable sets only
that handle to zero, idempotently. Only disabled service void callbacks implement
the original b==0 return. Active service callbacks, Object.toString/equals and
the declared hashCode override remain explicit boundaries. No native Method,
invoke/delete callback, MethodHandles constructor/c state, default method,
Java GC/finalizer or Android service success is invented.

The passive ledger contains weak JNI proxy references plus numeric/monitor state,
never a strong proxy object. CheckNoEnabledProxies must run before unload while
Runtime/modules/providers remain live; it rejects either a live enabled proxy or
an unexplained retired enabled handle. Invoke this snapshot audit only after all
factory/callback callers have quiesced; it is not an atomic close fence. The original native owner holds the real
GlobalRef and performs disable before releasing it. Factory-local, payload,
adapter and Host destruction run no native delete/finalizer. Host must outlive
the adapter, and the adapter must outlive worker drain. Adapter destruction must
occur on an already attached JNI thread because it deletes weak references via
Env227; it never autoattaches. Concurrent destruction
is outside the owner contract. Shared state locks never cover Host/Env operations
or Java payload retirement; per-handler locks cover only numeric reads/writes.

The strict NDK fixture registers labelled TEST native handlers at their actual
translated entries and verifies they are never called by this port. Tests cover
factory/disable direct,V,A forms, high64-bit handles, exact interface/class/loader
identity, array covariance/snapshot, native GlobalRef ownership, weak retirement,
disabled callbacks, concurrency, explicit unresolved enabled lifetime, and wrong
profile/active invocation failures. Fixture handlers are not original game
addresses and never enter production registration. The runner freezes an
accepted committed JNI/context support tree plus only these new files.

Executed candidate2 passed237 focused checks and ten expected fatal subprocess
boundaries on each platform, plus all seven existing regressions. A C++17 lambda
capture spelling correction was then frozen in candidate3; its focused gates
again passed237 on both hosts with the same43-trace fixture and no unsupported
or unresolved entries. No shared JNI/context/game source was changed. These
component gates do not establish original native invocation, finalization or a
new game frame; the next frame needs the separately accepted proxy/core wiring.
