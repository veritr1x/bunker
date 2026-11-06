# Native Windows recompilation: status and remaining work

The target is a standalone Windows x86_64 executable running the original
game's translated native libraries. Work is on `recomp-x86_64`; it is not yet
part of the normal Bunker release. The first original game frame is now verified.

Run25 completes 180 original render returns, 2,288 draws and 177 successful
presentations. Its untouched later 1280x720 capture shows SQUARE ENIX x applibot
logos; the game advances beyond Notice naturally. The first-frame and later
snapshot witnesses pass. The current build retains
4,661 guest objects and 595,556 trace heads. See
[the authoritative frame results](windows/first_frame.md) for exact pins.

The worker-retirement shutdown failure is fixed in actual original workers.
Finishing now stops at unresolved native entry `0x70ddd5a0`, LR `0x70ddd54c`.
It is case0 of an original bounded eight-case switch in existing object450;
all eight case entries need dispatch coverage. Immediate remaining work is
those guarded entries, continued startup beyond the publisher
splash, input and real client/backend behavior,
and a usable standalone Windows bundle. Audio remains explicitly muted while
the HDMI endpoint is unavailable. A visible frame does not establish gameplay.

The execution narrative below preserves earlier checkpoints; its historical
object counts and failure boundaries are superseded by the linked run25 result.

The latest execution boundary and build evidence are in
[the first-frame status](windows/first_frame.md). The exception-transfer
correction, full fresh guest rebuild and original Windows startup have run.
The current exploratory executable retains 4,653 guest objects and 595,408
trace heads, including the qualified numeric min/max repair and four original
computed-table entries. With Windows identity and calendar APIs added,
clock-resolution support passes 66 translated NDK calls and an actual static
Bionic reference. The JNI byte-array family passes focused translated NDK
callers on Windows and Linux. The consistent full host/bootstrap rebuild
and original startup now include real byte-array/charset String construction
and Java native-library loading. Unity's completed JNI_OnLoad is adopted
without replay. The actual FirebaseCppApp-9_6_0 request fails because that
APK library has not been translated. The manual-proxy property adapter passes
789 Windows checks and 151 translated NDK calls. A fresh consistent bootstrap
and all-44-source host build includes it and the corrected JNI version policy.
Scheduler yield support passes 436 Windows checks and 48 translated NDK calls
and is included in the latest full host build. The original game now completes
its HTTPS proxy-property query and the recorded URL scanner calls. The scanner
and six-GP bridge pass 387 Windows checks and 51 exact output/status/errno
comparisons against actual Bionic. The latest consistent bootstrap/all-host
build included the qualified IPv4/IPv6 converter after the user's Windows
restart restored available RAM to about 44 GiB. The converter passes 1,344
Windows checks and 190 exact Bionic comparison records. Original startup now
passes that boundary. Genuine name/service resolution, Android/Windows
structure and flag/error conversion, and result ownership/freeing pass 2,100 checks and
304 actual NDK calls across getaddrinfo/freeaddrinfo/gai_strerror. The 272
cross-Bionic records retain complete chains/status/canonical/error strings and
failure/free errno; only unspecified success errno is normalized, with raw
observations preserved. Its full host/bootstrap build and original execution
now pass the previous getaddrinfo boundary and stop at missing libunity.so
`socket`, LR `70b4a1b8`, AF_INET=2/SOCK_STREAM=1 (protocol unlogged).
The connected-client socket/readiness/shared-descriptor cohort now passes
3,913 focused checks across 29 APIs and 445 actual NDK entries; prior file
regressions also pass. Its separate collector phase passes actual physical
root/stop/restart tests and the legacy native collector regressions. Bootstrap
integration and the actual-disposition SIGPIPE policy now pass their focused
checks, with an exact combined 12-source proof. Its full bootstrap/all-45-host
build and original execution now reach socket/options/connect/poll/send/recv
on an actual prepared Unity-worker lifetime. Three original renders return,
all with zero draws. The TLS path reports missing
`javax/net/ssl/TrustManagerFactory` and Curl51/not-trusted; the fatal boundary
is unresolved original Unity target `70b4c100`, LR `70b47730`. Original-entry
recovery and genuine Windows-backed JCA trust support are the next work.
No frame is established.
Two original renders return,
but there is still no successful swap or captured game image. Windows
auto-detection remains unresolved and is not a proven direct route.
Initialization, rendering, gameplay,
client/backend integration and standalone packaging remain unfinished.
The historical network inventory identifies 32 missing imports plus four file
APIs needing socket-aware ownership/dispatch. Three inventory names are now
implemented (inet_pton/getaddrinfo/freeaddrinfo); socket transport is qualified
and its client API path now executes in the original game. Complete TLS and
client/backend integration remain unverified. The prepared backend has not been
connected to the real client. Execution notes below retain earlier checkpoints.

All recomp source work is in the `recomp-x86_64` worktree at
`C:/Users/user/.codex/worktrees/bunker-recomp-native/bunker`.
Its `recomp/work` junction retains the existing artifacts at
`C:/GitRepos/bunker/recomp/work`; the previous worktree is clean and detached.
Migration receipt: `work/worktree-migration-20261104-1/acceptance.json`.

The matching pre-inliner compiler hook and pass are checkpointed locally in
the Remill fork, whose latest local checkpoint is
`df627afa707566cfdf932c2225345e6241802257` including scalar numeric min/max.
The CMake executable target builds against
the existing qualified dependency archives; default and guarded Leaf/Exercise
IR match the qualified tool byte for byte. A fresh dependency build has not
been run. The running candidate continues using its frozen compiler binary.

