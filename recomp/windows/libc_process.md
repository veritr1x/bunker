# Android process CPU clock and scoped sysconf

`LibC` appends two imports, `clock` and `sysconf`, after the existing locale
markers. Old marker addresses remain unchanged. This supports the actual
IL2CPP GC-chain calls at RVAs0x25a6eec (clock),0x25b18d4 (sysconf39), and
0x25b1b18 (sysconf97); it does not establish collector startup or suspension.

Android ARM64 `clock_t` and the `long` returned by sysconf are signed64.
`CLOCKS_PER_SEC` is1,000,000. The actual NDK fixture checks those facts at compile
time and calls both imports directly and through volatile function pointers.
Windows CRT long/clock_t and host sysconf enum values are not passed through.

`ProcessClock()` returns process CPU microseconds. Windows uses the real
GetProcessTimes current-process kernel and user totals, including other threads.
Its100ns durations are added with quotient/remainder conversion, so even the
sum of two maximum64-bit inputs does not overflow an intermediate. Linux uses
native CLOCK_PROCESS_CPUTIME_ID and checked seconds/nanoseconds conversion.
The returned resolution remains that of the real host CPU accounting; the
microsecond unit does not promise microsecond precision. Successful calls
preserve guest errno. Real API failures return-1 with a mapped guest error.

`Sysconf(int32_t)` implements only these Android names:

| Android name | Value | Real backing |
| --- | ---: | --- |
| _SC_PAGESIZE |39| Windows GetSystemInfo.dwPageSize; native Linux sysconf page size |
| _SC_PAGE_SIZE |40| Same actual page-size query (a distinct Android alias) |
| _SC_NPROCESSORS_ONLN |97| Windows GetActiveProcessorCount(ALL_PROCESSOR_GROUPS); native Linux online count |

The processor count is the actual system online count, with no synthetic1-CPU
fallback or affinity-based substitution. API failure/invalid nonpositive host
data returns-1 with guest errno. Success leaves guest errno intact.
`libc_sysconf_names.inc` pins all148 names from the Android13 primary header,
whose SHA256 is recorded in the file. The actual NDK compiler independently
checks every value. Known but unimplemented names throw an exact-name diagnostic
(fatal through a Runtime import); they never masquerade as invalid or
indeterminate limits. Truly unassigned names return signed64 minus1/EINVAL22.

The focused gate passes453 checks and57 actual NDK calls on both native Windows
and Linux through5 strict translated traces, zero unsupported/unresolved.
It compares process CPU samples against independent native brackets, measures
CPU-work progress, distinguishes sleeping from CPU work, and verifies another
thread contributes to the process total. Eight simultaneous callers verify
guest errno isolation. It also covers169 extreme100ns sum/conversion pairs,
all148 valid Android names, invalid/reserved IDs and a separate fatal probe for
a valid unimplemented name. Actual pages and online counts are printed; the
tested host reports4096 bytes and16 processors. Numeric busy/sleep/worker CPU
evidence is printed without imposing a fake host clock precision.

Run from WSL with the NDK and a frozen lifter/semantics pair:

```sh
python test_libc_process.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --remill REMILL_HEADERS --windows
```

Omit `--windows` for the Linux host gate. Existing full LibC and Bionic locale
regressions should accompany provider changes. Platform-query failure mapping
is implemented, but tests do not claim to have forced real Windows process-query
or processor-query failures. No GC runtime, signal policy, polling, stack-root
integration or actual collector initialization is provided by these imports.

Primary references:

- [Android13 clock implementation](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/clock.cpp)
  uses process CPU time and the Android clock-unit conversion.
- [Android13 sysconf implementation](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/sysconf.cpp)
  and [name constants](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/bits/sysconf.h)
  establish the distinct page-size aliases and online processor query.
- [Microsoft GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)
  defines the process kernel/user CPU durations and100ns units.
- [Microsoft GetActiveProcessorCount](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getactiveprocessorcount)
  defines the all-groups system count and zero-on-failure behavior.
