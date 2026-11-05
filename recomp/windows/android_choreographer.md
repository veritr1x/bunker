# Asynchronous UnityChoreographer port

This adapter supplies the HandlerThread/Looper/Handler/Message/Choreographer
closure reached by original constructor `70437178..704372f0`. The original
constructor sends message0 while holding its own mutex, then waits for its own
predicate through `pthread_cond_wait` at LR`704372c8`. Calling its callback
synchronously from sendToTarget would deadlock. The adapter neither reads nor
writes that predicate, native mutex or condition; the actual original queued
callback must publish and broadcast.

The constructor also briefly creates a default Handler on UnityMain before
replacing it with the child-Looper Handler. Although that temporary Handler is
not sent a message in this FDE, its constructor genuinely requires the current
thread's prepared Looper. Root therefore binds the actual existing UnityMain
native lifecycle FIFO with PrepareCurrentLooper rather than fabricating a
successful Handler on an unprepared thread.

The original dispatcher uses message0 to obtain a Choreographer and publish its
native payload, message1 to post the original FrameCallback, message2 to remove
it, and message3 to publish null during shutdown. Its destructor then constructs
a temporary singleton Handler.Callback proxy, whose actual callback follows
Message.getTarget→Handler.getLooper→Looper.quit before Thread.join. This explains
why the active proxy profile includes both the ordered pair
`[Handler.Callback, Choreographer.FrameCallback]` and singleton Handler.Callback.
The entry recovery and original boundary artifacts are owned separately; this
service does not replace original computed cases or native bodies.

## Real callback route

The factory remains `bitter/jnibridge/JNIBridge.newInterfaceProxy(J,Class[])`, not
ReflectionHelper. It preserves the full opaque handle, actual application
loader, exact ordered interface identities and one shared recursive invocation
monitor. No callback occurs during factory creation: the native owner is not
fully constructed then.

An actual Handler or frame dispatch enters the implementing Java proxy method.
That method obtains the real interface MethodID, converts it using JNI
ToReflectedMethod, and calls the **actually registered** JNIBridge.invoke through
the supplied Runtime/Pthreads native runner. Its arguments are JNIEnv,
JNIBridge class, unchanged handle, real declaring class, reflected Method and a
real one-element Object[]. The original native invoke calls
FromReflectedMethod and performs its own native virtual dispatch. Guest handles
are never cast into Windows C++ objects or manually routed to guessed entries.

Frame timestamps are owned Long objects, unboxed by the original native helper
through Long.longValue()J. Handler results are Boolean objects constructed by
the original helper through Boolean.<init>(Z)V, then genuinely unboxed through
booleanValue()Z. These adapter-backed values implement this bounded callback
boxing profile. Existing unrelated SharedPreferences box payloads are not
misinterpreted or assigned fake zero values. A disabled primitive-boolean proxy
returns null from its handler and therefore raises NullPointerException when
unboxed, matching the generated Java proxy contract; disabled void callbacks
make no native call. Existing four passive proxy families remain unsupported
for active native dispatch. Unknown interfaces and Object/default-method bodies
continue to fail closed. No automatic native delete or invented finalizer is
introduced; actual native destruction owns disable/release.

## Threads, queue and ownership

HandlerThread.start creates a real native thread. Its required preparation hook
runs on the actual creator immediately before creation and returns an owned
passive context lease. The child enter hook receives that exact lease and must
attach its real JNI thread and register its actual Pthreads/signal context.
The exit hook releases native thread/TLS resources while JNI is still usable
and detaches as appropriate. No creator, thread token, mask or attachment
result is inferred on the child.

getLooper waits for actual child preparation. Message.sendToTarget enqueues and
returns; FIFO dispatch occurs on that prepared child. Queued messages retain
their Handler, which retains the callback. Each dispatch has an owned JNI local
frame. The Message.what int field and getTarget/getLooper chain are genuine
backed objects. The actual base Handler.handleMessage body is empty; no Runnable
or user-subclass Handler bodies are claimed by this profile.

Choreographer.getInstance uses the current prepared Looper thread. It fails on
an unprepared caller and returns the same instance on repeated calls on that
Looper. Frame requests retain their actual Java callback until delivery,
removal or cancellation. Delivery is one-shot: the original native callback
must post itself again. Removal matches Java object identity, and quit cancels
pending frames, including a due batch not yet admitted to invocation.

Stop rejects new worker admission, marks queues as quitting, cancels pending
work and joins actual workers. Already-admitted callbacks can complete and
attempt a repost into the quitting queue without premature provider revocation.
Only after joining does Stop revoke the service. Java join and owner Stop share
a native join claim and condition variable; queue/provider locks are released
across native joins and callbacks. The service must be stopped from its owner,
not from one of its own callbacks. A callback can use its real Looper.quit.
Asynchronous failures are retained for CheckHealthy/Stop and notified through
the optional failure hook; no fake initialization acknowledgment is produced.

Externally owned lifecycle workers use PrepareCurrentLooper(name, wake_owner),
PumpCurrentLooper and ReleaseCurrentLooper. Preparation requires the actual
already-attached owner and creates its backed Looper/message queue. A sender
retains its message and invokes the owned wake callback outside queue locks;
the callback must only enqueue a task on the existing native owner FIFO.
Pump executes that task on the actual prepared owner, and never creates another
thread or dispatches synchronously from sendToTarget. A rejected wake means the
owner is stopping and cancels its queue. Callback/reference retirement occurs
on real delivery, removal or cancellation. Release runs on the same owner after
its callbacks quiesce, cancels remaining messages and removes its mapping.
Service Stop rejects an unreleased external Looper before cancelling anything;
the external lifecycle must stop/release first. Frame posts on external Loopers
fail explicitly before acceptance because a genuine external deadline-wakeup
integration is outside this reached profile. The original Choreographer uses
the dedicated owned HandlerThread, whose frame scheduling is implemented.

## Explicit Windows frame clock

The owner must supply a genuine monotonic timestamp and an observed Windows
refresh numerator/denominator. There is no guessed default refresh. The service
uses that ratio for a nominal frame period and bounded native CV waits; it
passes the sampled monotonic timestamp to doFrame. It does not claim Android
display events, DWM vertical-blank observations, compositor synchronization or
that a timer expiration proves a presented frame. Callbacks and the original
renderer determine actual progress. Refresh changes apply when subsequent
nominal deadlines are scheduled.

Root integration must construct SharedPreferences first if it supplies the
existing Long/Boolean classes, then AndroidChoreographer (framework interfaces),
then the active JniInterfaceProxy with run_native. Required owner order is:
stop/join this service before Pthreads shutdown, proxy/native/module retirement
or Host destruction. The actual original shutdown-message path may stop/join
its worker earlier; service Stop remains the owner-side quiescence fence.

Framework queue/error behavior follows pinned Android13 source copies in
`work/android-choreographer-primary1/sources.json`: [Handler](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/Handler.java),
[HandlerThread](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/HandlerThread.java),
[Looper](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/Looper.java),
[Message](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/Message.java), and
[Choreographer](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/view/Choreographer.java).
This is a bounded native port, not ART, general Android scheduling, message
pooling, arbitrary Java Thread execution or Java garbage collection.

Qualification and an original first rendered frame are separate outcomes. A
component callback, timer tick or native initialization broadcast does not by
itself establish a first frame.