The separate Game29 debugger diagnostic identifies a mistranslated ARM `EXT`
in Unity's pointer sort. The corrected instruction passes 12,352 ARM/Bionic,
Linux and Windows records per host; the complete original sort's insertion
paths pass 140 differential cases, including the exact full 128-function Windows
object. Only the sort function changes. A v3 cohort preserves the existing
prefetch repair and permits one additional shard 78 replacement. Game30's
constructor/JNI, initJni and surface controls pass; its collector-profile
startup stops at unresolved target `0x70b5b648`, with no native exception
record. The target is one of five valid original formatter jump-table
destinations missing from the catalog. The next checkpoint is qualified
additive recovery of those five entries, preserving the current guest objects.
There is still no returned frame or completed initialization result.
See [the EXT/sort evidence](windows/unity_ext_sort.md).

Game29 passes constructor/JNI, initJni and surface lifecycle profiles. Both
muted frame profiles return from original nativeResume and master mute without
creating a hardware-volume observer. Startup reads and saves PlayerPrefs,
copies all24 Managed files exactly, parses buildDate, publishes unity.ver and
enters public IL2CPP initialization. Standard muted startup still rejects
nonzero signal30 at LR0x825b2d1c, preserving the default guard.

Game22, Game23, Game25, Game26, Game27, Game28 and Game29 execute their first original stop/restart cycle in the
explicit `frame-muted-gc` profile. The captured finalizer0x825c3ed0 enters the
exact untimed CondWait at LR0x825505d8. Original signals30/24 both return success from pthread_kill;
the real stop/restart handlers execute, make both original semaphore posts,
and return with record epoch4→5. Actual31 GPR/32 Q-register bytes are checked
in the real interrupted stack frame above the original published FP before
both posts. The phase-aware mask fix validates saved0x80000000 against the
actual installed action mask0xfffffffffffbbed9; no host mask rewrite is used.
This proves one bounded handler cycle, not general collector safety, managed
retention/reclamation, completed initialization or a rendered frame.

Game23 adds the qualified native process-image `readlink` and advances beyond
the previous boundary at LR0x82554214. The actual run does not log returned
pathname bytes. It now reaches Unity's `dladdr` at LR0x70432a8c, querying the
raw `dlsym("end")` value0x7cb1e78. The natural static call graph places this
helper after public `il2cpp_init` returns; its returned value and success are
not observed, and nativeRender still has not returned.

Game24 adds qualified real ELF metadata for `dladdr` and Android's absolute-symbol
rules. Both raw end0x7cb1e78 and Bionic-biased end0x87cb1e78 are outside logical
PT_LOAD ranges; the latter is the exclusive segment endpoint. A rounded
reservation must not manufacture ownership. Android's symbol resolver also
changes two real IL2CPP GLOB_DAT entries (`end` and `__stop_il2cpp`), so the
explicit Bionic loader profile and public dlsym policy are qualified together.
The generic loader and explicitly declared export maps retain their original
behavior. The new native build runs the original startup, but this attempt
stops earlier at a newly observed timing import: `usleep(3000)`,
LR0x825b394c. The original E4 signal30 send returns0 and its target's saved
and installed masks pass validation. A concurrent physical-frame log line is
incomplete; no complete frame check, semaphore post, restart24 or handler
return is recorded in this attempt. It does not reach dladdr. Timing and
scheduling can expose an earlier missing import; Game23's completed bounded
cycle remains separate evidence. The new interruptible delay passes16 actual
Bionic/translated call records,176 focused checks per host and the existing
default/allowed signal regressions. Its Windows clock uses the actual precise
KernelBase API. The game adapter admits no signals at the timed-delay boundary
and leaves the exact finalizer-wait profile intact. Game25 completes its E4
handshake without entering that retry-delay path; no original game usleep
call/return is observed.

Game25 now observes original dlsym("end") returning87cb1e78 and dladdr returning0
at LR0x70432a8c, consistent with the exclusive PT_LOAD endpoint. The next fatal
import is Unity `syscall`, LR0x702ad510, with X0=98 and a dynamic address in X1.
The original caller statically supplies FUTEX_WAIT_PRIVATE/op0x80, expected
word in W3 and null timeout. W3, the current syscall thread/token and its
application role are not logged; nearby worker lines are interleavable.
A private futex wait/wake provider now passes23 matching Bionic/Linux/Windows
records and2921 checks per translated host. It uses atomic comparison/enrollment,
actual wake counts and a fault-safe readonly Runtime memory helper. Number/op/
value decoding follows the kernel's low32 semantics. The game adapter admits
zero signals and captures actual registers/thread identity plus the owned
saved caller for this exact frame. Game26 executes that provider from worker4,
native TID1197904, with expected word0, null timeout and saved caller702f161c.
No futex return, wake or enrollment outcome is logged before a different
thread's fatal import, so blocking success is not established. The completed
E4 handshake and actual dladdr return0 remain observed in this attempt.

