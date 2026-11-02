# Opt-in original finalizer signal profile

This profile is available only in a native build explicitly compiled with
`game_bootstrap_build.ps1 -EnableCollectorDelivery` against the fully accepted
cooperative cohort. The build records capability
`original-finalizer-single-condwait-v1`. Runtime opt-in is separately
`frame-muted-gc`, which supplies `--mute-audio --collector-delivery`. All other
profiles retain their existing nonzero-signal guard, including when the binary
has this capability. An unpolled build cannot compile the capability. The
ordinary muted profile still omits the hardware-volume observer and requests
the genuine original master mute after resume; no endpoint or playback claim
is added.

This is a bounded admission design, not general production GC correctness. It
does not implement arbitrary provider/parent-State roots, general signal
delivery, nonlocal exits from a handler, managed retention/reclamation tests,
or an Android device UID. The explicitly configured virtual Android real UID
is 10000 and the sender PID is the checked actual process ID. No Windows SID or
original device identity is inferred. Future getuid support must use this same
declared process identity rather than a conflicting default.

The original ELF is pinned to SHA256
`ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522`
at base0x80000000. The before-Create witness requires creatorLR82556a64,
entry82556a94, wrapper82557c80 and initialized payload[Thread*,825c3ed0,0].
Only its real synchronous prepare hook assigns the finalizer role to the
actual new lifetime-unique token. Neither token3 nor a name is a role selector.
Payload addresses are not retained as permanent roots.

WorkerSignalLifecycle supplies real creator-time masks, fresh pending/disabled
alternate-stack policy and actual child binding. Heap-owned per-worker poll
bindings remain live through TLS and are explicitly destroyed by that child
before adapter retirement. A ContextUse covers each active frame. Active-frame
pthread_exit/nonlocal transfer is unsupported; no destructor invents cleanup
or original GC deregistration. Original code owns GC records and unregister.
All six supported setjmp/longjmp-family imports check the owner-local active
collector depth before capture or transfer dispatch. This is explicit rejection,
not merely an assumption that the normal handler callgraph contains no jump.

Every compiler entry/backedge poll defers by default. The only admitted poll
site is the controlled native CondWait checkpoint, labelled with the actual
import PC and reserved ordinalUINT64_MAX. It is not described as a compiler
site. Outside its lock-free read-only Admission decision, the checkpoint holds
native errno/fenv and same-worker ContextUse scopes. Admission itself receives
borrowed const State/chain metadata and does not take locks or invoke providers.

Wait shape is checked before publication: actual entered finalizer, native
identity, activeState==CurrentExecutionState, one Runtime frame, no opaque
enclosing phase, untimed X2/deadline null, original LR825505d8, actual import
PC7ffc60000020, original event holder879a7a40, condition=event+2c and
mutex=event+4, registered normal SP/TLS and9504 bytes of known-path capacity.
Alternate stack must remain disabled. Both ConditionReleased and
MutexReacquire are actual lock-free, guest-mutex-unowned transport phases.
The original condition predicate/deadline/reacquisition remain unchanged.

Basic wait checkpoints do not walk original GC buckets. A nonzero send first
proves the original caller (30/LR825b2d1c/X26 or24/LR825b2f74/X27), singleton
nonopaque sender State, target role, original epoch/world/registry-lock
consistency, initialized globals, real record membership/token/stack high,
actual30/24 dispositions and original thunk/table slots. Signal0 remains an
ordinary probe. The original registry lock is never acquired or modified by
the host. A lock byte1 alone is not an owner certificate.

Only a new genuinely sent epoch with no prior target stop entry permits the
target's full registry relookup. Before its first original acknowledgment the
audited coordinator must still hold that cycle's registry lock. A late standard
30 after resume is left pending until a later genuine cycle certifies a new
epoch; the profile does not promise general asynchronous-delivery latency.
No bucket walk is done merely because a transport hint exists. No slow-hook
completion progress means the checkpoint returns with the request pending.
Once no model signal is pending, the separately qualified checkpoint can drain
stale transport epochs; this is not an original GC acknowledgment.
If a late request races the stale-hint check, Pump throws a private defer tag
before any bucket walk or signal consumption. Only the reserved direct C++
provider call catches that tag, before returning to lifted code; the poll epoch
is not completed. Ordinary compiler sites never admit this handler. This is
not C++ exception unwinding through guest LLVM or a nonlocal signal return.

Outer selection is `DispatchOneAllowed(..., Bit(30), ...)`, intersected under
SignalHost's own mutex before consumption. A lower-number pending24 remains
untouched. No shadow signal queue, mask toggle or peek-then-dispatch selection
is used. The original stop thunk825beb3c tailcalls825b2af4; table879a7788 must
match, actionflags10000004 and original normalized mask must match. The genuine
registered RET-only head825aada0 is a checked normal-return boundary, never a
manual guest call or replacement handler.
An allowed30 selection finding only pending24 may consume its transport hint,
but leaves the actual model24 intact; a genuine subsequent30 send notifies the
channel again. It does not invoke the24 handler at an outer wait or fabricate
an acknowledgment. The next original stop's actual sigsuspend is its qualified
delivery phase. Late pending exit ordering remains an explicit bounded edge.

The original handler publishes FP and posts the real semaphore87cb1e68. Before
forwarding each original post, the wrapper checks its actual callsite, actual
published FP and every saved GPR/Q byte physically above that FP in the real
owned guest stack. No host sem_post, epoch write, record patch or ack drain is
introduced. Posts precede original E/E|1 stores; diagnostics deliberately do
not claim a post proves the later store already occurred. Return checks observe
the actual eventual epoch and original handler return.

Before the actual sigsuspend provider may consume anything, its original
LR825b2c24/mask879a6b18, exact outer stop scope, two Runtime States, SP=B-60,
FP=B-30, real published record FP/E and temporary mask are checked. That mask
keeps30 blocked and permits24. Only the matching original restart leaf is
qualified; general frames>1 remain unsupported. An early/old24 can return while
worldStopped is still1, and the original body itself waits again. A later
genuine24 after worldStopped0 releases the original wait. No transport wake
substitutes for that signal. Other signal-consuming wait phases are rejected
before their providers run.

The runner distinguishes pre-call send witnesses, actual pthread_kill returns,
verified physical frames, original sem_post returns and original handler
returns. None alone establishes collector retention, initialization return,
rendering or a playable game. Default profile history remains in the existing
bootstrap documents. Static/source gates compile both capability settings and
the missing-cohort rejection, pin the original byte/audit evidence and parse
the builder/runner. They execute no game or original collector code. An actual
new profile run requires the separate reviewed cohort/prerequisite seal and
explicit run authorization.
