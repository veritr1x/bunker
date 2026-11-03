# Native Windows first-frame status

The target is the original game running as a standalone Windows x86_64
executable. A presented game image and working gameplay remain unverified.

Current execution frontier: the real foreground/focus prerequisite, before
nativeRender. Actual build `work/windows-first-frame-label1`, host
`cbfd33b57ee3653e2f1605861a7256828b64e5ac`, executable
`f5d07ac77d283cd763d07caa3503fb16bec2c8074d6a1b5660ca2db1bf0b24f5`,
logs SetForegroundWindow accepted0, then exits after the three-second wait
without a real HWND focus event. Native exit1/controller1, IL2CPPctors0;
the new label calls and original nativeRender were not reached. No draw,
swap or game image. Inputs SHA256
`689884e86c3bf9f8a1ab541ac14c1b57ebf7f29bebcdf2ccf785fed895007bed`;
log SHA256 `3e22d5c3f8a495767062fd3a38cdf5778d5b836054b4f5ba0dcc6919a7148fd1`.
The next diagnostic increases only --first-frame's observed-focus wait to
60 seconds, retaining the default three seconds and every real focus check.
The same qualified GL/collector/affinity sources and all27 receipts remain
unchanged. An actual window activation can then deliver the OS focus event;
no guest focus is synthesized. Next startup: `work/windows-first-frame-label2`.

The preceding execution frontier was a missing native graphics object-label setter.
Actual build `work/windows-first-frame-storage1`, host
`86e55e87e0310f27e3b2635f97a9c21ddba370c7`, executable
`2225f47d4997c41d89fc7c3756a16f971f339f95454d51a317f8a53521105531`,
passes glTexStorage2D and uploads its first texture through glTexSubImage2D.
It stops at target0/StatePC0, LR `7047b1c4`. The outer function calls the label
helper, which restores its frame and tail-branches through slot `0x340`
(glObjectLabel, core/KHR) or `0x360` (glLabelObjectEXT). Both reached lookup
names returned0. The two APIs copy label text with different length rules;
the next batch adds exactly those setters, using native getter oracles only
in the component test. Native exit3/controller1; still no original draw,
successful swap, nativeRender return or game image. Inputs SHA256
`72400b52457eafd0c7d63873365f250dfc4e694fac936dddeb688a71a271a6fd`;
log SHA256 `d97188caad1f9c301e8750b2786df53f7a31a48f1b67efcc530a791e585289a2`.
Bounded audit: `work/storage1-next-texture-boundary1/summary.json`, SHA256
`d96bb6081f7202fabfc1b291af10c4ef0ad555e3acd7aaa483e869a4adb22a1b`.
Because the helper tail-branches after restoring its frame, the fatal LR
cannot establish which of the two label slots was selected at runtime.
The first label component gate passes653 checks/56 NDK calls/53 records
through7 heads and2 objects. Both setters match native byte/length and error
oracles, including NULL/explicit/NUL conventions, embedded NULs, guard edges,
copy lifetime, invalid-object-before-copy ordering and duplicate pending
errors. Actual native maximum label length is1024. Old126 markers remain
exact and two setters append to128; no label getter or unobserved alias is
exposed to the guest. Receipt: `work/gl-label-qualification1/acceptance.json`,
SHA256 `95afb7768194d0c319c5c28846f795e2df0c16bcdf87aef62ecfed22e5d3d6b8`.
The next actual startup is `work/windows-first-frame-label1`.