The next Game26 fatal import is Unity getpriority(PRIO_PROCESS,1197904),
LR70438a80. JNI lookup also leaves a NoClassDefFoundError for android/os/Process.
Original code calls static Process.setThreadPriority(II)V and then always
queries that same native TID; the query is not a fallback for missing Java.
An owned-thread priority service and the real Android method/exception contract
now pass248 Windows checks and13 actual ARM64/Bionic reference records. Existing
JNI tests pass on both hosts, plus Windows thread and signal-lifecycle regressions.
The bootstrap exception catalog includes SecurityException as a RuntimeException
subclass; a real Java throwable roundtrip is tested without simulating OS denial.
Windows uses an explicit four-level translation
under NORMAL_PRIORITY_CLASS, with real native set/query/readback; Linux nice
scheduling equivalence is not claimed. Game27 observes the original Java setter
request nice0/return error0 and native getpriority return0/errno0 for worker4,
TID1321820, from caller TID1322936. The diagnostics do not reveal the setter's
before-query value or prove a particular branch/native priority mutation.

Startup then reaches syscall122, sched_setaffinity, at LR70438a10, targeting
the same worker with length4 and a pointer to the original owned stack. No mask
bytes are read or affinity operation/return observed in this attempt. Original
code can supply a dynamic mask or -1, and maps zero to all32 bits; the log does
not distinguish those paths. An owned-thread Windows affinity adapter now
passes158 checks/32 records, with22 shared cases matching native Linux four-byte
kernel calls. ARM64/QEMU rejects length4 before copying despite the real Android
kernel accepting it; its records and separate length8 controls are explicitly
separated from that comparison. Game28 observes17 actual native affinity calls:
requestedFFFFFFFF, process/system/effectiveFFFF and native previous/readbackFFFF,
with result0/errno0. The operation is real, though the effective mask was already
set to those16 CPUs. Seventeen untimed futex entries still have no observed
return/wake. More workers start; the next fatal boundary is a timed private
FUTEX_WAIT at LR708f2f14 from token21/native TID1344644, expected0, with a nonnull
timespec pointer at its actual SP. Timeout bytes/duration and worker role are
not observed. Static code converts a uint32 millisecond argument, including a
possible49.7-day interval; the particular argument remains unknown.

The new timed provider passes38 matching ARM64/Linux/Windows records, the
existing23 untimed records/2921 checks per host, and handler-overrun EINTR cases.
It uses real fixed deadlines and queue withdrawal, with no new signal/root
admission. Game29 copies two actual16-byte snapshots, both4294967 seconds and
295000000 nanoseconds, with valid fixed deadlines. Neither logs a timed result;
no wait enrollment, blocking or completion is established. Startup reaches19
real affinity operations before an unhandled native access violation. The
original log records only native instruction address7ff6ddc600db, without its
loaded ASLR base, accessed address, thread/register context or guest PC. An
exact-executable debugger diagnostic with fresh data is being prepared; no
cause or fix is inferred from the preceding log line. A returned public
initialization value, nativeRender return and rendered image remain unobserved.

The process-image query returns the actual native executable with forward
slashes, not an APK/shared-library substitute. Its consumers derive
DLL/config/Data/SymbolMap locations. The existing virtual filesystem does not
yet reopen arbitrary native Windows paths. Short Unicode-path execution is
qualified; the native launcher rejected the longer path before execution, so
the image-query growth branch remains unexecuted.

The selected3575 objects cover456684 trace entries,122089 cycle cuts and79436
closed direct targets, with1439 unsupported heads. Game21 replaced only
IL2CPP local shard01083/global1553 for the qualified prefetch fix; Game22,
Game23, Game24, Game25, Game26, Game27 and Game28 retain every guest object/header and change host providers only.
Older cohorts, failed attempts and original source/semantics remain preserved.

Component prerequisites remain separately qualified: cooperative polling
27349 checks/260 pauses per host; native condition transport397 checks;
worker signal-lifecycle270 checks; sender metadata3207/3209 checks against
static Bionic ARM64; and mask-phase133 checks per host. The game profile uses
explicit virtual Android UID10000 and the real process PID. General parent or
native-only root publication, other blocking pthread routes, repeated-cycle
stress and managed retention/reclamation still require work.

Four scalar FRINTP/M forms pass65536 matching records per ARM64/Linux/Windows
host and4118 decoder checks. Six UADDW/UADDW2 forms pass12544 records per host
and782 decoder checks. Eight unsigned CMHI forms pass16640 matching full-state
records per host and1038 decoder checks. Their source/fixtures are checkpointed;
these new toolchains are not selected in the game cohort. A new isolated lift
of head8261b5ac now clears its USHLL2/UADDW/CMHI instruction gaps. Exact splicing
preserves127 neighboring raw and polled bodies, attributes, types and direct
closure; a Windows COFF candidate retains all128 definitions and poll coverage.
Twenty-three focused cases match the actual original ARM64 prefix against
Linux/Windows raw and polled targets, including guarded and overlapping inputs.
Nineteen cases stop without returning at the real snprintf boundary; binary128
formatting and the tail are not qualified. The candidate remains unselected,
with no game-cohort unsupported-head reduction claimed. A previous whole-shard
lift changed24 neighboring bodies through optimization and remains unselected.

The muted profile avoids the HDMI volume prerequisite for this diagnostic;
continue with it while the TV is off. It does not disable backend initialization
or qualify persistent gain/output. The original engine has a no-sound fallback
after device initialization fails, but startup has not reached that path yet.
A real scalar FCSEL transport bug found by master mute is fixed and tested
against ARM64 on both hosts. Only Unity shard00168 is replaced for this fix;
the earlier Unity USHLL and IL2CPP prefetch replacements remain intact.
Earlier failures, including Game16's original muted crash, remain preserved.

## Current checkout and tools

