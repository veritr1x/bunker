# Native Windows first-frame status

The target is the original game running as a standalone Windows x86_64
executable. A presented game image and working gameplay remain unverified.

Current execution frontier: missing scalar query width for
`glGetIntegerv(0x90d9)`, original return `70488370`. Actual build
`work/windows-first-frame-gles-procedure1`, host
`367977430191d3e04b619c815d6e334b9cc30530`, executable
`eec19b0e2967dd01f24eb919132539d9412bed972abf4d0c747a97f665dc0df0`,
returns null from all27 optional procedure lookups and reaches the
capability scan. It records2758 paired EGL calls and201 GL dispatch
attempts; the terminal query is rejected before native forwarding.
There is no presentation, nativeRender return or frame PNG. The bounded
audit is `work/first-frame-gles-procedure-width-boundary1`.

The four identified scalar query entries are now qualified against real
ANGLE:1142 checks,137 enum rows and all three typed getter widths. The
old133 rows are an exact prefix and all other GL source bytes are exact.
Receipt `work/gl-query-width-qualification1/acceptance.json` has SHA256
`d57dc87c9210b6802c9b133315c5001cbf4b33959a6bea4a46f2a3ff61392515`.
One terminal runner CR was normalized after execution with exact AST and
single-byte proof; no functional test was replayed or claimed for that
format-only change. The next build is
`work/windows-first-frame-gles-query-width1`.

