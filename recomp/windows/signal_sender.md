# Explicit pthread_kill sender identity

`SignalHost::ThreadKill` adds the optional bounded Android AArch64 SI_TKILL profile. An explicit snapshot supplies positive signed32 process ID and uint32 real UID; the callback runs outside SignalHost locks and native errno/fenv/LastError are restored around it. Signal0, invalid/dead/unsupported targets and ignored dispositions never invoke it. The final Queue rechecks lifetime/disposition and preserves first pending standard-signal Info. Existing generic Queue and empty-sender Install retain their original signo-only profile.

No Windows SID-to-UID mapping or default Android UID is inferred. Game wiring must separately choose a consistent guest-process identity source. Current LibC ProcessId is real GetCurrentProcessId/getpid; getuid remains outside production LibC. The focused fixture deliberately declares one virtual UID source used by both its getuid import and sender snapshot, including uint32 edge cases. It is not a native Windows Android UID claim.

Primary Android13 Bionic pthread_kill/tgkill, siginfo headers and Linux5.15 do_tkill are pinned under ignored work/signal-sender-audit. NDK27.2.12479018 proves size128/alignment8 and offsets signo0/errno4/code8/pid16/uid20, with SI_TKILL=-6. No native-host siginfo cast is used.

`test_signal_sender.py` freezes a committed support archive plus exactly eight owned files. The same actual NDK core object links into a static Bionic ARM64 reference and the lifted shared fixture. Static reference TLS uses the real ELF TLS model and explicit64-byte alignment required by ARM64 Bionic. QEMU reference records its actual process PID/UID; translated Windows/Linux use actual LibC PID plus explicit virtual test UID. Only those verified process-dependent bytes are normalized; all128 Info bytes are checked, including unused zeros.

Focused tests execute actual NDK direct/volatile-indirect pthread_kill calls and SA_SIGINFO handlers through real same-worker SignalDelivery/owned guest-stack frames; preserve ABI, error state and bounds; test coalescing, identity failures, UID edges and real concurrent SignalHost target retirement. Three import-boundary negatives must abort within the actual installed production fence. Existing signal/semaphore and combined signal-delivery gates qualify backward compatibility. These gates do not qualify production collector registration, game delivery, GC roots or a playable frame.

Results and exact hashes will be recorded in a fresh ignored candidate; failed prechecks/candidates remain preserved. No natural game execution is performed by this component workflow.

The accepted `work/signal-sender5/acceptance.json` SHA256 is
`86d2f5d1b9292d1e089b94de3fd32071f6d78ebfa6104aad9c497b2e2286d410`.
Focused Linux/Windows runs pass3207/3209 checks, respectively. The unchanged
signal/semaphore gate passes159 checks and combined frame delivery passes305
checks/16 cycles on each host. Independent review reconstructs all128 bytes
for six reference/translated records and revalidates every executed source,
tool, reused input and evidence file. The static Bionic reference input proof
SHA256 is `248740cd64958e38334e05e4d99e8a90fbbc75c4b4002b09dd3a705fc385eb51`,
recorded by `work/signal-sender-held.json`. Earlier setup/fixture failures remain
preserved; production game activation remains pending.
