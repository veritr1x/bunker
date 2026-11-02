# Opt-in native Windows downward-growing mappings

`FileSystem::EnableGrowdownMappings()` enables one explicit Windows compatibility
profile. The default remains disabled with the existing named MAP_GROWSDOWN
boundary. It does not ignore that flag or silently precommit the extra capacity.

The enabled mmap profile requires address0, private anonymous RW storage,
offset0, and MAP_GROWSDOWN with optional MAP_STACK. Returned P is the initial
accessible low address, and N is rounded to a page. The usable owner is fixed at
`[P-8MiB,P+round(N))`. A separate1MiB lower gap and4KiB upper guard stay reserved.
Only the initial requested pages are committed. These are chosen host limits,
not inferred Android device limits or an implementation of Linux RLIMIT_STACK.
There are process-wide limits of128 active owners and4096 lifetime controls.
Retired controls are never recycled into a new generation.

Actual read/write access violations within the available lower capacity commit
the needed contiguous prefix and retry the real faulting instruction. Every
committed prefix has the owner's current native protection. The handler rejects
execution faults, unowned/retired storage, the permanent guards and unauthorized
access to protected pages. It does not change a guest return value or skip a
faulting translated instruction. Its native-TID recursion guard and owner/read
state use preallocated lock-free atomics, without C++ thread_local first use.
The separately preserved MinGW scalar-TLS probe demonstrates why an emutls-based
guard would have allocator/locking paths.

MappingRegion checks actual requested committed pages and protection but returns
the fixed full usable owner bounds and generation. An uncommitted/mixed requested
span is not reported readable/writable. AcquireMappingUse pins the complete
physical reservation, including future growth. It blocks unmap/protection
mutation while allowing a legitimate fault to extend the pinned owner.
Full-current-span mprotect supports0/1/2/3 (native write permission implies read);
read-only growth remains physically read-only. Executable and partial protection
requests are named boundaries. A successful extension does not invalidate a
reservation on unchanged existing guest bytes.

Munmap accepts only the complete current committed span, from the lowest touched
page through the original high address. Original P,N after expansion is a partial
unmap and must not release the whole owner. A full unmap closes new fault-reader
entry, refuses an already active native fault reader, invalidates tracked guest
memory, and releases the complete native reservation. Destruction refuses active
mapping leases/readers before retirement. An ordinary MAP_FIXED_NOREPLACE request
over an actual committed overlap returns genuine EEXIST. A Windows reserved-only
growth window is a distinct named unsupported collision, rather than an invented
Linux occupied VMA result. Placement/publication and ordinary NOREPLACE
classification/allocation share normal-path process serialization; the fault
handler never acquires that lock.

Callers must quiesce all external/native/guest workers and callbacks before
teardown or helper/module retirement. The handler-entry count is diagnostic; it
is not a general concurrent shutdown/drain protocol. Active-owner count zero alone
does not establish quiescence. The helper remains mapped in the standalone
executable through process exit. The component does not qualify arbitrary DLL
unload or forced termination during a callback.

## Qualification and limits

`test_growdown_memory.py --out <fresh-directory>` freezes committed74798fb plus
exactly four production files and its three fixture/runner files. No live harness,
Context or root build scripts are captured. The NDK fixture materializes real
loads, stores and LDAXR/STLXR in the existing Runtime. First touches therefore
exercise actual Windows faults, including while the Runtime memory lock is held.
Concurrent native and translated stores target distinct words in overlapping
prefixes. Tests inspect native reservation/commit/protection state, zero bytes,
old canaries, stable generations, physical leases, retirement/address reuse,
native LastError preservation and exact cleanup. VirtualQuery is walked forward
from the known low bound; querying P alone does not locate an earlier prefix.

Fatal hardware cases execute in fresh native Windows subprocesses and require
full STATUS_ACCESS_VIOLATION `0xc0000005`: lower/upper guards, beyond capacity,
write into a grown read-only page, prohibited new write growth under RO,
NOACCESS read, foreign reservation, same-address retired ownership, and native
instruction fetch from non-executable storage. Native PowerShell captures the
complete signed Windows status because WSL interop exposes only its low byte.
Named unsupported calls stop at the real import boundary before a C++ exception
can unwind through lifted nounwind intrinsics. Resource budgets run in separate
fresh processes and consume real native reservations/retirements.

`FileSystem::Install` applies one fatal exception fence to all30 unchanged bridge
expressions: standard or unknown host exceptions print the actual API name,
flush diagnostics and abort before translated continuation. The direct C++ API
still reports its explicit unsupported capabilities by exception. A targeted
`--production-from <qualified-candidate>` run uses actual production Install
directly, without the fixture's forwarding fence. It checks normal NDK
mmap/mprotect/munmap/errno and six production named boundaries, requiring native
abort status `0xc0000409`. Reuse of earlier native/helper/budget/regression results
requires exact comparison of all pre-Install hot paths (apart from a utility
include), reverse equality of all30 registrations, unchanged other production
files/helper object, and unchanged existing fixture bodies. Reused and newly
executed results are recorded separately.

The independent primitive gate in `work/windows-growdown-primitives1` qualifies
overlapping immutable-RW MEM_COMMIT behavior on the actual Windows build. The
handler-code inspection in `work/growdown-handler-proof1` identifies only
GetCurrentThreadId/GetLastError/SetLastError/VirtualAlloc/VirtualQuery imports and
no allocator, emutls, mutex, runtime, static-initializer or guest calls. Its helper
object SHA256 `890d49dfd06ddfa8f5922e36b849ac7c75af7d41185389e6b6ca8583a7cc08d7`
matches the executed component object. Those are separate native/static proofs.

The gate does not induce native commit failure, nested faults inside the handler,
recursion-table exhaustion, or the active-fault-reader-close rejection branch.
Those paths are source-reviewed, not claimed as executed. No test-only handler
hook or synthesized exception record is added. Existing MappingUse and FS116
regressions use their frozen actual test sources, fresh fixture/data output and
verified immutable old inputs. This feature does not implement collector thread
records, asynchronous signals, polling, suspension, scans, Java attachment, a
rendered frame or GC readiness.

Earlier candidates are preserved. Candidate1 exposed a test's incorrect backward
VirtualQuery inference; candidate2 exposed WSL status truncation. Candidate3's
positive/native/budget evidence is preserved, but its named NDK negative calls
were not accepted because the fixture had permitted C++ diagnostic unwinding.
The later explicit import fence qualifies those boundaries without that reliance.

Final qualification keeps the results separate. `work/growdown-memory4` passes
535 positive checks, nine actual hardware AV cases, five fixture-fenced named
boundaries, active-budget387 and lifetime-budget16386 checks. Its existing
MappingUse regression passes488 dynamic checks across128 real races (82 acquired,
46 mutation wins), plus FS116 with fresh data. Historical MappingUse negative
logs remain preserved; they are not the final production-abort qualification.

`work/growdown-memory5` runs only the new actual-production transport gate:
25 normal NDK API/errno checks and six full `0xc0000409` abort boundaries, with
nine healthy strict trace heads. It proves the mechanical Install-only delta
and reuses the unchanged candidate4 helper/native/ownership/budget/regression
qualification explicitly. It does not relabel those535 checks as newly executed
against the final transport fixture. The helper object matches the independent
code inspection byte for byte. This document was completed after both runs;
all earlier variants remain intact. No natural game frame was run by this gate.
