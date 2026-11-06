# Host Throwable diagnostics

Run17 reports the missing NotificationManager class, then a second missing
class, `android/util/Log`, while Unity formats the first exception. Original
`AndroidJNISafe.CheckException` calls static
`getStackTraceString(Throwable):String` after obtaining and clearing the pending
exception. The formatter is diagnostic; it does not complete notification setup.

The checked JNI host now implements that method for its initialized Throwable
objects. Those objects contain an actual class and optional message, with no
captured Java frames, cause or suppressed exceptions. The formatter invokes
the real virtual `Throwable.toString` path and appends a newline. Null and
UnknownHostException subclasses return an empty string. Plain uninitialized
instances, wrong argument types and unimplemented cause/stack overrides are
rejected. No Java or Windows frames are invented.

The focused gate `work/jni-log-qualification1/acceptance.json` passes 74 checks
and 24 calls compiled with the Android NDK and translated for Windows. It
covers direct/V/A JNI calls, null versus empty messages, embedded NUL and
supplementary Unicode, a real localized-message override, original
FindClass/ExceptionOccurred/ExceptionClear flow, temporary-reference lifetime
and rejected states. The existing JNI host checks also pass on the changed
source. This gate does not execute the original managed CheckException or
establish a complete Java Throwable interpreter.

The change is not selected by the frozen run17 executable or the subsequent
candidate-only Unity parameter-switch build.

Primary contracts:

- [Unity 2021.3 AndroidJNISafe](https://raw.githubusercontent.com/Unity-Technologies/UnityCsReference/2021.3/Modules/AndroidJNI/AndroidJNISafe.cs)
- [AOSP Log implementation](https://android.googlesource.com/platform/frameworks/base/%2B/47fb191/core/java/android/util/Log.java)
