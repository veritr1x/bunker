# Android process identity

The real normal engine initializer reaches `getpid` from original Unity
callsite `9cfd80` (guest return `709cfd84`), through priority -5000 initializer
`a3e694`. Native7 stopped at that explicit unsupported import after all 417
constructors. This provider supplies the actual host process identity using
Windows `GetCurrentProcessId`, or native `getpid` for the Linux host gate.

Android `pid_t` is signed 32-bit. The provider rejects zero, negative native
values, or values above `INT32_MAX` with a decisive diagnostic. It never assigns
a synthetic identity. The typed `int32_t()` bridge returns the Android W0 ABI;
all threads in the same process observe the same real PID. Successful queries
leave guest errno untouched. The marker is appended after `gettimeofday`, so
existing markers keep their identities. No provider memory is published by
this no-argument scalar query.

`libc_pid_guest.c` is compiled with the actual Android NDK API24 headers. It
asserts signed32 `pid_t`, calls `getpid` both directly and through a volatile
function pointer, widens results to signed64, and records actual guest errno.
The Windows and Linux focused gates each pass 490 checks /193 actual NDK calls:
independent native PID comparison, repeated and concurrent observations on four
native threads, PC/SP and callee-register preservation, signed result conversion,
guest/native errno, output canaries and untouched padding. No native overflow
condition was forced; rejection is explicit in the adapter.

Meaningful regressions with the same overlaid LibC pass: process CPU clock,
page-size and online-CPU queries (453 checks /57 NDK calls per platform), plus
Windows actual UTC gettimeofday (475 checks /130 NDK calls, native clock
bracketing, progress, thread errno, tracked output and guards).

Support files are frozen from committed `90b646c`; only the two LibC files and
new PID fixture/test are overlaid. Existing fixture objects and accepted
78e33/098d2 lifter/semantics are retained. The focused fixture has four translated
roots, zero unsupported traces and zero unresolved direct targets on each
platform. Evidence is ignored `work/libc-pid/acceptance.json`; sources, fixtures,
toolchain and executable hashes are recorded there.

Run under WSL with a fresh output directory:

```sh
python test_libc_pid.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --support-source FROZEN_HOST/recomp --out NEW_RESULT
```

This gate establishes process identity and the stated regressions. A completed
engine initialization, rendered frame and playable game remain separate results.

The fresh work-only Native8 host (frozen `90b646c` plus the tested two-file LibC
overlay and the accepted 16 original hash-tail entries) passed the prior getpid
boundary on the actual nativeRender path. It stopped at missing Java APIs:
getContentResolver, ServiceConnection, then the unimplemented original APK
UnityPlayer.initializeGoogleAr()Z method. Complete command/input/executable/log
hashes and diagnostics are in `work/windows-unity-native8/acceptance.json`.

Primary contracts: installed NDK `sys/types.h` / `unistd.h`, and
[Microsoft GetCurrentProcessId](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getcurrentprocessid).