- Active isolated source: `C:\Users\user\.codex\worktrees\bunker-recomp\bunker`,
  branch `recomp-x86_64`. The shared `C:\GitRepos\bunker` checkout is used by
  separate support work; preserve its branch and edits. The replaced original
  checkout remains at `C:\GitRepos\bunker-backup-before-replace`.
- The isolated `recomp/work` is an ignored junction to the original checkout's
  artifact directory. Existing immutable builds and separate Remill repository
  remain there; do not recursively delete through this junction.
- Remill fork: `recomp/work/remill-src`, branch `bunker`, remote
  `veritr1x/remill`. This is a separate Git repository, ignored by Bunker.
  Preserve Remill changes there as well as Bunker changes here.
- WSL build mirror: `/home/user/bunker-recomp`. The older
  `/home/user/bunker` contains unrelated Archive edits; leave those alone.
- Working build uses native WSL LLVM 18, Python 3.12, pyelftools and Capstone 5.
  Native Windows host code uses MinGW GCC 15.2. Docker Desktop is running,
  but the LLVM 22 Docker development image has not completed building.
- Original APK, extracted libraries, reference tools, reports, generated
  objects and executables remain in ignored work/input directories.

## Completed gates (November 3, 2026)

- Whole-library ELF planning, relocation-backed function pointers, translated
  address dispatch, recursive/direct/indirect/tail calls, constructors and
  checked imports. The integration fixture passes **100,105 checks** on both
  Linux x86_64 and native Windows, including absolute/undefined-weak symbols.
- Parallel, resumable Windows COFF translation with hash-verified caches and
  immutable lifter/semantics snapshots. Unknown targets and unliftable
  instructions fail explicitly.
- Guard-proven jump-table recovery finds 5,262 Unity and 13,473 IL2CPP case
  entries, including width-equivalent masked indices,
  bounded loop closure and joined guard paths.
  Byte/halfword/signed-word, masked-loop and joined layouts pass 9,984
  ARM64-reference checks per platform. Ambiguous patterns remain unresolved.
  Local snapshot proofs now recover the reached hash-tail table even when
  earlier loop expressions are ambiguous; 57,344 additional translated records
  match ARM64 across both hosts and every older table proof remains unchanged.
  See [the exact new proof](whole/snapshot_jump_tables.md).
- Real `libFastAES.so` executes as native Windows x86_64 code: all 48 calls
  match the original ARM64 reference and OpenSSL.
- Real `libmain.so` translated `JNI_OnLoad` registers its original loader
  methods. Its load/unload path works with an explicitly synthetic Unity
  module. This does not establish that real Unity initializes.
- Real Unity now completes all 417 constructors, returns JNI 1.6 with all 42
  native registrations checked against ELF/DEX, and exits cleanly through
  `JNI_OnUnload` and its actual finalizers. The separate `initJni(Context)`
  diagnostic now returns cleanly with zero original JNI exception events,
  using checked Java strings, launch intents and the original APK boot.config.
  The bounded UnityMain surface gate also completes actual created/changed/
  detached native calls, observing two fromSurface, two acquire and four release
  calls against the same actual HWND-backed token before close. The separate
  bounded first-frame diagnostic now receives actual HWND focus, returns from
  nativeResume and enters nativeRender. Reached PackageManager and Intent
  services now have checked implementations. Windows now exposes a real default
  audio endpoint; the frame attempt passes resume and enters engine startup.
  Resolver, ServiceConnection and disabled-AR implementations pass focused gates.
  The latest dual-engine frame creates real ServiceConnection, audio-focus and
  LocationListener proxies. Game9 also returns from the original 256 KiB
  downward-growing mmap and alternate signal-stack installation. The exact
  missing-PlayCore branch and OBB getters pass the earlier startup boundary.
  Game10 resolves MODE_PRIVATE and creates both reached Runnable proxies.
  Unity now naturally loads IL2CPP, executes its nine constructors and resolves
  all 222 original API export requests. Game13 additionally executes the real
  parser and enters public il2cpp_init, then stops at dup LR82553f20. IL2CPP
  initialization has not returned. Original Java catches
  permit startup to continue past missing getSystemService, runOnUiThread,
  system-UI listener and Handler APIs; these remain work to finish. Original
  preference initialization now opens both actual stores and saves its marker.
  No frame has completed or rendered. A read-only native
  volume observer supplies resume's cached initial music/mute state without an
  invented initial native callback. The full Java/game lifecycle remains open.
- Real IL2CPP completes all nine constructors and both finalizers. Its actual
  parameterless GC signal-initialization routine also passes, installing the
  evidenced actions and acknowledgment semaphore. A fresh full cohort now has
  397,058 traces/3,105 objects and 101 unsupported heads, closed direct targets
  and accepted native constructor/signal-init/finalizer parity. Earlier mixed
  cohorts remain preserved. These isolated gates do not execute collection or
  il2cpp_init; later natural startup has entered initialization as described
  above, without returning. See
  [the current lineage and boundary](windows/il2cpp_snapshot_current.md).
- A separate combined native Windows gate now runs both accepted module
  cohorts together: 417+9 constructors, Unity JNI/initJni, its actual ClassLoader
  findLibrary helper and NativeString destructor, then host-registry loading
  and all 222 original Unity-requested IL2CPP export lookups, refcounts and
  2+2 reverse finalizers. All 3,548 original objects remain unchanged. The
  frozen host uses an isolated checked Object.getClass adapter. Unity's whole
  API loader/startup queue, IL2CPP API bodies/init/GC and managed execution
  remain unrun. See [the bounded combined gate](windows/combined_modules.md).