The preceding execution frontier was missing `glTexStorage2D` during texture creation.
Actual build `work/windows-first-frame-getaffinity1`, host
`f9506de773d3ebca8796802c18627d8278db9b69`, executable
`9cac123d3243ecd24092409cb4250f27a03b4653b237a957f289bbb2186c8ba3`,
passes public sched_getaffinity and both observed worker sched_setaffinity
calls with result0. It then creates a native texture and configures swizzles,
filters and mip bounds before unresolved target0, StatePC0, LR `7048e8e4`.
Original FDE `7048e20c..7048e8e8`, BLR `7048e8e0`, loads slot `0x520`;
both core and EXT-alias lookups for that slot returned0. The same FDE contains
the related TexStorage3D/2DMultisample/3DMultisample calls. The next batch
adds those four pointer-free native storage APIs in a separate typed table,
preserving all122 old marker indices and143 query rows. Native exit3/controller1;
still no original draw, successful
swap, nativeRender return or game image. Inputs SHA256
`b162795ca33e24d571f5a548baff806c7bcfa881f65f9bf915be2b50d199f711`;
log SHA256 `60771f392b31b59d841420a88cac94850df34169d591a2ad081172cc1ba792b8`.
Bounded audit: `work/getaffinity-texture-creation-boundary1/summary.json`, SHA256
`aa09808757057f8841968866ae6762442970be95e6cbb7c76298a51ab853838c`.
Optional EXT lookups are skipped when the core pointer is valid, and null
EXT results never replace a stored pointer; no alias bridges are required.
The first storage component gate passes858 checks/61 NDK calls/42 records
through10 heads and2 objects. The actual native context is GLES3.2; all four
families have positive allocations, with mip/sample/immutable metadata and
initialized FBO pixels/MS resolve checked against direct native calls.
Low8-bit boolean ABI, invalid arguments, poisoned unpack/PBO state, pending
errors and all122 old markers also pass. This is component QA, not a game
frame. Receipt: `work/gl-storage-qualification1/acceptance.json`, SHA256
`ed195460a007e66e52cd3cbf912276fb54986b01be8ca9fd5ae13153c07bc873`.
The next actual startup is `work/windows-first-frame-storage1`.

The preceding execution frontier was the missing public Bionic
`sched_getaffinity` import. Actual build `work/windows-first-frame-window-manager1`, host
`51046016c712835c3f6fdebec6a14e7be59639fc`, executable
`cda0ecb26b831df800b4623d300fc6cdc079e54699543f8d3470453c3d75bbbd`,
passes the repaired Activity/WindowManager/Display chain and reads the actual
associated output at3840x2160,224 DPI and120/1 Hz. It then stops at
`sched_getaffinity`, captured LR `708f173c`, PID `0x1bf95c`, size128.
Native exit3/controller1; still no original draw, successful swap,
nativeRender return or game image. Frozen inputs SHA256
`6e317a725626bd74f403602812e70b70b542a66fb27b1d09f07d08a267614adf`;
log SHA256 `cd20d800694b82efc794c87450832a965a7f9e0c369d13c18dd7a7e72ead30e1`.
The bounded caller zeroes128 bytes atSP, calls the public getter for the
current native TID, ignores its return and scans for the first clear CPU bit.
Its count is a trailing-one prefix, not a popcount; no dense mask or CPU count
may be fabricated. The next addition is an owned-thread Windows affinity
query with the public Bionic return and output-buffer contract. The immediate
worker caller also conditionally reaches the adjacent public128-byte
`sched_setaffinity` helper, BL `708f17d8`. That companion is included in the
same build with actual native mutation and readback; its execution has not
yet been observed. The existing raw four-byte affinity syscall stays exact.
The public Get/Set gate passes599 Windows checks and28 records through8 NDK
heads, with26 Bionic return/errno records matched. The existing Windows raw
setter regression passes158 checks/32 records against the new provider.
Receipt: `work/affinity-public-qualification2/acceptance.json`, SHA256
`d53e2045cba776791bf684e17674cc8020dfd9eb03e4b3b0d190932a163deb26`.
Q1 retains a fixture assumption failure about partial copies; Q2 compares
effects with an independent same-size native copy. Provider sources stay
unchanged. The next actual startup is `work/windows-first-frame-getaffinity1`.

