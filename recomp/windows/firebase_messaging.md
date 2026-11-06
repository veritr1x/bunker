# Firebase Unity 9.6 Messaging desktop bridge

Runtime16 reaches all three genuine Crashlytics registrations, nonnull native
GetInstance, SetCustomKey and Log. It then fails the original lookup of
`SWIGRegisterExceptionCallbacks_FirebaseMessaging` and its ANSI fallback.
This bridge adds the seven exports that remain in the original stripped
Messaging assembly. Existing App/Crash indices 0–40 retain their positions.
No Future, token request, subscription or notification-send API survives in
that PInvoke closure, so none is added speculatively.

| Index | Genuine native export | C ABI |
| --- | --- | --- |
| 41 | `SWIGRegisterExceptionCallbacks_FirebaseMessaging` | `void(E,E,E,E,E,E,E,E,E,E,E)` |
| 42 | `SWIGRegisterExceptionArgumentCallbacks_FirebaseMessaging` | `void(B,B,B)` |
| 43 | `SWIGRegisterStringCallback_FirebaseMessaging` | `void(S)` |
| 44 | `Firebase_Messaging_CSharp_SetListenerCallbacks` | `void(int32_t(*)(void*),void(*)(const char*))` |
| 45 | `Firebase_Messaging_CSharp_SetListenerCallbacksEnabled` | `void(uint32_t,uint32_t)` |
| 46 | `Firebase_Messaging_CSharp_SendPendingEvents` | `void()` |
| 47 | `Firebase_Messaging_CSharp_delete_FirebaseMessage` | `void(void*)` |

`E` is `void(*)(const char*)`; `B` is `void(*)(const char*,const char*)`;
`S` returns the original translated callback's allocating UTF8 string pointer.
Original metadata independently proves the message callback returns signed
int32, while its argument is IntPtr; the token callback receives a string and
returns void. The original SetListenerCallbacksEnabled stub at `0x853c9778`
normalizes its managed bool arguments before the native call. Native SWIG
accepts bool32 and treats a nonzero value as true.

The original FirebaseMessaging class initializer `0x853c91cc` creates its
Listener. Listener's constructor `0x853c9a04` retains DefaultInstance and
registers two callbacks through `0x853c9600` / PInvoke `0x853c96d4`. The
PInvoke initializer `0x853ca644` initializes its separate exception/string
helpers; the exception helper initializer `0x853cb560` registers eleven
exceptions followed by three argument exceptions. The managed method name
`SWIGRegisterExceptionCallbacksArgument_FirebaseMessaging` resolves the
native spelling in row42 above.

## Genuine desktop behavior

The exact Unity v9.6.0 source commit
`c851452bd928d98c4730efb3e3cb4e1889ddaeb9` selects C++ SDK v9.6.0.
The C++ desktop build selects `messaging/src/stub/messaging.cc`; its fake
message thread is disabled, and NotifyListenerSet has an empty body. The
Unity wrapper maintains a real local Listener and queues; its polling API
does not manufacture messages or tokens.

The pinned DLL independently matches the local listener path. Native export
RVA `0xb23d0` installs/clears a real Listener through `0x19eb50`, whose
notification hook reaches return-only `0x7d940`. Enabled export `0xb24e0`
stores two normalized bools; SendPendingEvents `0xb2380` examines the local
listener/queues. Source hashes and bounded native instruction records are
stored under `work/messaging-typed-preparation1`.

The service forwards these genuine SDK calls. It does not generate a
registration token, call a token Future, fake availability, change collection
or network settings, or insert a message into SDK/backend queues. It does
not claim desktop FCM delivers notifications.

## Callback and native ownership contract

Messaging has its own eleven exception, three argument, and allocating
string slots and native C thunks. Registering it leaves AppUtil and
Crashlytics slots intact. Existing same-owner synchronous callback admission
remains; unexpected foreign/asynchronous callbacks defer an explicit failure
and execute no guest code. Callback exceptions do not unwind through the
MSVC SDK DLL.

The real SDK calls the message callback with a copied native Message. A zero
int32 return leaves ownership with the SDK, which deletes that copy. A
nonzero return transfers ownership to the guest. The bridge tracks the
actual pointer provisionally during the callback. If original guest code
disposes synchronously, deletion waits until the callback result is known:
zero retains the SDK's single delete; nonzero performs one genuine native
delete. A nonzero retained message remains registered until its later native
delete. Forged, other-subsystem and already-deleted pointers fail closed.

The SDK's token path calls the Messaging allocating string callback first.
The token thunk forwards that exact returned pointer to the original
translated receiver, without allocating a second snapshot or freeing it.
The original receiver retains its own marshalling/free contract.

Installing either callback requires a genuine default App reference. The
native SDK creates a Listener only when both callbacks are nonnull, but
retains each callback slot independently. Pending delivery can still use a
partial registration after the Listener itself is gone. The last App release
is rejected until both callbacks are cleared. Both-null clearing is
forwarded to the actual SDK, and outstanding owned Messages can still be
deleted after detachment/App release. Revoke requires no listener or owned
messages. This is a current raw-pointer ownership profile, with no universal
ABA capability guarantee. Reentrant listener registration remains outside
the admitted registration profile; ordinary message disposal is supported
inside its synchronous callback.

## Qualification and limits

`test_firebase_messaging.py --out <new-folder>` snapshots actual source,
extracts the original 3632-byte APK config unchanged, compiles real ARM64 NDK
callers, translates them and builds/runs a Windows fixture against the pinned
genuine DLL. It tests all seven imports by direct and volatile pointer call,
three-family slot isolation including AArch64 stack arguments, empty native
polls, real listener attach/clear, bool32 forwarding, ownership return values,
deferred disposal, real delete, parent release guards and quiescent revoke.

Callback ownership tests are explicitly transparent observer instrumentation:
the selected SDK poll runs first, then the observer invokes captured thunks
with genuine locally constructed SDK Message objects. It emulates the
documented native SWIG zero-return delete contract without enqueuing any
event. A genuine SDK Message string getter exercises the Messaging allocating
callback; an explicitly local ABI payload passes through the captured token
thunk and the translated fixture frees the exact allocation. This payload is
not a registration token and is never sent to Firebase.

Q2 passes 1401 checks, 106 translated calls and 55 callbacks, two exact string
allocations/frees, seven native listener calls, thirteen polls, five service
native deletes and four observer SDK-contract deletes. A separate foreign
callback child passes 1046 checks. The unchanged Crash Q3 fixture, frozen ARM64
guest and translated objects pass 1443 checks/107 calls on the new48 service;
its foreign mode also passes. The unchanged App lifetime fixture and guest
pass positive, missing-config, original18 and foreign modes; genuine native
dependency status remains7. Old whole SDK files are historical inputs, not
equal to the changed current files; those behaviors are requalified here.

Q1 preserves a fixture-only unused-helper warning promoted to error. Q2
passed the complete initial fixture. Root review then identified that partial
callback registration must retain its parent App. The production condition
now retains the parent when either callback is nonnull. Q3 additionally
checks both partial forms by direct/pointer calls, the pinned SDK's actual
callback slots and absent Listener allocation, pending callback routing,
last-App release guards, and exact allocating string pointers. Q3 is the
final gate; its immutable receipt records the updated counts and current
production hashes.
These focused fixtures establish native ABI/ownership behavior, not original
managed callback execution, asynchronous delivery, every SDK API, original
game startup or a visible frame.
