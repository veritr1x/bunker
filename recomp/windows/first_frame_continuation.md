# Original render continuation

The first original render in `windows-first-frame-launch-url1` returns true
without drawing or presenting. The first-frame diagnostic therefore needs more
than one render request. It keeps the original UnityMain, Activity, window,
surface, guest stack, TLS and collector registration, and calls nativeResume
once. The ordinary one-frame profile keeps its existing single-call behavior.

Each explicit request owns a fresh promise. Polling distinguishes a pending
call from the original false return and propagates failures. A new request is
admitted only after a true result, completed FIFO work, an acquired surface,
resumed Activity and acknowledged actual window focus. Owner focus is checked
under the same lock as the worker state. Loss of focus blocks new requests;
window events continue to be drained while a render is pending. Pause, stop
and destruction settle an unused request and retain resources until the live
worker finishes and joins.

The image observer pairs a pre-swap readback with a unique ticket containing
its native thread, EGL display, context and draw surface. Only that same
original swap returning EGL_TRUE publishes the PNG. A failed, mismatched or
already consumed ticket cannot qualify, even if another swap succeeds. The
observer preserves graphics state, errors and the caller's environment. Uniform
frames do not exhaust a fixed capture budget before a later game image appears.

Acceptance still requires original drawing, a nonuniform PNG, that capture's
own successful original swap, and a returned original nativeRender. Component
fixtures and their synthetic images do not establish an original game frame.

The lifecycle gate passes236 frame checks and53 unchanged surface checks on
each Windows/Linux host. Receipt
`work/unity-frame-continuation-qualification4/acceptance.json`, SHA256
`c36afff295df66a4ffedb8ed235cd5dae8680ab2517d71634c6776c4bf0913d4`.
This includes distinct pending/false/exception results, duplicate requests,
focus acknowledgment and recovery, surface prerequisites and cancellation.

The real ANGLE component fixture passes242 checks, including65 uniform swaps,
failed candidates followed by unrelated successes, mismatched thread/context/
surface tickets, and a final matching successful swap. Its synthetic triangle
PNG is independently decoded. Receipt
`work/capture-present-ticket1/acceptance.json`, SHA256
`bb492c496ac589fee0e8fc6d9ef2e528e763cae6ea1818d4f3b6fed1cdc7385a`.
Existing typed GL commands, marker order, EGL implementation and GL operation
bodies remain exact outside the selected diagnostic capture spans.

The shutdown callback `ReflectionHelper.endUnityLaunch()` now increments its
retained per-Host launch epoch modulo2^64, matching the original DEX read/add/
write. Separate relaxed load/store operations retain the unsynchronized
operation's possible lost updates without a C++ data race. Actual NDK direct,
V and A callers pass26 checks per Windows/Linux host. Receipt
`work/reflection-launch-epoch-qualification2/acceptance.json`, SHA256
`f16ab0de0b1b4998035c920072afee424af189114929251da492e82e3a131cc1`.
This does not implement the independent reflection cache initializer or expose
an unbacked Java long field. ReflectionHelper proxy creation/accessor/dispatch
remain unsupported and must share this epoch when implemented. The existing
bitter/JNIBridge proxy family remains independent.

The integration passes the existing default/enabled collector syntax checks
and expected missing-cohort rejection in `work/game-collector-source13`.
No original guest translations, collector rules, protected JNI/runtime bodies,
audio-disabled APK or device settings change in this repair.
