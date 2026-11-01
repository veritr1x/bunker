# Native thread IDs

Unity reached `gettid` at return PC `0x704243f0` while reporting a captured
Java exception. `Pthreads` now supplies this import using the calling native
Windows thread's ID. Each thread record already caches its native ID; `GetTid`
checks it against `GetCurrentThreadId` and requires a positive Android-width
`pid_t` before returning. It fails explicitly if the identity or width is
invalid. Successful calls preserve guest errno and do not change guest memory.

The independent NDK header probe verifies `pid_t` and `gettid()` are four bytes.
[Bionic's Android 13 implementation](https://android.googlesource.com/platform/bionic/+/refs/tags/android-13.0.0_r1/libc/bionic/gettid.cpp)
likewise returns the cached calling-thread ID, with a syscall fallback when
needed. [Windows native IDs](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getcurrentthreadid)
are unique while their thread is alive and may be reused after termination.
The existing lifetime-unique opaque `pthread_self` tokens remain separate.
This adaptation does not implement Linux thread-group leader equality with
`getpid`, `/proc`, `tgkill`, or a scheduling/signal PID namespace.

On November 2, 2026, the full Windows pthread gate passes **78 checks**.
Actual translated NDK callers compare against independently observed Windows
IDs on the main thread and 12 simultaneous external native threads, with
32 repeated calls per external thread. Managed pthread workers also check
positive, stable, mutually distinct IDs. The existing contention, stacks/TLS,
destructors, explicit exit/detach, once and timeout gates still pass. The
fixture has 63 traces, no unsupported traces and no unresolved direct targets.

The changed fixture layout exposed a final direct `pthread_exit` call falling
into zero linker padding. Its once-exit callback now uses a real typed volatile
function pointer, yielding a supported terminal tail branch under the pinned
NDK. The expected `0x77` thread result still detects an erroneous return.
No unsupported instruction allowance or compiler/runtime workaround was added.

Evidence: ignored `work/pthread-gettid-{prepare,native}.log` and
`work/windows-pthreads-gettid/`. Run `prepare_pthreads.py` and
`test_pthreads.ps1` with that separate output directory to reproduce.