- The next isolated gate now executes Unity's original API-loader itself:
  real dlopen, 222 ordered dlsym calls and publication of every original export
  pointer. It observes an empty startup queue/JNI cleanup list, runs JNI unload
  while IL2CPP is live, and closes through Unity's real cache helper. All 24
  checks pass. Stale top slots and an empty-map allocation remain process-lifetime
  diagnostic state; no reuse or full boot is claimed. See
  [original-loader scope](windows/unity_api_loader.md).
- The next registration-only gate runs Unity's original dispatcher and checks
  all 1,987 registrations through the actual IL2CPP lookup API. Real DSO teardown
  invokes the registered map destructor once and frees all 3,972 observed map
  allocations. Its 2,019 checks plus eight isolated precondition cases pass.
  Stored native targets, configuration, init and GC remain separate gates. See
  [the registration and teardown boundary](windows/unity_icalls.md).
- Three original preinit APIs now pass 2,030 checks: log callback, runtime
  exception policy and the command line measured from Unity's actual getters.
  The observed argc is zero; only that empty-argument path is qualified. Both
  libraries' registered argument-state destructors run once in ownership order.
  Paths, managed-data copy and init remain separate. See
  [the preinit boundary](windows/unity_preinit.md).
- Unity's reached APK setvbuf shape passes 76 native checks, and real rooted
  unlink/rmdir pass 138 checks; each retains the 116-check file regression.
  Real directory streams now pass 16,309 checks and 2,839 NDK calls, retaining
  that file regression. Real absent-destination quarantine moves pass 103 checks.
  The original ZIP-backed Managed-copy component now copies all 24 APK files
  (24,570,231 bytes), checks every size/CRC/SHA and actual metadata read/mmap,
  and retires its original owners and streams. A read-only follow-up of game10's
  unique original-process DataRoot also verifies the natural physical copy:
  exactly those 24 files, with every byte matching the original APK. This does
  not qualify the later copy helper return/cleanup or IL2CPP initialization. See
  [the copy component](windows/unity_managed_copy.md).
  See [directory streams](windows/filesystem_directory.md),
  [buffering](windows/filesystem_setvbuf.md) and
  [single-entry removal](windows/filesystem_remove.md).
- Android process CPU `clock()` and `sysconf` page-size/online-CPU queries now
  use real host APIs, passing 453 checks and 57 actual NDK calls per host.
  Known unimplemented query names fail explicitly. These prerequisites do not
  establish collector startup. See [the process adapter](windows/libc_process.md).
- The original parameterless IL2CPP stack-top helper passes 3,264 checks with
  real pthread attributes, committed guest-stack backing, nine constructors,
  two finalizers and thread retirement. Collector state and all 256 thread
  buckets remain pristine. No save callback, init or collection executes. See
  [the original stack helper](windows/il2cpp_stack.md).
- The original IL2CPP save-only helper passes 3,929 checks using its real
  automatic environment and callback. Its lifetime is revoked at actual helper
  return; the raw trailing global is not a surviving root. No collection runs.
  See [the save-helper boundary](windows/il2cpp_save.md).
- Reached gettimeofday/getpid use real host time and process identity.
  Reached resolver/interface/disabled-AR Java behavior passes 141 checks on
  each host plus JNI/Context/PackageManager/callback/constructor regressions.
  Enabled AR remains an explicit unsupported native-effects boundary. See
  [the Java scope](windows/java_init.md).
- Reached JNI reference arrays pass 1,450 checks per host, covering owned
  elements, covariance, local/global/weak references, threads and unlocked
  retirement. Settings.Secure's exact Android-ID query now reads an explicit
  per-user Windows store; actual missing rows reach the original nullable
  fallback. Its focused checks and six Java/JNI regressions pass on both hosts.
  A later natural frame passes those earlier lookup/factory boundaries but still
  stops before nativeRender returns. See
  [reference arrays](windows/jni_object_array.md) and
  [settings and identity scope](windows/settings_secure.md).
- The exact singleton ServiceConnection and audio-focus proxy profiles preserve
  original native handles, interface arrays, class-loader identity and explicit
  disable/ownership. Active callbacks remain unsupported; no service or focus
  event is invented. Both profiles pass Windows/Linux focused and regression
  gates and are reached by the original first-frame path. See
  [proxy scope](windows/jni_interface_proxy.md) and
  [the latest natural startup result](windows/game_bootstrap.md).
- The reached LocationListener now has its exact six-method interface and a
  distinct singleton proxy profile. Both hosts pass 547 focused checks and all
  existing proxy/Context/Java regressions. Every active callback remains an
  explicit boundary; no GPS, provider or coordinate result is supplied. The
  original factory's actual singleton Class[] is now captured in game8. See
  [LocationListener scope](windows/location_proxy.md).
- Typed host JNI reference-array results pass 2,289 checks per host, preserving
  result assignability and owned callback frames. The OBB directory getters use
  an explicit ordered volume catalog and preserve unavailable null slots;
  Windows passes 106 focused checks with real mapped directories, Linux 88 with
  a labelled injected verifier. See [array returns](windows/jni_array_result.md)
  and [external-volume scope](windows/android_obb.md).
- JNI integer and binary32 methods pass 11,125 focused checks per host plus
  existing JNI/frame regressions. Actual Base/interface method IDs resolve the
  implementation before decoding independent GP/FP or va_list argument banks.
  Float promotion is checked against the original ARM64 object; no Java numeric
  method body is implied. See [numeric transport](windows/jni_numeric.md).
