# Unavailable Android sensor service

The Windows port explicitly selects `SensorService::Profile::Unavailable`.
Its only native export is `ASensorManager_getInstance`, returning a null
manager. It offers no sensor service, event queue, looper, sample data or
physical-device inventory. Other sensor/looper imports remain unsupported.
This optional capability policy is intended for the desktop port, including
first-frame testing without Android motion sensors.

This is a deliberate port fallback, not a claim to reproduce Android's normal
sensor-manager behavior. The [NDK contract](https://developer.android.com/ndk/reference/group/sensor)
describes a singleton manager; the [AOSP implementation](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/android13-frc-resolv-release/native/android/sensor.cpp)
returns a reference-backed manager. An empty Android sensor inventory is a
different state. This port does not infer that Windows hardware has no sensors.

The actual reached Unity function is `704119f8..70411a90`. With its global
queue initially null, it clears576 bytes at `712be048`, calls the manager
getter at `70411a20`, then branches on null at `70411a24` to the real epilogue
at `70411a84`. That path returns without entering looper, queue creation,
enumeration, logging or sensor activation. A preexisting nonnull queue skips
initialization before the getter. No guest instruction or call is removed.
Original caller/import evidence is in `work/audio-disabled1-sensor-boundary1`.

The provider uses the existing AAPCS64 pointer-return bridge and unused marker
namespace `7ff470000000`. It changes no errno, host thread state, device state
or guest memory. Bootstrap prints the explicit policy outside the API call.
Existing duplicate-import checks and the unsupported-import fence remain active.
The header-only integration adds the normal typed provider to the existing
resolver; it changes no JNI, module registry, collector, GL or guest code.

Qualification must execute the complete original caller with the declared
unavailable service and verify the cleared globals, canaries, original return
and callee-saved ABI. The ARM reference uses a named test-only null-manager
seam, not a claimed Android sensor-service result. Native Windows/Linux runs
must use the actual provider, plus translated NDK direct/function-pointer ABI
callers. This gate does not qualify the nonnull-manager path or sensor hardware.

The completed gate matches four records across ARM and Windows/Linux raw/polled
execution, including repeated initialization and an already initialized queue
control. It checks all64KiB of owned globals/canaries, post-null capability
queries, callee-saved ABI, NDK callers, isolated1200-byte State/token preservation
and profile/marker rejection. Receipt
`work/sensor-service-qualification2/acceptance.json`, SHA256
`0c19b5d1045494773f08bc76e5367c712092d094b612801634e8f5611d2a9347`.
The first fixture attempt fails a Windows error-state measurement after all
ARM cases pass. The second captures LastError immediately and compares an
identical Runtime control call; provider and control match. No absolute
Runtime LastError guarantee is claimed, and the provider remains unchanged.
