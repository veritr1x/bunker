# Focused JNI byte arrays

The component executes NDK-compiled C callers through the actual `JNIEnv`
vtable for slots 171, 176, 184, 192, 200 and 208. The checked host supplies
owned byte-array copies with `isCopy=1`; release modes 0, 1 and 2 respectively
copy/free, copy/retain, and discard/free. Tests cover byte values, exact region
bounds and writes, lease misuse, JNI references and thread/frame lifetime,
typed `[B` methods/fields, nested byte-reference arrays, and pending-exception
identity during permitted release cleanup. They also retain a small existing
reference-array control.

This is a host qualification using genuine NDK calling conventions, not an ART
runtime claim. Invalid lengths, bounds, types and lease releases exercise the
host's defensive policy. Region buffers remain nonNULL even for zero length.
The fixture does not use ordinary array operations while an exception is
pending as a Java-runtime oracle. It checks the 1200-byte State ABI and an
opaque 64-bit Memory token without replaying the historical JNI suites.