The preceding execution frontier was the absent legacy Android display JNI chain.
Actual build `work/windows-first-frame-vao-query1`, host
`5525d90ef65ab7576a9f11ce43ceb1fab9514659`, executable
`12c64eddda4740428140ce8e5af1a08131183ce6be5e7b4982e09c305c9e5e17`,
passes VAO setup and creates/uploads native GPU buffers. Missing NativeActivity
and WindowManager metadata leads to null method/receiver errors in the
Activity.getWindowManager → WindowManager.getDefaultDisplay → Display refresh
chain. Native exit5/controller1 is a null8-byte read in __remill_read_memory_64;
the exact final guest instruction is not proven. Original static teardown can
leave a JavaVM field null when that display setup fails. There is still no
draw, swap, nativeRender return or game image. Pinned audits:
`work/first-frame-vao-display-jni-boundary1/summary.json` (`bede3e4b…f7628a`)
and `work/vao-query-native-av-audit1/summary.json` (`21f2fd75…a9eb4c`).
The next build adds the two real JNI methods and NativeActivity inheritance
metadata, using the existing Windows display provider and a weak reader for
the actual owned HWND. Its monitor/device selects the existing Display object;
no primary-display assumption or invented hardware values are used. Existing
topology, caching, refresh, SDR and host-scheduling policies remain exact.
Reader qualification passes300 checks; display-chain qualification passes165
checks through19 NDK heads and observes one native associated output at120/1 Hz.
Receipts: `work/native-window-reader-qualification2/acceptance.json`, SHA256
`9c3d4e4e09613cebecdfc1316253f60e112e47b0cd4ae02055f2ab849f402e0c`,
and `work/activity-window-display-qualification2/acceptance.json`, SHA256
`3f4ed33364a5562c36c9e4d1e430fceeb8df33732189b330fb2ea39215e94781`.
ReaderQ1 preserves a minimum-window-size fixture failure, fixed only by using
supported320x240 test windows. DisplayQ1 preserves a new callback error-path
bug; Q2 reports Java errors for invalid/closed/expired backing. No original
guest function, Runtime, JNI core or GL command changes are included. The next
actual startup is `work/windows-first-frame-window-manager1`.

The preceding execution frontier was missing `glIsVertexArray`, original BLR
`70490734`, captured State LR `70490738`. Actual build
`work/windows-first-frame-renderer-state1`, host
`1c5c247fa310e3a567b959181148490a5fc56ee3`, executable
`165c5098c93ea05bcc75ade8d247930e0102a7abc383b9df804a7b1eb6869521`,
advances through sampler/indexed-buffer reset and texture/framebuffer state.
Native exit3/controller1; still no draw, swap, nativeRender return or image.
Loader slot `0x610` and its zero dlsym result identify the captured call.
The exact wrapper FDE returns a GLboolean for a GLuint name. Its bounded
continuation uses existing Gen/BindVertexArrays and DisableVertexAttribArray;
no other missing name was found before initialization returns. The actual
queried name, context values and result remain unobserved.
Audit: `work/renderer-state-vao-query-followup1/summary.json`, SHA256
`08a9a654b1e4d0d443a00fa1f50d7e1e13f1b141b7f237e40151bdfa4120cd82`.
The next addition is that native boolean query, tested within the existing
draw fixture. Its first gate passes544 checks,33 NDK boolean calls and10
lifecycle records, including native zero/reserved/bound/unbound/deleted/
arbitrary/context-local behavior, function-pointer/procedure paths, narrow
return ABI and pending errors. Existing draw/readback/guard/sharing/tracked
write controls also pass. Receipt:
`work/gl-vao-query-qualification1/acceptance.json`, SHA256
`ffe5f99b0e8c37f23b44b0780eacc4219d2eb66961f90c2cabe442150cd1d8f5`.
The next actual startup is `work/windows-first-frame-vao-query1`; the
component's synthetic draw is not an original game frame.

