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

First-frame acceptance requires an image captured from the original GL
window framebuffer, original drawing activity, a successful original
`eglSwapBuffers`, and a returned original `nativeRender`. A synthetic
triangle or clear-only surface is not evidence of a game frame. The
`--first-frame` diagnostic preserves the image and holds the real window
for ten seconds when its witness succeeds. Audio stays explicitly muted
while the HDMI endpoint is unavailable.