The preceding execution frontier was the configured EGL procedure resolver throwing
on `glDebugMessageControl`. Actual build
`work/windows-first-frame-gles-module1`, host
`0bf472dc4f45a9ae929fe540a88685eccd4fdbd1`, executable
`84263022c5c5ce94346665dbb97b1d8e9960b4eddf5bb64f417839e890fce04e`,
now resolves the GLES module and dispatches188 real typed GL queries
(one GetString, one GetIntegerv and186 GetStringi calls). It stops at
`eglGetProcAddress`, with no drawing, swap, nativeRender return or PNG.
Original `7047363c` explicitly accepts a null result before storing the
optional debug pointer. The next repair makes the configured typed lookup
return zero for unsupported names, consistent with the
[EGL procedure-lookup contract](https://registry.khronos.org/EGL/specs/eglspec.1.5.withchanges.pdf),
while preserving known markers and the default unconfigured-resolver fence.
No debug API or callback is replaced with successful stub behavior.
The extended actual NDK/ANGLE component passes140 checks, including
known GL/EGL markers, null optional results, unchanged default fence
and pending-error behavior. The previous registry22-case results per
host are source-hash-verified and reused rather than rerun. Receipt:
`work/gl-nullable-proc-qualification1/acceptance.json`, SHA256
`71c3725f9d88db882a122a132b4292ae7ec2c77acee41410e1d00d53a4a364c9`.
The next build is `work/windows-first-frame-gles-procedure1`.

The preceding execution frontier was guest `dlopen("libGLESv2.so",2)` and its
three `dlsym` requests return zero, followed by an unresolved indirect
target0. The graphics provider already has typed `glGetString`,
`glGetIntegerv` and `glGetStringi`; the module-loader path does not yet
expose them. The final indirect caller/State was not captured, so its
exact consumer is not attributed.

Actual build `work/windows-first-frame-build-model1`, host
`7c1ecf9519cc5d5bafb180a4bf55afdfb42d9819`, executable
`49306b94f1bee1b2a836df1db9008f13bb8e3163f2580f1948a970323ec607f9`,
records2731 paired original EGL calls, including successful context and
window-surface creation, MakeCurrent and SwapInterval. There is no guest
GL dispatch, eglSwapBuffers, successful presentation, nativeRender return
or PNG. The next repair registers the existing typed GLES functions as
an explicit service module, preserving real ELF ownership/dladdr rules.
The exact run audit is `work/first-frame-build-model-gles-boundary1`.
The typed-service repair now passes130 real Windows ANGLE/NDK loader
checks, plus the unchanged22-case registry suite on Linux and Windows.
It exposes the existing63 GL markers, preserves Open/Symbol/Close, and
keeps typed-service markers outside ELF address ownership. The ordinary
incomplete-ELF catalog guard remains active. The receipt is
`work/gl-module-qualification1/acceptance.json`, SHA256
`a0e4d39898323a00760f3a118ccdec1471859cfd20849a151f78b1a17178793d`.
No GL implementations or guest objects are changed by this repair.
The next build is `work/windows-first-frame-gles-module1`.

The preceding execution frontier was missing static `android/os/Build.MODEL`
String. Build `work/windows-first-frame-fcvtzu-fixed1`, host
`3fc7304f51b6a78d9cd182a049f5f8ac4de9bc8a`, executable
`28048f7ca5104cb3f43bb7b7e32387c7cdc3539881dd819d913e94aa5e574ec0`,
reaches original native window width/height queries without an unliftable
instruction diagnostic; a direct entry/return witness for the preceding
repaired function was not captured. Actual startup exits native3/controller1
after `NoSuchFieldError: MODEL:Ljava/lang/String;` and guest `strlen`
rejects null X0, with recorded return `700f4ecc`. Original master mute
returns and9 IL2CPP constructors execute. There are still no EGL/GL calls,
nativeRender return, successful presentation or frame PNG. This requires
the reached typed Build field in the explicit absent-product-property
profile, followed by another original execution. That additive profile
extension now passes45 checks each on Linux and Windows through actual
NDK JNI callers, including typed field lookup, static String/UTF8 and
lifetime checks, MANUFACTURER regression and retained SDK33. Its receipt
is `work/build-model-qualification1/acceptance.json`, SHA256
`5d8357b570a0c4acc984d8d2f6f2e95c7d9c8acad991c7005d7bb27912fa8b83`.
The next build is `work/windows-first-frame-build-model1`; its guest code
and v10 cohort remain unchanged. The exact preceding-run audit is
`work/first-frame-fcvtzu-model-boundary2`.

The preceding execution frontier was `FCVTZU X9,S0,#10` at `70362a44`,
word `9e19d809`, reports the following PC `70362a48`. It is in original
function `70362a2c..70362a8c`, selected object123. The frozen Windows
executable `c40327523b766606112244abd7e15208d6f030704ac828d977e72c7adb71c23c`
includes the global FCSEL transport repairs and both qualified ST2
initializer repairs. Its actual muted execution passes the real focus
event gate and returns from original master mute, then exits
native3/controller1 at this conversion. There are no EGL/GL calls,
returned nativeRender, successful presentation or PNG. The four unsigned
fixed-point scalar conversion forms are now implemented, qualified and
selected in the build above. Existing
FCSEL repairs in object123 remain exact. The same function also
contains unscaled `FCVTZU X8,S0` at `70362a5c`, word `9e390008`.
Actual pinned compiled semantics dereference its numeric float carrier.
The bounded toolchain repair therefore includes numeric transport for
the four unsigned unscaled S/D-to-W/X forms, retaining the existing
integer conversion and exception helper byte for byte. Signed forms,
FP16 and vector conversions remain outside this repair.

The [conversion family gate](../whole/fcvtzu_fixed.md) matches43,008
records per ARM/Linux/Windows platform and passes531 decoder checks.
The [original-function gate](../whole/unity_fcvtzu_fixed_function.md)
matches16 cases on ARM and Windows/Linux raw/polled variants, with full
architectural captures and independent host State checks. Its zero-result
path calling real `703631a8` remains explicitly outside the dynamic gate.
Only `70362a2c` in object123 is replaced; all127 neighboring IR/native
bodies, including the existing FCSEL repair, remain exact. The v10 cohort
retains456689 heads and3576 objects and removes only this unsupported head.
Component results do not establish nativeRender return or a game image.
Both production build/runner guards pass907 cases each, including the
actual parent and new-plan file-integrity checks, in
`work/cohort-v10-validation2`. The first validation attempt preserved all
907 predicate results but stopped at a stale test-driver plan locator;
the corrected fresh run passes completely. The frozen v10 cohort is
`work/first-frame-fcvtzu-fixed-cooperative-cohort1`, acceptance
`0b43fb3dcee223186d0a6023d56f2de769ccc35612fcab805a672943db44d7e5`.
The actual Windows build and execution are recorded above; these
component checks alone did not establish that outcome.

The first display-enabled build is `work/windows-first-frame-attempt1`,
host commit `e48ee60b1e920c9079fa744bddce851a39121a24`. It includes the
Windows display adapter, explicit AOSP unknown-manufacturer profile, JNI
instance long returns, and opt-in EGL/GL diagnostics and PNG capture.
The native build and focused component checks pass. Its actual muted
collector startup exits with access violation C0000005 before EGL or GL;
no image or successful presentation was recorded.

One debugger execution of that exact executable, preserved under
`work/first-frame-native-av-debug1`, identifies the failure. The original
refresh-rate wrapper `70acc13c` calls `Display.getRefreshRate()F` through
JNI slot56. It receives the actual Windows refresh rate120.0f. Original
instruction `70abccbc` (`1e281c08`, `FCSEL S8,S0,S8,NE`) selects float bits
without accessing memory. The retained generated body instead performs
`select -> inttoptr -> load i32`. It dereferences the selected120.0f bits,
`42f00000`, and faults. The frozen native fault is
`sub_70acc13c+4020`; the captured module base and native instruction agree.
This diagnoses a retained legacy FCSEL translation, not a JNI object or
long-return mismatch.

The repair reuses the already qualified FCSEL translator documented in
[fcsel.md](../whole/fcsel.md), regenerates the complete original refresh
wrapper, and replaces that body in Unity shard459. Other definitions,
guest inputs, State layout, host providers and lifecycle behavior must
remain unchanged. A focused check must cover the exact instruction with
120.0f/zero inputs and both selection outcomes before another original
startup is run. Passing that check alone does not prove game rendering.

The repaired refresh wrapper is selected in
`work/windows-first-frame-fcsel1`, host `0d019faba9514fdd09e7215592c5e2f33ec3a84e`.
Its four directed complete-wrapper cases pass on Windows and Linux in raw
and polled form, alongside the original ARM opcode check. Both build
consumers pass302 cases each. The native executable builds successfully.
The original muted startup still exits5 before any EGL/GL call and has no
frame witness or image. Its external read-only module snapshot records
actual base `7ff6bd160000`; native fault `7ff6bfcdb2ee` maps to RVA
`2b7b2ee`, `sub_704238f4+942`, after the corrected wrapper call.

That second fault maps to original `70423960`,
`FCSEL S0,S1,S0,MI`, in constructor FDE `7042377c..70423a24`.
The retained native body again dereferences selected float bits. No
register context or accessed address was captured for this run; a value
for the faulting native R8 is not inferred. The same original instruction
appears in five selected shard161 bodies: `7042377c`, `704238f4`,
`70423908`, `70423918`, and `70423928`. The next repair covers all five
together and retains the refresh-wrapper repair. A bounded inventory of
the13 declared display/metrics wrapper heads finds no remaining instance
of this legacy scalar-selection dereference there.

The five-constructor candidate preserves123 other functions in raw,
polled and native form. Its directed test executes all five selected
entries with120/0/10 inputs, checking stored refresh bits, the normal
return path, preserved registers/stack and the remaining SDK33 result
fields. Fifteen records match on Windows/Linux, raw/polled. Three
independent ARM opcode checks cover the same selection outcomes.
These use labelled controlled getter/SDK seams and establish the
candidate behavior; the next integrated startup remains necessary.

The combined repair is selected in `work/windows-first-frame-fcsel2`,
host `36db3922df5dbd0fd0fe16695f9c2918473cde9a`, executable SHA256
`50674f04a6e5d13d807e313a2cd266196107164cf75d61dd0c364ff6e896626e`.
The native build and412-case checks for each consumer pass. Its actual
startup exits native3/controller1 at `unliftable instruction707bb4bc`.
Neither earlier native access violation recurs. There are still no
EGL/GL calls, successful presentations, returned nativeRender or frame PNG.

The reported PC is the next PC after original `707bb4b8`, word `4c008d80`,
`ST2 {V0.2D,V1.2D},[X12]`. The decoder currently rejects this multiple-
structure store; the latest qualified toolchain has no matching selector.
Original FDE `707bb458..707bb55c` initializes a0x498-byte object with a
finite interleaving loop and no calls. Only head `707bb458` is selected
in shard270. The run has no captured dynamic caller/thread context for
this instruction, so a returned display constructor is not inferred.
Proper ST2 translation and ARM memory/writeback reference checks are the
next prerequisite. The original bytes and read-only attribution are in
`work/first-frame-st2-audit1`.

ST2 is now implemented and qualified for the seven valid multiple-structure
arrangements and three addressing modes. The family gate matches1120 ARM,
Linux and Windows records,685 decoder checks and70 raw full-State checks
per host. The original object initializer matches16 cases across ARM and
Windows/Linux raw/polled execution. Only its body in shard270 is replaced;
the other127 functions remain exact. See [the ST2 gate](../whole/st2.md)
and [the original initializer gate](../whole/unity_st2_object.md).

The selected build `work/windows-first-frame-st2-1` uses host
`f8298953bace6cd5ea97c5f3a9278c09c3ce48a1`, executable SHA256
`44215a6da838aedbfecea888c0db554d08e40152350d9f8d2ea0b631f6b91bdc`.
Its native build and520-case checks per consumer pass. Original startup
still exits native5/controller1 with no EGL/GL calls, nativeRender return
or PNG. The earlier unliftable ST2 record does not recur. Actual base
`7ff6d8d70000` maps fault `7ff6e47125fe` to RVA`b9a25fe`,
`sub_70a01d00+3198`. The current fault is another retained FCSEL lowering:
original `70a01e34`, `FCSEL S0,S2,S1,EQ`, in FDE
`70a01d00..70a01e6c`, shard353. Native R12/accessed address and a dynamic
caller stack were not captured; their values are not inferred.

The next repair inventories remaining selected FCSEL implementations as a
group. Each proposed body must prove a FCSEL-only delta against its current
selected body, with existing ST2/EXT/prefetch repairs and neighboring code
preserved. A single batch replaces admitted bodies; unrelated differences
remain excluded. This addresses the common legacy defect across the
selected code rather than fixing only the newest caller.

The completed inventory identifies 5,766 faulty copies in 2,164 functions
across 556 objects. A full fresh-proposal pass generates all 556 modules but
holds 304 function comparisons; none is selected. The separate
[exact transport repair](../whole/fcsel_batch.md) changes only each
erroneous scalar-load line, retaining the original predicate, SSA names,
upper clear and all other bytes. Its 32 focused checks and real LLVM module
parses pass. All 5,766 original conditions pass evaluation for all 16 NZCV
combinations (92,256 checks, zero unknowns), and all 2,164 candidates pass
their inverse checks. All 556 objects compile. Native preservation is
byte-exact except nine constant-pool relocation addends in seven unchanged
functions of object2598. A separate saved-object check proves identical
resolved data, required alignment and every other instruction byte; the
original failed comparison remains preserved. Raw and polled neighboring
bodies stay exact. Final cohort validation and integrated startup remain
separate gates; these results do not establish a frame.

That batch is selected in `work/windows-first-frame-fcsel-batch1`, host
`55056035c9f77e52c4bb5de27d1bfec8278e85fb`, executable SHA256
`d3f499bfa14c59a7d8827695098edb986a687bfb0c7a96df5fc9181d0fbf075c`.
Its actual original startup exits native3/controller1 at reported
`70752174`, with the first-frame witness false. The original previous word
is `4c008d40` at `70752170`: ST2 2D/base through X10, already supported by
the held ST2 tool pair. The following instruction is a supported B.NE.
The next prerequisite is applying the existing translation to this
retained original function, with current FCSEL repairs preserved. The
exact reached word still needs its function-specific execution check;
no repeat of the generic ST2 family campaign is required.

The constructor repair is now qualified in
[the original-function gate](../whole/unity_st2_constructor.md). It
replaces only `707520c4` in object 249 and preserves all 127 neighboring
functions in raw, polled and complete native code. Sixteen cases match
across the untouched ARM64/Bionic function and Linux/Windows raw/polled
translations, including genuine memset effects, every object byte,
allocation canaries, normal return and the declared ABI-defined register
subset. The current FCSEL vector remains selected. Its new loop adds one
cooperative poll site; the complete cohort retains 456689 heads and removes
only this unsupported head. All 794 v9 guard cases pass in each of Python
and PowerShell. Build `work/windows-first-frame-st2-2` links successfully
under host `089a79354540b707fff7c53057749c3ace72470f`. Its first execution
times out waiting for a real Windows focus event before engine resume;
that execution alone does not establish progress through the repaired
constructor. A fresh observational run of the same frozen binary and
inputs, `work/windows-first-frame-st2-focus1`, passes the real focus gate
and reaches the fixed-point FCVTZU frontier above. It completes417 Unity
constructors/JNI and9 IL2CPP constructors; original master mute returns.
The earlier unsupported ST2 no longer terminates this execution. The
exact frontier audit is `work/first-frame-st2-focus-fcvtzu-boundary2`.

The next host build also expands only the native Crash handler's logging
to include the actual module base, thread, accessed address/operation and
x64 register context. Its MinGW syntax check passes, and reversing that
single function span recovers the previous source byte for byte. This
supports diagnosis from the next original execution without assuming a
faulting register's value.

First-frame acceptance requires an image captured from the original GL
window framebuffer, original drawing activity, a successful original
`eglSwapBuffers`, and a returned original `nativeRender`. A synthetic
triangle or clear-only surface is not evidence of a game frame. The
`--first-frame` diagnostic preserves the image and holds the real window
for ten seconds when its witness succeeds. Audio stays explicitly muted
while the HDMI endpoint is unavailable.
