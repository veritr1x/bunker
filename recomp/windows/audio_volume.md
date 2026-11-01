# Read-only Windows audio-volume observer

`AudioVolumeObserver` creates a dedicated COM MTA worker, reads the actual
default render/multimedia endpoint's level and mute, and registers endpoint
volume plus default-device notifications. It does not create an audio stream,
change system volume/mute, or call guest code from a COM callback.

Callbacks request work; the owner queries current native state. Delayed or
out-of-order payload values are not published as current volume. A generation
rejects late notifications from a replaced endpoint. Snapshots and a bounded
change queue are synchronized; initial state is cached without an initial
change event. Missing endpoints and native failures retain HRESULTs, rather
than pretending a volume/device is available. Caller code must check available,
stopped, status and callback_status. Stopped snapshots describe cached history.

The native value is an
[audio-tapered normalized endpoint level](https://learn.microsoft.com/en-us/windows/win32/api/endpointvolume/nf-endpointvolume-iaudioendpointvolume-getmastervolumelevelscalar),
not linear signal amplitude. Endpoint subscriptions follow Microsoft's
[AddRef/unregister rules](https://learn.microsoft.com/en-us/windows/win32/api/endpointvolume/nf-endpointvolume-iaudioendpointvolume-registercontrolchangenotify).
Device notification subscriptions follow their distinct
[caller-owned lifetime rule](https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdeviceenumerator-registerendpointnotificationcallback).
Unregistration occurs on the owner outside callbacks, then the worker joins.
Cleanup errors remain sticky across later status publication. Callback objects
retain only safe shared state; they do not own the observer or worker.

The Windows gate passes **266 live endpoint checks**, including independent
native queries, real subscriptions, concurrent readers, cleanup and restart.
It separately passes **529 synthetic callback-mechanics checks** covering
notification concurrency, deferred owner queries, old generations, bounded
queues, stopped callbacks and COM/state lifetimes. These synthetic events are
not claimed as real OS volume changes. Tests do not change this machine's
volume, mute or default endpoint; live external change delivery remains an
additional observation gate.

```powershell
recomp/windows/test_audio_volume.ps1
```

The APK's AudioVolumeHandler caches the initial STREAM_MUSIC index, emits no
initial native callback and notifies only on index changes. Its native handler
converts index==0 to mute, and its setter returns immediately for unchanged
mute state. A declared 0/1 host profile from actual mute/zero-level state thus
supplies this observed mute-only contract without inventing a hardware volume
maximum. The JNI/lifecycle adapter owns that mapping, UI-caller dispatch and
pause-time unsubscription. This observer alone does not implement Android audio
playback or establish full Unity resume/game operation.
