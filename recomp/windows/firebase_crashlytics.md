# Firebase Unity 9.6 Crashlytics desktop bridge

The service forwards nineteen additional exports from the pinned genuine
`FirebaseCppApp-9_6_0.dll`. Existing App markers 0–21 retain their indices.
This closes the original runtime15 frontier at
`SWIGRegisterExceptionCallbacks_CrashlyticsInternal`; qualification does not
claim execution of the original managed callers or a visible game frame.

## Exact stripped ABI

The original ARM64 IL2CPP PInvoke stubs and metadata determine these C types.
`P` means native pointer; strings are UTF8 `const char*`; SWIG `HandleRef`
wrappers pass their underlying pointer. Marker offsets are index × 8.

| Indices | Export suffix after `Firebase_Crashlytics_CSharp_` | Native C signature |
| --- | --- | --- |
| 22 | `SWIGRegisterExceptionCallbacks_CrashlyticsInternal` (no prefix) | `void(E,E,E,E,E,E,E,E,E,E,E)`; E=`void(*)(const char*)` |
| 23 | `SWIGRegisterExceptionArgumentCallbacks_CrashlyticsInternal` (no prefix) | `void(B,B,B)`; B=`void(*)(const char*,const char*)` |
| 24 | `SWIGRegisterStringCallback_CrashlyticsInternal` (no prefix) | `void(const char*(*)(const char*))` |
| 25 | `FirebaseCrashlyticsInternal_GetInstance__SWIG_0` | `P(P,int32_t*)` |
| 26, 28 | `FirebaseCrashlyticsInternal_Log`, `..._SetUserId` | `void(P,const char*)` |
| 27 | `FirebaseCrashlyticsInternal_SetCustomKey` | `void(P,const char*,const char*)` |
| 29 | `FirebaseCrashlyticsInternal_LogException` | `void(P,const char*,const char*,P)` |
| 30, 36 | `new_FirebaseCrashlyticsFrame`, `new_StackFrames__SWIG_0` | `P()` |
| 31, 37 | `delete_FirebaseCrashlyticsFrame`, `delete_StackFrames` | `void(P)` |
| 32–35 | `FirebaseCrashlyticsFrame_library_set`, `..._symbol_set`, `..._fileName_set`, `..._lineNumber_set` | `void(P,const char*)` |
| 38 | `StackFrames_Add` | `void(P,P)` |
| 39 | `StackFrames_size` | `uint32_t(P)` |
| 40 | `StackFrames_getitem` | `P(P,int32_t)` |

Notable original stubs: GetInstance `0x8538dde0`, Log `0x8538de70`,
SetCustomKey `0x8538df14`, SetUserId `0x8538dfd4`, LogException `0x8538e078`.
The lineNumber setter at `0x8538dc48` calls the original UTF8 marshaler
`0x825c7194`: lineNumber is a string, including formats such as `123:45`.
The managed vector item wrapper at `0x85391678` sets ownership false at
`0x85391704`; borrowed items must not call native delete.

## Ownership and callbacks

AppUtil and Crashlytics have independent 11 exception, 3 argument, and
allocating string callback slots and independent native C thunks. Existing
synchronous owner-thread admission and deferred callback failure remain in
force. Exceptions never unwind through the foreign MSVC DLL. No callback
failure is silently converted to success.

GetInstance receives the actual live App pointer. The native SDK writes an
owned host `int32_t`; the bridge publishes its real value with tracked guest
memory writes. It does not pass an untracked guest output pointer to the DLL.
The returned pointer is usable only while that App has at least one actual
service-owned native reference. Last release revokes associated bridge
handles. This is a current pointer/refcount profile, with no universal ABA
protection if the SDK later reuses an address.

The genuine SDK `GetInstance` allocates a Crashlytics object on every call.
Original SWIG Dispose explicitly has a native-delete TODO and zeros only the
managed handle. The bridge matches that contract: parent release logically
revokes the handle; native Crashlytics allocations remain until process exit.
It does not invent a native destructor or claim to free those allocations.

Frame/vector allocations use the genuine new/delete exports. Frame setters
forward typed string snapshots to the SDK; qualification verifies the SDK's
retained copied values after the temporary input lifetime ends. Vector item
views are borrowed and are conservatively revoked on every vector Add and
delete. Borrowed frames cannot be deleted. Revoke requires all App references
and owned Frame/vector objects released. This does not promise universal
stability of vector addresses across mutations.

## Official desktop behavior and fixture scope

Firebase Unity source tag v9.6.0, commit
`c851452bd928d98c4730efb3e3cb4e1889ddaeb9`, selects
`crashlytics/src/cpp/stub/crashlytics_stub.cc` on Windows. Its Log,
SetCustomKey, SetUserId and LogException bodies are empty. The common wrapper
still genuinely initializes and returns an object and status. The pinned
DLL independently matches this behavior: the three simple event exports
alias RVA `0x8df60`, then `0xfdc30`, then the return-only stub `0x7d940`;
the exception path reaches the vector-discard stub at `0xfddd0`.

Source URLs, hashes and bounded instruction records are captured in
`work/crashlytics-typed-preparation1`. The test forwards local fixture calls
through these genuine desktop stubs. It changes no collection preference and
collects/uploads no synthetic events. It does not claim desktop Crashlytics
is a functioning crash reporting backend, and does not fabricate any native
instance, dependency result, collection status, or Available flag.

The configuration is exactly the original APK member
`assets/google-services-desktop.json`, 3632 bytes, SHA256
`d8acf3a75a2839815783e185bcd51523febc4560ebe988b1ec529e9e4880ea9b`.
No configuration contents or credentials are printed or modified.

## Qualification

Run `test_firebase_crashlytics.py --out <new-folder>` under the established
WSL Python environment. It snapshots the actual source closure, pins the
genuine DLL and APK, compiles ARM64 NDK callers, translates them, builds the
Windows service and executes the resulting Windows fixture.

The caller exercises all nineteen imports by direct call and volatile
function pointer, including eleven-callback AArch64 stack arguments, separate
App/Crash routing, tracked GetInstance outputs and neighbor guards, real SDK
out-of-range callbacks, parent references, owned allocations, and borrowed
view rejection. State1200, Memory64 token/bytes, saved high registers and the
native errno/LastError/floating-point environment are checked.

To exercise Crashlytics' allocating string callback without expanding the
production cohort, a transparent test-only observer invokes the genuine SDK
Frame getters while a selected size import is active. Those actual getters
call the registered translated ARM64 allocating string callback; the ARM64
caller frees the exact returned allocation. Explicit callback-slot replays
verify routing only and are distinguished from the genuine SDK out-of-range
error. Separate processes verify foreign callback rejection.

An independent executable links the new service to the unchanged old App
lifetime C++ fixture and its frozen ARM64 guest and translated objects. Its
positive configuration, missing configuration, original 18-export behavior,
and foreign callback modes must pass. The native Windows dependency value
remains the genuine SDK result (7 in this qualification), while the original
managed create/dispose dependency path can return Available naturally.

Q1 preserves a fixture-only `-Wmisleading-indentation` compile failure. Q2
passed the complete fixture and old App regression. Q3 strengthens the
Frame/vector-only revoke check after every App reference is released and
records the real out-of-range callback slot; it changes no production byte.
The final source packet names the accepted immutable gate and all source
hashes. These focused fixtures do not establish original game startup,
asynchronous callbacks, all SDK overloads or a rendered scene.
