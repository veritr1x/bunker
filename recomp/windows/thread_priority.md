# Owned native thread priority

The explicit UnityNormalClass profile translates Android nice10/1/0/-2 to
Windows relative priorities LOWEST/BELOW_NORMAL/NORMAL/ABOVE_NORMAL. It requires
the actual process class to be NORMAL and never changes that class or boosts.
This is a finite translation, not Linux CFS, permission or inheritance parity.
Other nice values, relative levels, process classes and group/user namespaces
remain named unsupported boundaries.

Both getpriority(PRIO_PROCESS,tid) and Android13 Process.setThreadPriority(II)V
use the same service. Each operation acquires a duplicated native handle from
the actual live Pthreads catalog under its registry lock, then queries/sets and
checks native readback outside that lock. It never reopens a numeric TID with
OpenThread. A retained handle keeps the acquired object across exit, not a
promise of continued liveness. Known retired/negative IDs return ESRCH; unknown
unowned IDs are unsupported. Native API failures remain visible.

Successful queries preserve guest errno. The Java equal-priority shortcut also
preserves errno, while a real changed success clears it, matching Android's
framework setter. Failure maps Android errno to the actual declared Java
exception classes, including SecurityException. Native errno, LastError and
floating-point environment are preserved separately from guest errno.

The Process method remains native/static metadata. Its explicit platform body
uses existing validated JNI argument and unlocked callback frames, with no fake
translated native address. Generic nonnative binders keep their old guards.
RegisterNatives and UnregisterNatives reject platform ownership conflicts before
applying any changes. Those rejection guards are a bounded host ownership policy,
not full Android native-unregistration compatibility. Other Process APIs and
class initialization are not implemented. Optional diagnostics run outside JNI,
registry and service locks and cannot supply operation results.

Qualification2 has248 Windows focused checks,14 lifted heads/two objects and
13 static Bionic ARM64 records/32 checks. It exercises direct/function-pointer
and upper-register transport, direct/V/A JNI, native set/readback, real worker
retirement, environment preservation, ownership transactionality and throwable
roundtrips. Three intended failures retain exact native statusC0000409. Existing
JNI36 checks pass on Windows/Linux; Windows Pthreads78 and signal-lifecycle270
plus three intended failures pass. Acceptance is
`work/priority-fixture1/qualification2/acceptance.json`, SHA256
`5dc51794e8d368d55f718734741136375741f88521eee9d7eec14d131d595038`.
Qualification1 remains preserved and unaccepted: it lacked the SecurityException
declaration and its controller expected the wrong native abort status. No game
priority call/return, initialization result or rendered frame is claimed here.
