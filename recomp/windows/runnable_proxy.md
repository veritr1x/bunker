# Reached Runnable metadata and singleton proxy

The proxy adapter declares bootstrap `java/lang/Runnable` as an interface with
the sole abstract `run()V` method. It adds a distinct application-loader
`HostRunnableProxy` implementing only Runnable. The three existing singleton
proxy classes retain their own identities and interface graphs. The exact
ordered singleton Class[] is validated using actual Class identity; mixed and
duplicate lists remain unsupported.

Android 13's [Runnable declaration](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/ojluni/src/main/java/java/lang/Runnable.java)
is the metadata source. Android's
[Class.getClassLoader implementation](https://android.googlesource.com/platform/libcore/+/android-13.0.0_r1/ojluni/src/main/java/java/lang/Class.java)
returns the BootClassLoader singleton for this bootstrap interface. The factory
uses the actual JNIBridge application loader, which can see Runnable. Source
bytes and hashes are preserved in `work/runnable-proxy-audit`.

The original DEX factory obtains JNIBridge.class's loader, constructs its handler
with the unchanged long handle, and passes the actual interfaces to
Proxy.newProxyInstance. The handler's synchronized b==0 branch returns null;
for run()V this is a void return. The adapter implements that disabled branch
only. Every active run call remains a named unsupported boundary because the
original native/reflected Method dispatch is not ported. Runnable is abstract;
no default method, UI task, Java Thread, queue, event or native invocation is
manufactured. Object.toString/equals/hashCode remain explicit boundaries.

Original Unity SHA256 `3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f`
contains singleton Runnable constructors at41d7b8 and432ed4, passing actual
count1 Class[] to ab7664 at41d890 and432fac. The first retains the returned proxy
through311af0→ab57c0→JNI21 NewGlobalRef. Its real cleanup41d8c0 removes the native
registry member, calls ab78b8's exact disableInterfaceProxy(Object)V, then
311bdc decrements the wrapper and calls ab589c→JNI22 DeleteGlobalRef on its last
owner. The second constructor uses432fdc→ab5960→JNI226 NewWeakGlobalRef. Mixed
count2 constructors42af54 and436f08 exist and remain outside this singleton
profile. These static facts do not identify the next runtime factory list.
Game9 observed the Runnable FindClass failure, with no actual Runnable Class[]
capture or active run execution. The DEX body extraction and native disassembly
proof are hash-pinned in `work/runnable-proxy-audit/proof.json`.

The proxy payload keeps the actual handler, loader and Class snapshot; it never
keeps the caller's mutable array as its type definition. Its native handle stays
opaque and full64-bit. The recursive handler monitor and passive weak ledger
are shared with the existing profiles. Disable changes only the handle. No
payload/provider destructor calls native delete or a finalizer. After callers
quiesce, CheckNoEnabledProxies must run while real Runtime/modules/providers
remain live; either a live enabled proxy or an unexplained retired enabled
handle stops unload. Host/context outlive the adapter; drain workers first,
destroy the adapter on an attached JNI thread, and preserve original native
disable-before-reference-release order. This is a component adapter, with no
Java GC, reflected Method, native dispatch or finalizer integration claimed.

The new actual NDK fixture tests interface metadata/no constructor, factory and
disable direct/V/A, interface/concrete run MethodIDs direct/V/A, unchanged
unused arguments/canaries, the actual app and bootstrap loaders, all old profile
identities, typed Runnable arrays, Class[] mutation, native global/weak reference
retirement, opaque high handles and an original zero handle. Labelled TEST
native invoke/delete counters must remain zero. Named negative subprocesses
cover active run through all six call/MethodID combinations, three mixed lists,
duplicate Runnable, enabled/retired/expired owners, and disabled Object methods.

The runner archives accepted committed support `3c7309a7df49c19e2333b1f3d6ccc88be3f8e8f3`
plus only the exact proxy h/cpp and new guest/test/runner overlays. Concurrent
Context/core/game edits are excluded. Candidate1 is retained: its test wrongly
expected Java SE's null bootstrap loader. Android primary source confirmed the
existing core was correct; only that test assertion changed in candidate2.
Candidate2 passed238 positive Windows checks, then its WSL-launched negative
process exceeded the30-second runner bound. A native Windows invocation of
the same duplicate-profile executable emitted the expected boundary and
0xC0000409 exit. Candidate3 preserves the same provider/guest/test bytes and
uses native PowerShell full-status capture for Windows negative processes,
with a bounded90-second wait and per-case persisted progress.

Final candidate3 passed on both Windows and Linux:238 focused Runnable checks
and16 named boundaries; unchanged ServiceConnection237+10,
AudioFocus217+6 and LocationListener547+22 checks/boundaries. Each host's
fixture contains45 strict translated heads with zero unsupported instructions
or unresolved direct targets. Windows native status capture confirms50 abort
boundaries at0xC0000409 and four explicit ownership-audit exits1 across the four
tests. The five executable overlays are revalidated against live and frozen
bytes before acceptance; the final six-file held manifest also pins this doc
and primary/static evidence. See `work/runnable-proxy3/acceptance.json` and
`work/runnable-proxy-held.json`. These are component results; an actual next
game run must still capture its own interface list and any active dispatch gap.