- Persistent SharedPreferences passes 1,052 Windows and 643 Linux focused
  checks, five explicit boundaries and JNI/frame regressions on each host.
  Windows qualification uses isolated real registry stores; decoded TEST
  migration calls do not establish original Unity initialization. Game11 setup
  exposed duplicate NoSuchElementException ownership with configured APK assets;
  canonical ownership and the combined16-check regression now pass on both
  hosts. Game13 genuinely reads absent v2/legacy stores and writes the v2
  integer version marker1 with native persistence status0; no direct production
  registry readback or completed teardown is claimed. See
  [preferences storage and ownership](windows/shared_preferences.md).
- AssetPackManagerWrapper's original missing-PlayCore branch passes 209 focused
  checks and eight explicit boundaries per host. The exact APK code catalog
  includes all four DEX containers and split metadata; the actual factory is
  absent from that supplied code scope. A real nonnull singleton reports the
  missing API, allowing original native branching without fabricated pack
  results. Game9 and game10 pass the previous natural startup boundary by
  original flow, without separately instrumented native callback claims. See
  [wrapper initialization and ownership](windows/asset_pack_wrapper.md).
- The reached exact sscanf %llu profile passes 2,319 focused checks and 225
  actual NDK calls on each host, existing LibC/startup regressions and four
  production fatal-format boundaries. It preserves Bionic's 512-character token
  limit, unsigned overflow/errno and tracked eight-byte assignment behavior.
  Game13 executes two original scans successfully, parsing638477124699603280
  and writing that uint64 value to unity.ver. See
  [the bounded parser](windows/libc_sscanf.md).
- Bionic's process-global C/C.UTF-8 locale state passes3,927 focused checks and
  362 actual NDK calls per host plus the existing locale/LibC/startup gates.
  The tests exposed a real Windows C++ TLS teardown ordering bug; the locale
  selection map now uses checked native thread storage, with19 actual cleanup
  callbacks observed. The separate pthread/EGL/automatic-frame stores now pass
  focused thread-exit and existing provider gates, with16 real native cleanup
  callbacks per store plus six nonempty binding maps. Game13's actual
  setlocale6/empty call at LR8254d0b4 qualifies public IL2CPP init entry, without
  proving inner initialization or its return. See
  [locale semantics and lifetime evidence](windows/setlocale.md).
- Real descriptor duplication passes 14,215 focused checks and 4,164 actual
  NDK calls, plus file/mapping regressions. Native proof confirms separate
  descriptors/handles sharing file position, independent close/CLOEXEC state,
  and removal of native handle inheritance. The managed descriptor namespace
  remains explicitly bounded; the next natural run must qualify the actual
  IL2CPP call. See [descriptor lifetime and scope](windows/filesystem_dup.md).
- Unsigned SIMD widening (USHLL/USHLL2) passes 121,088 reference records per
  host and 260 decode controls. The accepted sparse Unity shard replacement
  fixes the actual ZIP enumerator reached during copying; it retains all old
  heads and reduces Unity's remaining unsupported heads to 1,342. See
  [unsigned widening](whole/ushll.md).
- Windows JNI, module loading, mounted files, Android context metadata,
  logging/formatting, scalar ABI, libc and pthread providers have direct and
  NDK-translated caller tests. See [windows/README.md](windows/README.md)
  for supported behavior and remaining boundaries.
- Remill additions cover ADC/ADCS, lane/replicate/structure loads, table
  lookups, release stores, shifts/narrowing/permutations and many scalar/vector
  FP comparisons, conversions and arithmetic operations. FP result bits and
  FPSR are checked against ARM64 QEMU across rounding/FZ/DN modes, boundary
  values and deterministic random inputs. Physical ARM64 validation remains
  useful, especially for floating point.
- FP32/FP64 scalar/vector reciprocal and reciprocal-square-root estimates now
  match 3,354,880 ARM64 reference records on each host, including every lookup
  bucket boundary, FZ/DN/rounding modes and cumulative FPSR. Existing engine
  objects retain their earlier frozen semantics until refreshed.
  See [the exact estimate gate](whole/fp_estimates.md).
- Immediate signed/unsigned SIMD right shifts match 245,760 ARM64 reference
  records on each host, covering every legal shift amount, overlap, upper
  clearing and unchanged flags. See [the shift gate](whole/right_shifts.md).
- SIMD TRN1/TRN2 transposes match 17,920 ARM64 reference records on each host,
  including all allocated arrangements and source/destination overlaps.
  See [the transpose gate](whole/transpose.md).
- Indexed FP32/FP64 FMLA matches 5,689,856 exact ARM64 result/source/FPSR/NZCV
  records on each host. The original Unity matrix now lifts completely; the
  current refreshed Unity cohort includes these semantics. See
  [the fused arithmetic scope](whole/fp_fmla.md).
- Indexed FMUL's NaN/FZ/DN behavior is corrected and passes 8,444,032 ARM64
  comparisons per host. The exact original 104-byte Unity matrix leaf now
  passes 36,928 finite and 18,432 nonfinite/FZ records on each host, including
  register, memory, alias and guard checks. Its former 5,368 diagnostic failures
  are preserved as a separate baseline. Ordinary FMUL remains outside this
  correction. See [multiply scope](whole/fp_fmul_indexed_scope.md) and
  [the exact original-code execution boundary](whole/unity_matrix_scope.md).
