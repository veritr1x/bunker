# Private futex wait and wake

`SignalFutexes` provides Android ARM64 syscall98 with untimed
FUTEX_WAIT_PRIVATE/op0x80 and FUTEX_WAKE_PRIVATE/op0x81. It retains the public
signed64 return convention and actual raw X0–X6 witness. The ARM64 kernel
narrows the syscall number to32 bits; operation/value fields likewise use their
low32 bits. It never forwards Android syscall numbers to the host kernel.
Other syscall numbers and operations stop explicitly. The subsequently
qualified [relative timed WAIT extension](signal_futex_timed.md) handles nonnull
timeouts; the original untimed bodies and this baseline qualification remain
preserved.

One provider owns a process-private numeric-address namespace. Its queue lock
covers fault-safe word comparison and ticket enrollment, preventing a wake
between those steps. WAIT returns EAGAIN11 on mismatch or EFAULT14 for an
inaccessible word. WAKE selects actual enrolled tickets, returns their count,
and retains no credits. It does not inspect mappings or read/write the word.
The selected Android13 kernel behavior wakes one ticket for a nonempty queue
even when the signed wake count is zero or negative. No collector counter,
semaphore post or acknowledgment is synthesized.

The explicit untagged virtual-user profile covers lower48-bit four-byte spans.
Alignment errors precede range checks. Tagged-address eligibility depending on
TBI/PR_TAGGED_ADDR_CTRL is an unsupported boundary. This is a software profile,
not an inferred Windows mapping or original device configuration.

New `WithGuestMemoryRead` holds the existing Runtime memory lock without
invalidating reservation epochs. Its short callback only reads into private
host storage; guest calls, writes, waits, allocation and protocol reentry are
forbidden. WAIT uses ReadProcessMemory/self on Windows and process_vm_readv/self
on Linux, returning real read faults without a check-then-memcpy race.
Unexpected native API failures remain named boundaries. Lock order is queue
then memory; error sinks, notifications and guest handlers run outside both.

A caught handler withdraws the ticket before execution. A prior genuine wake
wins success; otherwise an un-restarted wait returns EINTR4. SA_RESTART retries
the original expected value with a fresh comparison and enrollment, so a
handler changing the word produces EAGAIN. Excluded eligible signals remain
pending. Native errno/fenv/LastError are preserved; observation scopes end
before actual dispatch. Providers and dispatchers outlive worker drain.

The game adapter admits zero signals at this boundary. Its full entry/return
log records actual token, native TID, registers and SP/LR. Only the original
LR702ad510 site may read its saved caller at SP+24, after the actual thread's
owned stack covers the exact32-byte frame. This witness does not establish
that a call blocked, identify an application role, or publish GC roots.

Qualification3 acceptance SHA256 is
`3d1bd842e61a88dd162b3a59e454ea3a7e8e921b99bcd0f94bc9b900a90f87ac`;
held receipt `work/signal-futex-held1.json` SHA256 is
`4ff64da762f073af3a1eb73e7a88289c06986aedc9f5e245b882095eb36baf5b`.
Final component/wiring peer SHA256 is
`c6aeb7b109729b1a347a7a87d875180cafecaacf87d6d0aa44009ea2df8246e3`;
static/source/capability acceptance SHA256 is
`3cc3a1f2d134e02409a2bb8a802f620b1e72862b19cfdbdfe4b6dddb65a55f68`.
Actual NDK/Bionic ARM64 and both translated hosts match23 canonical records.
Each host passes2921 focused checks and two real fatal subprocess cases.
All64 free-running races observed EAGAIN; separate enrolled-waiter groups and
handler cases exercise real wakes. The readonly epoch test is a labelled C++
protocol Trace under Runtime.Run; the actual NDK import-clear test is separate.
Earlier fixture failures remain preserved: invoking exclusive helpers without
an active execution, then colliding the TEST trace with an import marker.

The component does not qualify a game syscall, active collector roots at this
provider, general timed/shared/PI/requeue futexes, rendered output or gameplay.
