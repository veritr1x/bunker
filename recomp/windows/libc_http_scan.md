# Original HTTP/RTSP status-line scanner profiles

The original `socket-tls1` run completed three `nativeRender` calls with zero
draws, exported 60 public CA certificates to UnityTLS, and then stopped at
`sscanf` with the literal format ` HTTP/%d.%d %d`, LR `0x70b5680c`.
The input text and parsed status were not logged. These observations establish
the next compatibility boundary, not a completed TLS verification or frame.

Read-only original-ELF analysis found four formats in the same caller FDE
`0x70b56620..0x70b574f8`:

| Exact format, including initial ASCII space | Call LR | Outputs |
| --- | --- | --- |
| ` HTTP/%d.%d %d` | `0x70b5680c` | Three int32 |
| ` HTTP/2 %d` | `0x70b56834` | One int32 |
| ` HTTP %3d` | `0x70b56a28` | One int32 |
| ` RTSP/%d.%d %3d` | `0x70b5698c` | Three int32 |

The boundary receipt is
`work/socket-tls1-http-scanner-boundary1/acceptance.json`, SHA256
`d58d4f29802701417640bd700cc26428087bc0e3dae0031add1f0eac0a7d929a`.
Only these four exact strings enter the new bounded decimal/literal scanner.
The existing four string profiles and `%llu` keep their admission and behavior;
the import markers and typed bridge remain unchanged.

Format whitespace consumes zero or more of the six ASCII whitespace bytes.
Each decimal conversion separately skips leading input whitespace. A field
width of three includes an optional sign, excludes preceding whitespace, and
limits the numeric token. The other conversions use Android Bionic's 512-byte
token bound, including a sign. Literal mismatch, input exhaustion and partial
assignment return the observed assignment count; only assigned outputs publish
four bytes, in conversion order, through the shared guest-memory protocol.
The source snapshots input and format before publication and retains the
existing checked-output policy.

Android 13 [vfscanf.cpp](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/stdio/vfscanf.cpp)
uses `strtoimax` and narrows to `int*`; its
[strtol.cpp](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/bionic/strtol.cpp)
supplies signed64 saturation and ERANGE. The bounded implementation follows
that target behavior: signed64 magnitude overflow sets guest ERANGE34, then the
low32 bits are published. Out-of-int32 conversions are not portable ISO C
guarantees. The fixture explicitly labels those and token-boundary cases as
Bionic implementation observations rather than using host CRT results as the
reference. No general `scanf` grammar or foreign `va_list` API is admitted.

## Qualification

`work/libc-http-scan-qualification2/acceptance.json` passed, SHA256
`63b91371a38dd2690defdca373927217748892bd1d569a587c63ab4da6155a6f`.
It binds production `libc.cpp` SHA256
`346b267fe6f37b12b33c405df758cb46cbfd88fc188800614808993ecf49a037`,
unchanged `libc.h` `c905aeabd038efa235a934702f3a132e19f7e475ad6f1b1843e85022b11f749c`,
and unchanged resolver dependency
`c08b53fc851e9f2d744d2c6d551e8f310baef6d974fd76baca46c59ced3ad150`.

The same actual NDK caller object, SHA256
`e01bde00bc110bbbd1329c58616da16e904cab829543536014fb00d6f5df5ae3`,
is linked into a static AArch64 Bionic executable and into the lifted Windows
component. The reference has no PT_INTERP and carries aligned real PT_TLS.
The receipt pins the NDK compiler, static libc archive, QEMU executable,
lifting semantics, native compilers, generated objects and logs.

The 104 cases run through direct and volatile function-pointer variadic calls:
208 complete result/errno/output-and-canary records match exactly, with no
normalization. Of these, 38 are labeled implementation observations. The
canonical record digest is
`502afdffaf70ff44bd791494f350214db88e4b19ff985fac9a8537c92939dccc`.
Cases exercise exact literals, leading/inter-field whitespace, EOF and
truncation, malformed and signed input, width-three boundaries, partial
assignments, representable int32 limits, and target overflow/token behavior.

The Windows focus passed 1,384 checks and 228 actual NDK calls: 208 differential
calls, four additional output-alias/mismatch calls, and 16 concurrent calls.
It verifies assignment order with aliased int outputs; same-value tracked
publication versus mismatch using real exclusive reservations; thread-local
guest errno; native errno, LastError and nondefault FENV at the installed
typed bridge; and the full State1200 layout, saved high64 registers, SIMD128,
PC/SP and opaque Memory64 identity. Two translated traces and two objects have
no unsupported traces or unresolved direct targets.

One fresh regression against the current provider passed 387 checks and 51
actual NDK calls for the existing four string profiles and `%llu`. Its complete
records still match their original static Bionic reference, digest
`b49ce65478e7851ca5f966e83b171ce4d23af9697a7a2e8f25efceb3ff0def11`.
These counts are separate from the focused 228 calls.

Qualification1 preserved the successful static reference, then stopped at a
fixture-only `-Werror=misleading-indentation` diagnostic on its thread-join
loop. Qualification2 adds braces, reuses the exact pinned reference and caller
object, and freshly compiles the held provider. No production correction was
needed. This component gate does not run the full host/game, infer response
content, change settings, or establish a completed rendered frame.
