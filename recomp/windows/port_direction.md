# Native Windows port: reassessment and next experiment

Keep the accepted Remill pipeline. The original game already renders; replacing
the compiler or adopting a Switch runtime would discard demonstrated progress
without addressing the observed Android contracts.

## Authoritative checkout and evidence

The active port is `recomp-x86_64` in
`C:/Users/user/.codex/worktrees/bunker-recomp-native/bunker`. The main checkout
`C:/GitRepos/bunker` is on `mods-menu` and has an older untracked `recomp/` copy.
Its Game15 TODO is historical. Neither checkout nor existing compiler snapshots,
objects, diagnostic cohorts or the separate Remill repository was reset.
No applicable Bunker `AGENTS.md` was found in the inspected repository/ancestor
paths. The shared generated work lives at `C:/GitRepos/bunker/recomp/work`.

`bsearch` is integrated in the actual selected `libc.cpp`, including the typed
five-argument import and `Pthreads::Run` guest-comparator route. Its documented
qualification compares 2,373 records per host with an Android13 Bionic reference
and an independent midpoint oracle; it is not the current blocker. See
[the provider evidence](libc_bsearch.md).

Original run26 completed 180 returned renders, 177 genuine presentations and
2,288 draws. Root viewed the untouched Notice and SQUARE ENIX x applibot images.
The original worker-switch repair also passed: worker25 and child26 retired
normally. Finishing then exceeded the host's four-second wait, and original
`nativeDone` returned with missing `android/view/View`. The later Firebase
destructor message does not identify which ownership/quiescence guard failed.
See [the current execution result](first_frame.md) for exact build and audit pins.

## Fastest discriminating experiment

The 180-frame diagnostic deliberately starts finishing at its frame limit. A
cleanup failure is therefore not evidence that normal startup cannot advance
beyond the publisher splash. Run27 reuses the exact accepted executable and
changes only the returned-frame limit to600 and its corresponding audit.
It preserves real initialization, focus prerequisites, scene timing, drawing,
asset data and service failures. It does not invoke a private initializer,
restart a timed-out process, fabricate responses or bypass a collector barrier.

`work/qualified-runtime-apk-firebase-run23` records this count-only controller
change and strict inverse to executed Runtime22. The original run is
`work/windows-first-frame-native-presentation27`. Until its actual result is
collected, progress beyond180, title behavior and gameplay remain unproven.

Use its observed result to prioritize the next repair: an earlier startup
failure, actual input delivery at a waiting screen, or the real client/backend
contract. Keep cleanup-only repairs separate from the critical path to play.

## Donor source review

All reviews used pinned source implementations, not README compatibility claims.
The public clones are shallow partial no-checkout repositories under
`work/donor-review-20261106`. No donor build or replacement framework was run,
and no donor code was copied into production.

