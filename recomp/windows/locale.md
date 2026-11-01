# Android locale adapter

Unity's first actual `nativeRender` call reached `newlocale(0x1fbf, "C", 0)`
at return PC `0x70e56ad4` while formatting a captured Java exception. The
original exception is a missing PackageManager method; supplying locale
objects does not turn that failure into a successful frame.

`LibC` now supplies the three locale imports in this Unity image:
`newlocale`, `uselocale`, and `freelocale`. Contracts follow
[Android 13 Bionic locale.cpp](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r1/libc/bionic/locale.cpp)
and [locale.h](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r1/libc/include/locale.h).
Accepted names are `C`, `POSIX`, `C.UTF-8`, `en_US.UTF-8`, and the empty
name (UTF-8). Unsupported names return null/ENOENT; invalid masks or a null
name return null/EINVAL. The Android mask excludes bit 6 (`LC_ALL`). Bionic
ignores `base`, including with a zero mask, and creates a fresh object.

The adapter maintains checked, provider-owned objects with the Android LP64
eight-byte `mb_cur_max` field. Native thread-local selections begin at
`LC_GLOBAL_LOCALE` (`-1`); the initial global profile is Android's C.UTF-8.
`__ctype_get_mb_cur_max` now returns 4 for that profile and 1 for a selected
C/POSIX locale. The previous unconditional return of 1 was incorrect for the
Android initial profile. No Windows/Linux process locale or environment
variable is consulted or changed. Narrow C character classification and
numeric punctuation remain the existing C behavior in either supported
profile. This does not implement wide-character or UTF-8 conversion APIs.

Object storage is quarantined until provider shutdown, making retired locale
identities non-reusable. Guest memory publication and retirement participate
in tracked memory and exclusive reservations. Using a foreign or retired
object fails explicitly; freeing a currently selected object is invalid
caller behavior and its subsequent metadata access is rejected. A provider
must outlive its workers. Unique provider identities isolate selections from
other providers, replacement instances and native thread-ID reuse.

`test_locale.py` compiles actual Android NDK ARM64 callers and exercises
selection, masks, aliases, errors, unchanged errno on success, ignored base,
and multiple objects. Its host harness additionally checks 12 real threads,
ownership, retirement, and exclusive-reservation behavior. This is source-
audited Bionic behavior tested through the NDK call ABI; it does not execute
the Android Bionic shared library. `setlocale`, `duplocale`, `localeconv`, and
unimplemented `_l`/wide-character routines remain unresolved.

The final Windows and Linux gates each pass **71 checks**, including 29 NDK
caller scenarios and the cross-thread reservation test. The fixture lifts to
9 traces with zero unsupported instructions or unresolved direct targets.
The full pre-existing libc regressions also pass: 4,297 Windows / 4,293 Linux
native checks, seven translated NDK startup gates, and the deliberate fatal
import/destructor diagnostics. Evidence is under ignored
`work/locale-{windows,linux}` and the `*-final.log` files in `work`.