- Proved direct setjmp import calls now seed executable post-call continuations
  in the compiler: 49 roots in Unity and one in IL2CPP. Native dispatch checks,
  normal context-save tests and whole-compiler regressions pass on both hosts.
  This does not implement longjmp transfer or refresh existing engine objects.
  See [continuation proofs and boundaries](whole/nonlocal_roots.md).

Latest three-library instruction-form audit with LLVM 18 / Remill source `c535b75`
(`windows-estimate-shifts`, November 2):

| Library | Supported forms | Unsupported occurrences | Weighted liftability |
|---|---:|---:|---:|
| `libunity.so` | 1,280 / 1,442 | 5,579 | 99.8115% |
| `libil2cpp.so` | 918 / 941 | 176 | 99.9982% |
| `libgrpc_csharp_ext.so` | 776 / 826 | 666 | 99.8313% |

Compared with `windows-st1`, exactly the estimate/right-shift forms change:
3,031 unsupported occurrences are removed and no previously supported forms
are lost. The combined remaining count is 6,421. Hashes and per-form evidence
are recorded in ignored `work/coverage-windows-estimate-shifts.json`.

These sample one encoding per operand form and exclude control flow; they do
not establish whole-program correctness or execution coverage. The first
Unity Windows translation completed with 58,850 traces. The prior callback/
ST1 snapshot has 59,561 traces in 469 objects and 1,774 unsupported traces.
The estimate/shift/TRN snapshot has 59,610 traces in 469 objects,
1,345 unsupported traces and zero unresolved direct targets. Its constructor,
JNI, initJni and paused surface/shutdown gates pass natively. Original entries
are retained and all 49 new entries are proved continuations; see
[the frozen lineage and exact execution boundary](windows/unity_snapshot_native2.md).
The current corrected indexed-FP cohort retains the same 59,610 traces/469
objects with 1,343 unsupported traces, no newly unsupported heads, identical
State layout and closed direct references. Its constructor/JNI/initJni/paused
surface gates also pass on Windows with frozen callback-frame host `32edc69`.
See [current snapshot evidence](windows/unity_snapshot_indexed_fp.md).
The optional `initJni` diagnostic retains exception history so clearing a Java
exception cannot turn a missing-service path into success. Static callback
root recovery finds 112 Unity callback entries, including three otherwise
unseeded tiny destructors; this clears the observed finalization failure.
The initial IL2CPP translation completed
with 393,781 traces in 3,079 objects, 192 unsupported traces and zero unresolved
direct targets. Exploratory objects retain explicit failure paths for
unsupported instructions.

## Active work

1. The first captured and presented original game frame is verified in run23.
   Continue actual normal nativeRender beyond the diagnostic stop and fix the
   observed non-quiescent worker retirement during shutdown. Use
   [the current result](windows/first_frame.md), not the historical checkpoints
   above. Continue actual normal nativeRender through
   engine configuration and managed initialization. The refreshed IL2CPP cohort has passed lineage and native
   lifecycle gates. The new dual-engine diagnostic combines it with the accepted
   Unity hash-tail entries and unsigned-widening replacement, preserving older
   diagnostic cohorts. IL2CPP loads only when original Unity code requests it.
   Inspect reached unsupported traces and unresolved targets. Unity has 417
   initializers/344 imports; IL2CPP has nine initializers/280 imports.
2. Preserve the passing actual `initJni(Context)`/APK asset/surface handoff paths
   and continue the bounded focus/resume/frame/pause/done UnityMain flow with
   explicit master mute while HDMI is unavailable, then qualify the real default
   audio endpoint separately. Exercise the application ClassLoader/IL2CPP
   module path and audited internal file/cache services on this natural path.
   Keep the passing 417-constructor/JNI/shutdown gate. Never turn unknown
   imports or unsupported Java effects into successful no-ops.
3. Close instruction gaps reached by startup, then remaining SIMD
   stores/shifts/permutations, FP rounding and crypto groups.
   Coordinate shared Remill builds; engine builds use immutable snapshots.
4. Audit actual imports against available providers, then implement
   startup-critical libc/resource gaps using translated NDK caller tests.

## Remaining milestones

- Real Unity/IL2CPP startup and the Java service/native lifecycle catalog
  required by this APK. JNI support is an explicit catalog, not a Java interpreter.
- IL2CPP GC suspension/signals and needed Bionic/ELF TLS. The separate signal
  provider supplies checked masks and queued delivery; the older pthread-only
  provider leaves nonzero delivery/masks and atfork unsupported. Game22 executes
  one bounded original finalizer stop/restart cycle; general collector
  integration, root scanning and managed retention/reclamation remain unverified.
  Optional real-worker lifecycle hooks now pass 566 focused/78 existing checks,
  preserving creator mask snapshots, actual worker/TLS lifetimes and separate
  provider-destructor validation. The opt-in game profile installs these hooks
  and bounded polling bindings. Game22 executes both original handlers and
  posts with a physically verified interrupted frame; broader paths remain open.
  See [worker ownership](windows/worker_lifecycle.md).
  [The binary/ABI evidence and required gates](windows/GC-SUSPENSION.md) are
  preserved for the implementation; both stop and resume acknowledgments are
  needed by this collector's default retry mode.
  Opt-in compiler/runtime cooperative polling passes 27,349 checks/260 pauses
  on each host, including optimized register roots and irregular CFG cycles.
  [Its contract](whole/cooperative_poll.md) leaves provider transition roots
  and interruptible waits explicit. Signal-frame byte gates also pass;
  general production integration and collector correctness remain unverified. See
  [the frame contract](whole/signal_frame.md).
  [A bounded combined gate](windows/signal_delivery.md) passes 16 same-worker
  stop/restart cycles on both hosts with NDK handlers and actual guest-stack
  contexts. Game22 now executes the game's original handlers in the bounded
  finalizer profile; repeated cycles and other worker/provider shapes remain open.
  Virtual alternate stacks now pass 193 focused checks per host plus the existing
  signal, semaphore, delivery and frame gates. Active frames pin real mapping
  allocations; installed metadata remains unpinned, preserving original Unity's
  failed-restore/unmap behavior. Three measured QEMU-user differences remain
  explicitly separated from the pinned Android contract. See
  [alternate-stack ownership and limits](windows/signal_altstack.md).
