# Relative timed private futex waits

The extension handles nonnull timeouts for syscall98/FUTEX_WAIT_PRIVATE. It
retains the existing seven-register ABI, marker, WAKE and untimed behavior.
Runtime, SignalHost, SignalSleeps, Pthreads and the affinity/priority providers
are unchanged. The game admits no new signals or provider roots.

The provider copies exactly16 unaligned bytes once: signed64 seconds and
nanoseconds. Copy, validation and deadline construction precede key validation,
matching the pinned Android13 kernel. Bad/partial copies return EFAULT14;
negative seconds or nanoseconds outside0..999999999 return EINVAL22. A valid
zero duration still checks the word first: mismatch returns EAGAIN11, while
an expired matching wait can return ETIMEDOUT110. The existing explicit
untagged lower48 software address profile also covers the timeout span.

One fixed active-monotonic deadline uses saturating signed ktime arithmetic.
Windows resolves the actual KernelBase QueryUnbiasedInterruptTimePrecise;
Linux uses CLOCK_MONOTONIC. Native wait slices are at most one second, without
changing the deadline. Long valid durations therefore cannot turn into the
Windows DWORD INFINITE sentinel. The original helper can request UINT32_MAX
milliseconds, about49.7 days; its actual Game28 duration was unobserved.

Wake selection and timeout/interrupt withdrawal share the queue mutex. The
completion cause is latched before a real admitted handler: selected wake
wins0, otherwise expiration wins110, otherwise caught interruption wins4.
Handler duration cannot reinterpret a selected EINTR as timeout. Timed caught
handlers return EINTR even with SA_RESTART; untimed retry behavior remains
unchanged. No signal is consumed on rejected admission. No timeout leaves a
ticket that can steal a later wake, and no wake credit or guest word is invented.

Optional observations report the actual immutable timespec/deadline and
ordinary result, with validity flags, outside queue/memory locks. Native errno,
LastError and floating-point environment are preserved. Exceptions do not
promise a Return observation. Callbacks are replaced only while calls are
quiescent; captured resources retire outside the queue lock.

Qualification2 passes38 canonical records matching actual ARM64/Bionic on both
hosts: Linux4378 and Windows4353 total checks, including the unchanged23-record/
2921-check baseline and old rejection cases. Both restart flags retain EINTR
through100ms handler overruns. Sixteen free-running timed races all chose
timeout/wake0 on each platform; separate deterministic finite and49.7-day waits
prove real selected wake1/success0. Actual49.7-day expiration and suspend/resume
are not tested. Ten NDK heads/two caller COFFs are reused without new lifting.

The ARM64 reference execution is reused from qualification1 with unchanged
native inputs. Qualification2 reruns Linux/Windows after correcting the labelled
C++ protocol trace's initial PC materialization; that test is not an original
NDK instruction claim. The failed first attempt remains preserved. Acceptance
`work/futex-timed-fixture1/qualification2/acceptance.json` SHA256 is
`bd680027ad0578d98b491001930e2afd1a1786b63faf3a90f477352e8a517c64`;
held package `work/signal-futex-timed-held2.json` SHA256 is
`fb7891a20d92fb914978f0fe50d458f7c17651bce7858d38f21914f0c9b434e2`.

An original game execution of this timed provider remains pending. No new
blocking signal-root phase, general collector safety or rendered frame is claimed.
