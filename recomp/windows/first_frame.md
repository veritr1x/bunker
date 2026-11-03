# Native Windows first-frame status

The target is the original game running as a standalone Windows x86_64
executable. A presented game image and working gameplay remain unverified.

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

First-frame acceptance requires an image captured from the original GL
window framebuffer, original drawing activity, a successful original
`eglSwapBuffers`, and a returned original `nativeRender`. A synthetic
triangle or clear-only surface is not evidence of a game frame. The
`--first-frame` diagnostic preserves the image and holds the real window
for ten seconds when its witness succeeds. Audio stays explicitly muted
while the HDMI endpoint is unavailable.