| Project and exact revision | Inspected components and license | Decision |
|---|---|---|
| [androidrecomp](https://github.com/sp00nznet/androidrecomp/tree/4a2004953e396fca04e940c300cad7c9f5fa77f3) | `runtime/elf_image.cpp`, `shim_file.cpp`, `shim_posix.cpp`, `shim_sys.cpp`, `shim_varargs.cpp`, JNI/pthread/window bridges and instruction-verification scripts. MIT in the inspected source set. | Bionic layout, varargs spill and instruction/memory differential-test references. Keep Bunker's loader, tracked writes, checked JNI member ownership, real APK assets, genuine ANGLE and qualified pthread/TLS behavior. The donor has no usable View/input hierarchy and contains generic JNI and synthetic input shortcuts. |
| [Lunaria](https://github.com/yui0/lunaria/tree/712985fb322a3cb3a0d3b51e8b7137f8cb7e093f) | `src/loader.c`, `src/dvm/dvm_runtime.c`, `src/dvm/dvm_jni.c`, `src/jvm/jvm.c`, Bionic threading and EGL/GLES. Core MPL2.0; AOSP-derived files have separate BSD/Apache notices. | Actual lifecycle ordering, per-view listener state and View/ViewGroup/FrameLayout hierarchy are behavior/test references. Its wait handling supports pumping queued work outside monitor locks. Do not copy generic-Object fallbacks, successful service placeholders, fabricated insets, GL-error draining or continuation after nativeRender=false. Its Dynarmic/DVM architecture is not an AOT replacement. |
| [TotK Recomp](https://github.com/valentderah/totk-pc-recomp/tree/0ae47a578285cde080642c9e6c40316c99171ef1) | `runtime/dispatch.c`, `runtime/cpu.h`, `recomp/gen.py`, `recomp/jumptables.py`, `tests/diff/atomic.py`, `tests/excl_mt.py`. MIT; CPU/generator material attributes LAS Recomp revision `da35b83a9611d046a9a681aae668d7085954d37f`. | Read-only compressed dispatch tables, bounded jump-table reasoning and differential-test organization are future ideas. Defer performance rewrites. Reject the value-only exclusive helper: its saved-address/value CAS cannot detect intervening ABA or same-value writes. Horizon/NVN does not implement Android/Bionic/JNI. |
| [Serein](https://github.com/niizam/serein/tree/62612eaf5d05a36b58cbf935fe97b0098b77d0e2) | ARM64/native bridge, JNI/TLS destructor ordering, guest signal frames and masks. GPL3 root with explicitly Apache2 AOSP files; per-file provenance is recorded separately. | Behavior references for destructor reentry, guest-stack ucontext and target-thread delivery. Its Linux/ART/Bionic environment and host-longjmp assumptions do not replace Bunker's Windows ownership and guarded retirement model. |
| [Dynarmic](https://github.com/azahar-emu/dynarmic/tree/a46601580d5512d324104f985b5f0209dc980ddc) | A64 interface, test environment and Unicorn differential fuzzing. Core0BSD; optional test dependencies have their own licenses. | Small test-vector/generator/capture code is a reuse candidate with attribution. Do not treat its tests as a universal CPU oracle: exclusive forms are excluded, the basic fixture's exclusive writes always succeed, FPSR comparison is limited, and Jit.Run is nonrecursive. Retain native ARM references and Bunker's stronger State/memory checks. |

Exact file/line permalinks, blob identities, license boundaries and ABI comparisons
are in `androidrecomp-review.md/json`, `lunaria-review/review.md` and
`memory-lifetime-review.json` under that work directory. Androidrecomp was compared
with the actual344 Unity/280 IL2CPP import inventories. Direct reuse, behavior
reference and test ideas are distinct; a reuse candidate is not approved adoption.

## Correctness and remaining milestones

Keep callback guest addresses separate from native pointers; preserve nested
State1200, guest SP/TLS, Memory64 and actual callback return guards. Continue using
explicit Android LP64 layouts and typed Windows LLP64 conversions. Variadic
GPR/FP/vector save areas and return widths need caller-based checks. Every host
write must participate in tracked-memory invalidation. Preserve versioned
exclusive reservations and failure behavior.

Real run26 executed the original collector stop/restart paths through epoch62,
including recorded physical31-GPR/32-Q roots and genuine acknowledgments. This is
stronger than signal/polling component success, but it does not complete the
production GC milestone. Managed retention/reclamation, all supported nested
and provider-temporary roots, wait coverage and sustained stop/resume progress
remain requirements. Unknown contexts must keep failing closed.

New unselected components are separately qualified: native input capture passed
241 hidden-HWND checks plus300 matching NDK/window checks; asynchronous finishing
acknowledgment passed108 checks/18 negatives plus294 frame and53 surface checks.
Capture is not Unity/JNI input delivery; API tests are not original shutdown
success. The root bootstrap integration remains pending a new full build.

A correctly rendered original frame is verified. Complete initialization claims
need their own observed return evidence; a frame does not prove general GC,
clean shutdown, a functioning backend, sustained gameplay or final packaging.
