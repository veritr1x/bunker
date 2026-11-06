# Asynchronous native finishing acknowledgment

`BeginPauseNative(finishing)` queues the existing PAUSE message and native
acknowledgment Runnable exactly once on the same UnityMain FIFO. It returns to
the caller without waiting. `PollNativePause()` returns false while that actual
Runnable remains incomplete, returns true once on genuine successful completion,
or consumes and rethrows its actual callback exception. Polling without an
outstanding request, duplicate requests, worker self-calls and Activity resume
while a pause acknowledgment is outstanding are rejected.

The original finishing branch is unchanged: finishing goes directly to
`nativeDone`; a nonfinishing request calls `nativePause` and selects `nativeDone`
only if its original boolean result requests it. Status changes remain after
the native call and JNI exception check. A pending result never invents
`native_done`, clears a Java exception, acknowledges collector work, or cancels
the original callback.

The existing synchronous `PauseNative` still waits four seconds and raises its
original timeout error. The timeout leaves the genuine request available for
later polling. Owners using the new asynchronous API must retain the lifecycle,
HWND and providers, pump their UI events, and wait for real completion or failure.
They should not enqueue new native focus/surface work behind a finishing callback;
after successful acknowledgment the existing detach/stop sequence applies.

`test_unity_async_pause.py` freezes the selected lifecycle/JNI/Runtime inputs and
compiles transparent native callbacks. The focused test holds a real UnityMain
callback for 4.5 seconds while the owner polls, verifies the legacy four-second
timeout and later completion, checks callback Java-error propagation, tests both
nonfinishing branches, and checks same-worker FIFO and provider/JNI lifetime.
The unchanged existing frame and surface fixtures run against those providers.
These tests execute no original Unity entry, game, HWND, full bootstrap or Firebase
shutdown. Bootstrap event-loop integration and original-game shutdown are separate.
