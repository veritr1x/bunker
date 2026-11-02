# Reached gettimeofday import

The actual resume/render path reaches `gettimeofday(timeval*,NULL)` from Unity
return PC7036bea8 during allocator startup. `LibC` now appends this import after
sysconf. The Android LP64 output is two signed64 fields: Unix seconds and
microseconds, totaling16 bytes. The real NDK fixture checks that layout.

Windows queries actual UTC with GetSystemTimePreciseAsFileTime. Integer
conversion divides before subtracting the whole-second1601→1970 epoch offset,
handling dates before1970 and all unsigned64 FILETIME inputs without underflow.
The output truncates sub-microsecond ticks and is published through tracked
guest-memory writes. Success preserves guest errno. The Linux implementation
uses the native gettimeofday query; this new focused gate is Windows-only.

Only the reached nonnull-timeval/NULL-timezone shape is currently qualified.
Optional NULL output or timezone output requests fail explicitly rather than
fabricating timezone data or claiming general Bionic/POSIX equivalence. This
adapter reads time; it never changes the system clock or timezone.

The Windows gate passes475 checks and130 actual NDK direct/indirect calls through
three strict trace heads, zero unsupported/unresolved. It checks independent
native UTC brackets, progress, full-range epoch conversion, exact output guards,
errno, tracked same-value writes and concurrent calls. The453-check process CPU
clock/sysconf regression passes against the same updated LibC provider.

```sh
python recomp/windows/test_libc_wall_time.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --support-source FROZEN_HOST/recomp
```

Evidence: ignored `work/libc-wall-time/acceptance.json`. This import's tests do
not establish a completed frame or managed initialization.

Primary contracts: the installed Android NDK sys/time.h and
[Microsoft UTC query](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimepreciseasfiletime).