The preceding execution frontier was missing `glBindSampler`, original BLR `70491348`,
captured State LR `7049134c`. Actual build
`work/windows-first-frame-internalformat1`, host
`e1ad2955559b3281883a41c43d0d553f3280b16c`, executable
`3193cc0e58701a0cb226a5b9c6291111c326041adadcb65d1a24dd6caa76c514`,
passes internal-format initialization and reaches VAO creation and renderer
depth/blend/stencil/cull state. The new failure diagnostic reports target0,
StatePC0 and LR `7049134c`; original loader slot `0x738` maps to the observed
zero-result `glBindSampler` lookup. Native exit3/controller1; still no draw,
swap, nativeRender return or game image. The exact bounded audit is
`work/internalformat-renderer-state-followup1/summary.json`, SHA256
`efb2b72a996b10aa616457af98dc9f50e967738fa9bdc4fc3679ec56de486048`.
The same FDE has four later guarded `glBindBufferBase` sites with a zero
lookup. Other subsequent GL slots in that FDE resolve nonzero. Their later
execution is not claimed. The next batch covers the four observed sampler
APIs and that indexed-buffer binding API. Both first driver gates pass:
samplers301 checks/39 NDK calls and indexed buffers947 checks/110 NDK calls.
Receipts are `work/gl-sampler-qualification1/acceptance.json`, SHA256
`421eb25c3a54ee71897b8f92e17fb7dcd92db68c52b7b513ee762034bad787b5`,
and `work/gl-buffer-indexed-qualification1/acceptance.json`, SHA256
`bce4fc573e6eccecd8aa1dbe313b933cd6d13561e03b2e4c8732b9df8d54d2e7`.
Both compile the same held composition, preserve the old116 marker prefix
and143 query rows, and append five markers to121. The existing indexed
guest-query whitelist and Runtime remain unchanged. The next original
startup build is `work/windows-first-frame-renderer-state1`.

The preceding execution frontier was unresolved indirect target0 after the default
framebuffer properties query. Actual build
`work/windows-first-frame-platform-query1`, host
`87bc34552f720aeab334e13ca51684597eb25697`, executable
`7c2f5051f61cf3e7d192e7ac9bcfc9eff9be947eeed32ca40596606de1d6b1e6`,
records231 GL entry attempts and2758 paired EGL calls. Its final eight
queries are RGBA/depth/stencil bits and SAMPLES/SAMPLE_BUFFERS; the final
logged original return is `7048db74`. The previous ID/RELEASE/INCREMENTAL
missing-field errors are absent. Native exit3/controller1, with no draw,
swap, nativeRender return or frame PNG. The fatal diagnostic does not
capture guest State PC/LR/SP, so its exact null caller remains unattributed.
Saved audit: `work/first-frame-platform-query-null-boundary1/summary.json`,
SHA256 `2ed82eb5087f2acea9119d913e0c98dc84010e0c679f1904ffc1acbe6f0723b3`.
The next build adds one failure-only Runtime line printing target and State
PC/LR/SP before the existing unresolved-target abort. Exact inverse proof
recovers the previous Runtime byte for byte, and runtime.h is unchanged.
Linux and Windows each pass97 prior checks, five prior fatal cases and
two new zero/nonzero target cases. Qualification:
`work/runtime-unresolved-diagnostic1/qualification4/acceptance.json`, SHA256
`ca33662cafb9743a433972d84be2aaedbb0a698581115cf3b9f2ae5e66dc91cd`.
The corresponding source-pin supersession passes19 cases, including16
tamper rejections; old receipts and archives remain unchanged. State PC
may be a next-PC value and does not itself identify a failing instruction.
The bounded static caller walk identifies `glGetInternalformativ` as the
next candidate: its loader result is zero at slot `0x758`, and the subsequent
format-init path calls that slot at `7048c114`, using GL_RENDERBUFFER,
GL_SAMPLES and capacity8. This is static attribution, not a captured fatal LR.
The new appended marker115 bridges only GL_NUM_SAMPLE_COUNTS/GL_SAMPLES,
using native validation and exact bounded output publication. It passes384
real ANGLE checks,61 NDK calls and48 native-oracle records, including the
old115 marker prefix, typed service/procedure lookup, guards and tracked writes.
Receipt: `work/gl-internalformat-qualification2/acceptance.json`, SHA256
`e8bbd6d2674bbed4d8d74491ce6794e6ce44083ad0c6ffb2ec2ce8176338babe`.
The first component attempt is preserved; its assertion incorrectly required
a zero-count format on this driver. The corrected fixture reports native
count3 for all three formats and does not claim that branch was exercised.
Capacity-zero and truncated/full-output paths are covered. Production code
is unchanged between those component attempts. The next actual startup is
`work/windows-first-frame-internalformat1`.

