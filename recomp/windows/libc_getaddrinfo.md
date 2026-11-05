# Name and service resolution

The resolver bindings expose Android LP64 `getaddrinfo`, `freeaddrinfo`, and
`gai_strerror`. Windows uses its real native resolver after checked Winsock
startup. Android families, flags, EAI codes, service parsing, `addrinfo` and
socket addresses require explicit conversion; host `addrinfo` cannot be
published as an Android structure. Numeric parsing, name resolution and service
lookup return real results with owned guest-visible chains.

The focused qualification uses the identical NDK caller object in static Bionic
and translated Windows execution. Direct and volatile function pointer calls
cover complete chain fields, binary addresses, canonical text, errno, output
publication, free/null operations and error strings. Chain records are sorted
for comparison while retaining duplicates. The NDK source statically checks
the 48-byte Android layout and offsets 24/32/40 for canon/address/next.

Deterministic comparisons use numeric and null hosts, numeric/service names,
passive and canonical flags, malformed flags/families/type/protocol hints, and
service range/strtoul edge cases. Environment-dependent DNS answers, interface
configuration and ordering are outside byte-for-byte cross-OS comparison.
Windows separately performs a real native `localhost` name lookup and validates
the published Android chain. This does not establish an external DNS packet,
socket connectivity or game networking.

Successful `getaddrinfo` does not specify errno. Raw Bionic and Windows errno
observations remain in the pinned logs; only that successful-result field is
normalized in the canonical comparison. An isolated Bionic probe shows its
first `strdup` sets incidental errno 22 under QEMU, including inside the first
canonical-name result. No warmup or synthetic errno reproduces that artifact.
Failure errno and free/null errno are compared exactly. The fixtures set errno
immediately before free so preceding record formatting cannot contaminate it.
EAI_SYSTEM/native DNS failure mapping is reviewed in bound source; this numeric
profile does not force that native failure path. Nonempty service parsing has
the explicit Bionic LP64 strtoul zero/range-error side effects.

Additional installed-boundary checks cover native errno, LastError and floating
state, full State1200/Memory64 transport, concurrent native worker calls,
cross-thread chain release, detached suffix release and independent providers.
Only valid C input/output storage is used; arbitrary invalid pointers and
double free are outside the C API contract. Differential call totals and the
additional 32 concurrent NDK calls are reported separately.

Primary sources:

- https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/dns/net/getaddrinfo.c
- https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/netdb.h
- https://learn.microsoft.com/en-us/windows/win32/api/ws2tcpip/nf-ws2tcpip-getaddrinfo
- https://learn.microsoft.com/en-us/windows/win32/api/ws2tcpip/nf-ws2tcpip-freeaddrinfo
