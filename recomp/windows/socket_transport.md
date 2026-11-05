# Windows socket transport and shared descriptors

`SocketTransport` supplies native Windows TCP/UDP operations, address formatting,
readiness and descriptor controls. FileSystem and transport use one guest
descriptor namespace; native CRT descriptors and SOCKET values never become
guest descriptors. Open-file status, including nonblocking mode, is shared by
aliases; FD_CLOEXEC belongs to each descriptor. Closing one alias does not close
the resource while another alias or an admitted operation retains it.

The qualification executes one typed NDK dispatcher object in actual static
Bionic and through the current Windows runtime. Both direct and volatile
function pointer forms cover TCP connect/accept/options/peek/transfer/half-close,
UDP sendto/recvfrom and scatter/gather/truncation, generic I/O, duplication,
nonblocking state, mixed file/socket/pipe poll and select, and inet_ntop.
Android LP64 socklen32, poll nfds32, pollfd8, fd_set128, timeval16, iovec16 and
msghdr56 layouts are statically checked against the installed NDK headers.
The ioctl request is an Android int32 argument, including its overloaded
unsigned spelling; caller-owned upper register bits must be ignored.

Canonical records describe validated logical steps, rather than assuming one
record per syscall. Raw call results, actual guest descriptors, endpoint address
bytes and ephemeral ports, connect completion outcome and pipe capacity remain
in pinned logs. Comparison excludes successful-operation errno, which is not
specified, and uses explicit endpoint relations instead of equal ephemeral
ports or descriptor numbers. Failed-operation errno, meaningful readiness bits,
defined lengths, canonical address strings, option values, payloads and canaries
remain exact. Actual NDK entry/API call counts and canonical record counts are
reported separately; pressure and short-I/O loop counts may differ by OS.

Pipes are bounded guest byte channels backed by owned memory and native C++
condition variables. The implementation is explicit about that ownership;
Windows socket buffers do not stand in for PIPE_BUF guarantees. Tests fill a
nonblocking pipe, release one byte, and require a 4096-byte write to fail with
EAGAIN without publishing a partial record. Separate concurrent NDK writers
produce 64 complete 32-byte records with no torn payloads. EOF, EPIPE, aliases,
empty nonblocking reads, mixed readiness and real blocking-reader progress are
checked. A separate 196643-byte blocking write must complete its full input while
a concurrent reader drains actual queued bytes, with complete payload/canaries.
Static Bionic's reference process ignores SIGPIPE so its EPIPE return
can be compared; guest signal integration is a separate bootstrap gate.

Additional Windows tests exchange real TCP and UDP payloads with independent
native Winsock peers, including a 131111-byte TCP scatter/gather exchange with
partial-send progress and full MSG_WAITALL receive/canary checks. Native errno,
LastError and nondefault floating state are
checked at the installed socket/shared-I/O boundary, with State1200/Memory64
transport and caller register/canary checks. Current frozen FileSystem code
also runs the existing regular-file duplication/OFD/mmap and file ABI tests.

The QEMU socket-type translator drops unknown socket flag bits. Consequently,
socket type 99 reaches its host as raw type 3 and cannot prove Android kernel
validation of the original value. The canonical reference uses invalid low type
15 instead. A separate Windows check requires EINVAL for unknown flag bits,
following Linux kernel validation; the older raw QEMU observation is preserved
and is not normalized into an equivalence claim. Only TCP and UDP socket kinds
are provided by this transport. Valid unsupported kinds, optional interface
controls, and regular-file F_SETFL outside the retained file policy remain
explicit capabilities rather than successful substitutes.

Positive SO_LINGER is rejected with EOPNOTSUPP before changing native state:
an always nonblocking native socket could otherwise fail its final close and
leak the handle. The Windows capability test verifies unchanged state after
that rejection and real off/abortive-zero options. It does not claim general
positive-linger semantics or compare this capability limit to Bionic success.

QEMU 8.2.2 has a separate AArch64 F_GETFL artifact: its target header omits the
O_LARGEFILE override and inherits generic 0x8000, then injects that bit on a
64-bit host. Android's actual AArch64 0x8000 is O_NOFOLLOW; O_LARGEFILE is 0x20000.
The pinned Android kernel allocates socket files with O_RDWR and O_NONBLOCK.
Only the Bionic side of the three named status records removes this proven
spurious bit; exact Windows values 2 or 2050 and every other bit remain checked.
All six raw discrepancies remain in logs and a separate source/probe receipt.

Socket wait observations and physical collector admission are separate gates.
Functional readiness does not prove that a socket wait can publish collector
roots or deliver managed signals. No external service, backend, synthetic game
image, network setting change or original-game execution belongs to this gate.
Optional interface enumeration/binding and ancillary control messages are
explicit capability limits until required by an actual game call path.

Primary sources:

- https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/sys/socket.h
- https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/poll.h
- https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/bits/ioctl.h
- https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-start-page-2
- https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-wsapoll
- https://github.com/torvalds/linux/blob/v5.15/net/socket.c
- https://github.com/qemu/qemu/blob/master/linux-user/syscall.c
