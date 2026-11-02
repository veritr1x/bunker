# Virtual ARM64 alternate signal stacks

`sigaltstack` now uses each live, native-thread-bound virtual thread's actual
configuration. A new thread starts disabled. Queries write the full zero-padded
24-byte Android ARM64 `stack_t` and compute `SS_ONSTACK` from the materialized SP
using the downward-stack interval `low < SP <= high`. Registration supports flags
0 and `SS_DISABLE`; valid but unported `SS_ONSTACK` input and `SS_AUTODISARM` stop
explicitly. Invalid modes return EINVAL; replacing a stack while on it returns
EPERM first, and an enabled size below the ARM64 NDK minimum 5120 returns ENOMEM
before mapping ownership lookup. Success preserves errno.

The import snapshots new input before any overlapping old output. Invalid new
input returns EFAULT without changing configuration. The configuration operation
precedes checking/copying old output, so an entirely inaccessible old output can
return EFAULT after a successful commit. A partly accessible old output is an
explicit unsupported boundary after commit: this does not claim Linux's partial
copy semantics. The caller must retain wire-buffer storage during the operation;
arbitrary concurrent native pointer retirement is outside this component gate.

Registration uses an unpinned writable mapping snapshot with full owner bounds
and generation. Queries neither resolve backing storage nor clear stale tuples.
Delivery requires a real active-use lease, compares the full owner and generation
again, and keeps that lease through handler execution, frame readback and saved
registration restoration. Windows uses `FileSystem::AcquireMappingUse`; the Linux
fixture physically owns mmap allocations and guards native munmap/mprotect with
its real pin counter. A missing lease, retired/reused generation, or nonwritable
mapping stops before frame writes. Merely installed metadata never pins a mapping.

The qualified `SignalDelivery` constructor takes `SignalHost` and its bound token.
SA_ONSTACK switches to the enabled alternate top only when interrupted outside
it; a nested handler remains below the current alternate SP even without
SA_ONSTACK. The frame saves the configured raw flags in `uc_stack`, separately
from query-time ONSTACK. The interrupted stack's actual bounds govern restoration.
The saved enabled mapping is pinned even for a handler on the normal stack, so a
handler's A-to-B registration change returns coherently to saved A. Unchanged
nested configuration is an internal no-op instead of an erroneous public setter
call on the alternate stack. Editing `uc_stack` in the frame, PC redirection,
AUTODISARM, asynchronous native signals and unqualified storage remain explicit
unsupported boundaries. Ordinary Pthreads stack attributes still describe the
normal stack.

The original Unity sequence at 0x7040edf4 queries, sees a disabled size zero,
mmaps 256 KiB and genuinely installs it. Cleanup at 0x7040eee8 forcibly changes the
saved flags to zero, attempts restoration, then unmaps its allocation regardless
of the result. For an initially disabled stack, the forced tuple `{0,0,0}` fails
ENOMEM and unmap leaves a stale registration. This behavior is preserved; a pure
query can still read that tuple, while later attempted delivery rejects its stale
owner. No artificial ART registration or automatic disable is supplied.

Game8 and game8b qualify only the original query. Their FileSystem rejects the
next valid mmap flags0x20122 because MAP_GROWSDOWN is unimplemented, so original
Unity takes its allocation-failure branch before installation. The focused
stack tests use real ordinary writable mappings and do not establish that
original growing-map allocation.

Game9 enables the separately qualified [Windows growth profile](growdown_memory.md).
Its original mmap at LR7040ee6c returns actual 256 KiB writable storage, and
sigaltstack at LR7040ee98 installs that same address with flags0/size262144 and
returns zero. This qualifies original installation. In-game downward-growth
faults, cleanup, signal delivery and collector use remain unqualified. See the
[natural startup record](game_bootstrap.md) for the frozen inputs and next boundary.

## Evidence and limits

Run `test_signal_altstack.py --out <new-directory>` in WSL with the repository's
Python tools environment. It archives accepted host 714daef, overlays and hashes
only the four provider files plus its six new fixture/runner files, compiles the
real NDK caller/handlers for both native hosts, and rechecks frozen sources after
execution. Windows tests exercise the accepted production FileSystem lease. The
controlled TEST imports trigger component delivery while a real NDK execution
state is materialized; they are not production signal polling or original game
callbacks. No collector records, scanning, suspension or collection is tested.

The independent ARM64 QEMU 8.2.2 reference records actual alternate/nested SPs,
on-stack EPERM, overlapping input/output, guards and normal-handler A-to-B-to-A
kernel return. Its complete normalized output is asserted. Three observed
QEMU-user results differ from the pinned Android contract: it accepts size 5119,
prevalidates inaccessible old output so no install
is committed, and writes computed ONSTACK=1 into nested `uc_stack`. The provider
instead uses the ARM64 NDK minimum 5120, commit-before-copyout and raw configured
flags=0. Those three cases are Android-source-backed model tests, not claims of
QEMU or executed Android-kernel parity.

Pinned primary evidence is in `work/sigaltstack-audit`: Android13-5.15
`kernel/signal.c` SHA256
`ff549a86100bcebbf358c68760c3ef6047e437a84a84baa704c2bc36c0664c11`
(`do_sigaltstack`, syscall copy ordering and `__save_altstack`), original Unity
disassembly and the ARM64 Bionic/NDK header. The independently reviewed ARM64
kernel signal implementation SHA256 is
`f31794a4688465d58af51c2d2c7abbac5f35a3745352adca908900cefeff6b33`.
Production game cohorts remain unpolled; their unsupported nonzero signal
delivery guard remains required. This change alone makes no stop-world or GC
readiness claim.

Accepted component candidate `work/signal-altstack4` freezes host
`714daeff64880209eb9de33b99a7164ea237557d`. Both Linux and Windows passed
193 focused checks, four expected named boundaries each, and two healthy NDK
object shards. The same frozen archive passed the existing signal/semaphore gate
(159 checks each), cooperative delivery gate (16 stop/restart cycles each;
305 Linux / 295 Windows checks on this run), and pure signal-frame gate
(3921 checks / 32 NDK cases each). `acceptance.json`,
`regression-acceptance.json` and the logs preserve these distinct results.
Earlier failed setup candidates 1–3 are preserved; no failed variant was replaced.