- Original Unity's alternate-stack allocation requests valid MAP_GROWSDOWN.
  The opt-in Windows profile now commits real downward growth on native access
  faults, with fixed owner generations, guards and physical mapping leases.
  Qualification includes 535 positive checks, native guard faults and targeted
  production import boundaries. Game9 genuinely allocates and installs the
  original stack; in-game growth faults, delivery and collector use remain
  unqualified. The unenabled profile still stops explicitly. See
  [the native growth contract](windows/growdown_memory.md).
- Finish provider memory integration and exercise paired exclusives in real
  Unity startup. The replacement single/pair reservation protocol passes 90,112
  instruction comparisons per platform plus 97 runtime checks and five
  rejection checks per platform.
  Host providers must participate in tracked reads/writes and allocation
  lifetime invalidation; untracked native/external writes remain a boundary.
- Real Windows HWND/Surface ownership passes 291 NDK/host checks. The checked
  EGL bridge passes 49 checks, including real window/pbuffer draws, readback,
  swap, tracked outputs and resource lifetimes. The actual Unity surface gate
  now passes temporary crash-action setup, a real saved Bionic context, and
  observed native window handoff/detach, all with clean shutdown. Rendering
  remains a separate gate. Default-size RGBA/RGBX format support passes 391
  additional native draw/lifetime/concurrency checks; RGB565 is unsupported.
- Pinned Vulkan ANGLE now passes GLES3.2/AEP, shader, draw/compute and all 28
  ASTC formats (239 samples/61,184 bytes), including correct sRGB behavior.
  The typed query resolver passes 976 checks for six getter signatures and 133
  enum widths. An additional 28 scalar state/clear signatures pass 342 checks
  through actual NDK callers, native state/error comparison and 64 independently
  checked RGBA pixels. Errors follow actual EGL contexts across switches and
  native thread migration; all 976 query regressions still pass. See
  [the scalar command boundary](windows/gl_scalar.md).
  A further 29 shader/program/VBO/VAO/draw/readback commands pass 286 checks
  through ten strict NDK traces, including real array/indexed triangles and
  exact native pixel comparison. Query976/scalar342/EGL49 regressions pass.
  Readback is restricted to in-bounds owned pbuffers; textures, uniforms,
  client/mapped memory, FBO commands and compute execution remain open. See
  [the typed draw scope](windows/gl_draw.md).
  A separate native Vulkan scaling variant now passes fixed-size
  buffer negotiation, physical/logical resize and present-mode checks; the
  original ANGLE bundle is preserved. Further GL APIs, client/mapped memory, Unity's
  full surface/resume/frame lifecycle, input and audio remain unverified.
- Real APK/data/decompression paths and Bunker backend/launcher services,
  including required networking and Android service behavior.
  The Windows harness does not yet start embedded Go Lunar Tear, configure
  matching loopback ports/asset roots or provide socket imports. The backend's
  required master/resource dump was found in Downloads. A separate patched
  master and all201073 revision0 files/20907771934 bytes now pass preparation
  and inventory/CRC checks. The native Go DLL passes real Start/SelfTest/Stop
  with fresh save storage and explicit loopback ports38003/38080/33000; the
  listeners are released before child exit. No game connection is claimed.
  Matching client transport changes and real native socket providers remain
  pending; prepared private-server derivatives are not selected in the game.
  See [the backend preparation and receipts](windows/backend_native.md).
  The native APK reader passes 69 independent checks on both hosts and reads
  the actual 149-byte boot.config exactly; checked Java stream/Scanner wiring
  now clears the actual native initJni gate.
  See [the reader contract](windows/apk_assets.md).
- Normal setjmp context saving is implemented and used by the real surface
  gate with an owned mmap lifetime and inherited worker mask. Longjmp transfer
  remains fatal: it needs rooted continuation PCs and a proven unwind/status
  route compatible with lifted LLVM contracts. See
  [the exact wire/transfer boundary](windows/nonlocal_jmp.md).
- Reach title screen, load a save, exercise gameplay/render/audio/input, then
  package a reproducible Windows build consuming user-supplied game assets.
- Preserve local checkpoints in both Git repositories after review. No remote
  push or public upstream PR has been made during this continuation.

## Reproduction and cautions

[whole/README.md](whole/README.md) describes the current compiler and gates.
[README.md](README.md) retains the older Docker/reference experiments.
Use a WSL filesystem for large builds; source can be read from Windows.

The fork now tracks included semantics sources as CMake dependencies. Rebuild
Remill before starting a new translation snapshot after compiler edits.
`--resume` reuses compatible, hash-verified output; keep one writer per output
directory. `--allow-unsupported` is diagnostic, never evidence of a complete
translated library.
