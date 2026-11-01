# Scalar GLES commands on native Windows

`GlHost` now exposes 28 scalar state/clear commands, in addition to its six
existing query signatures. The append-only catalog is
`gl_scalar_commands.inc`; existing query marker addresses are unchanged.
Each declared guest signature is checked at compile time against the exact
Khronos native function-pointer type from
[GLES3/gl32.h](https://github.com/KhronosGroup/OpenGL-Registry/blob/main/api/GLES3/gl32.h).

The catalog covers active texture, enable/disable/isEnabled, viewport/scissor,
color/depth/stencil clear and masks, depth function/range, separate stencil
operations, blend state, cull/front face, polygon offset, sample coverage,
line width, hint, flush and finish. Calls go to the pinned ANGLE DLL on the
calling thread's real current context. Driver validation and error flags are
preserved; scalar commands do not drain errors. Query-cached errors and later
native command errors remain visible through the existing `glGetError` bridge.

No new command has a guest pointer, output buffer, object lifetime, client
array or mapping to translate. Shader/draw/buffer APIs and guest `glReadPixels`
remain unsupported. Unknown resolver signatures still fail explicitly.

The Windows gate passes **342 checks** with the original pinned Vulkan ANGLE
bundle, without changing either ANGLE bundle. Its actual Android NDK caller
resolves and invokes all 28 signatures through `eglGetProcAddress`; its two
translated traces have no unsupported instructions or unresolved direct
targets. A separate native context runs the same command sequence directly
through driver pointers as an ABI reference. Thirty-six integer/vector state
queries, eight float/vector queries, errors and all 64 RGBA pixels match.
The pixels also match a separately specified scissor/color-mask image.

The gate checks mixed float/GPR arguments, noncanonical true GLboolean bytes,
upper argument padding, zero-extended GLboolean returns, unchanged unrelated
registers, PC/SP, output canaries, accumulated distinct errors, query/command
error interaction and orderly resource cleanup. The existing query fixture
was separately linked against the new host object and frozen support objects;
all **976 checks** still pass.

```sh
python recomp/windows/test_gl_scalar.py --ndk <linux-ndk> --lift <remill-lift> --remill <remill-source>
```

The script runs under WSL, builds with native Windows MinGW and uses the local
`work/angle-native` bundle. An optional `--support-source <recomp-directory>`
freezes a chosen support cohort; the accepted run used Bunker `1942e24` to avoid
concurrent JNI edits. `--semantics-dir` supports an explicit compiler snapshot.
Ignored evidence is `work/gl-scalar/acceptance.json` and
`work/gl-scalar/query-regression.json`, including exact source, object, DLL and
executable hashes. This is a real driver command gate, not a game frame.

Cached errors belong to the actual EGL context, rather than its current native
thread. `GlHost` now borrows its `EglHost`, checks that they use the same GLES
module, and keys saved flags by never-reused provider context tokens. This
fixes errors leaking across same-thread context switches or disappearing when
a context moves to another thread. Deferred-deleted current contexts retain
their flags until unbound; retired-context flags are discarded. A GL call
without an owned current context fails explicitly. Read-only ownership checks
do not consume EGL errors. Tests cover these cases on actual ANGLE contexts,
including migration in both directions and replacement after destruction.