The preceding execution frontier was `glGetIntegerv(GL_RED_BITS=0x0d52)`, original
return `7048dafc`, is rejected before native forwarding because its width
is absent. Actual build `work/windows-first-frame-gles-core1`, host
`981cea5f75ba130ec746d0aef8f0a72ab5b38ccd`, executable
`62caf1fafe673db1abe4a56f90e3f55d4d490b600c44b3db60d006a34f53f03a`,
records224 typed GL attempts and2758 paired EGL calls. It advances through
the three indexed workgroup-size queries at indices0/1/2 and past the
capability scan. Native exit3/controller1; no draw, swap, nativeRender
return or game PNG. Saved audit:
`work/first-frame-gles-core-bit-width-boundary1/summary.json`, SHA256
`33d5898978d47cf7e9d5e3cdba7c85a62fdecb7422839b4b3c50124c538c9fcc`.
The six adjacent original queries are RGBA/depth/stencil bit counts.
Their additive width repair passes1190 actual NDK/ANGLE checks,
137 old rows preserved as a prefix of143; all graphics implementations
and fragments are unchanged. Receipt:
`work/gl-framebuffer-bit-width-qualification1/acceptance.json`, SHA256
`656d489a557627e538b6193cf1b78a06de7072d4cbf28006c972fd9abc1f057f`.
This run also requests static String fields RELEASE, ID and INCREMENTAL;
each missing-field exception is cleared before the terminal GL query.
The qualified profile now supplies `Build.ID`, `Build$VERSION.RELEASE` and
`Build$VERSION.INCREMENTAL` using each property's AOSP absent-value default
`"unknown"`. It reuses the existing VERSION class and retains SDK33 and its
field identity. The first actual NDK/JNI gate passes89 checks on each of
Linux and Windows, including old MODEL/MANUFACTURER behavior, class/type
ownership, UTF8 lifetime and the negative BRAND probe. Receipt:
`work/build-info-qualification1/acceptance.json`, SHA256
`7bab3d58a32c84b8840abdb982a0622f9fd37c6e45549a9031a22b6022bca2e2`.
No Android release or device identity is inferred. The next actual startup
build combines both repairs: `work/windows-first-frame-platform-query1`.

The preceding execution frontier was unresolved indirect graphics target0 after
`glGetIntegerv(0x90eb)`, original return `70488458`. Build
`work/windows-first-frame-gles-query-width1`, host
`d781f6afddefd2bdf61e5d5c15a6f42e4be8d726`, executable
`c47520ea749abf5377b5d0874a497c160a76f7a202eb0a6be026957fe9057990`,
passes the previously rejected three scalar SSBO widths and records204
GL entry attempts and2758 paired EGL calls. Native exit3/controller1;
there is no swap, frame PNG or nativeRender return. Static following
BLR at `70488474` loads table slot `0x5f8` with enum `0x91bf`, index0,
then repeats indices1/2. The runtime did not capture the failing guest
PC/LR; attribution of this null target remains a static inference.
Read-only audit: `work/first-frame-gles-query-width-boundary1`, summary
SHA256 `951857451feae6b4a5455791465b97e040c22bd4bb13be6138979d81ff9ddde2`.
The next provider batch covers51 observed missing GLES2 core names and
the narrow indexed compute-limit getter, appended after the old63 markers.
All six real ANGLE/NDK component gates pass: textures270 checks,
uniforms1923, framebuffer/renderbuffer168, miscellaneous290,
indexed limits88 and the expanded115-export service module192.
Receipts are `work/gl-texture-qualification2`,
`work/gl-uniform-qualification1`, `work/gl-framebuffer-qualification1`,
`work/gl-misc-qualification1`, `work/gl-indexed-qualification1` and
`work/gl-core-module-qualification1`, each `acceptance.json`.
Texture qualification1 is preserved: it expected a poisoned compressed-PBO
upload to succeed, while actual ANGLE rejects it. Qualification2 corrects
only that fixture expectation with a native error oracle and a separate
valid upload/texel comparison; production code is unchanged.
The central source projection preserves every old implementation and
query row. Source proof: `work/gl-core-composition-preparation1/source-proof.json`,
SHA256 `05c093adcb92d5f6b455d61e3b84fce1fe0467816bfdf409abf2cb91d8c1cf4d`.
These gates establish component behavior, not an original game frame.
The next actual startup build is `work/windows-first-frame-gles-core1`.

The preceding execution frontier was missing scalar query width for
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
format-only change. That repair is exercised by the build above.

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
