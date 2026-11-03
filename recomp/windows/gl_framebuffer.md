# Framebuffer and renderbuffer commands

This additive group exposes the twelve observed GLES2 core entry points through
the same owned EGL context and pinned ANGLE module as the existing GL provider.
Native ANGLE owns GLuint allocation, storage, attachments, completeness, error
flags and deletion. The adapter does not synthesize framebuffer success or keep
a second object registry.

`gl_framebuffer_commands.inc` is an append-only command group. Central integration
must append it after the existing 63 commands and any preceding new groups,
declare/load its native fields with the `framebuffer_` prefix, include
`gl_framebuffer_impl.inc` inside `GlHost::Impl`, and call
`BindFramebufferCommands()` from `Bindings()`. The existing scalar and draw row
order stays unchanged.

Generation uses the existing bounded `Generate` helper. Deletion snapshots the
guest GLuint array through `DeleteNames`. Both object getters use a native local
GLint and publish exactly four tracked guest bytes only if the native query
succeeds. They do not expose driver pointers or widen general `glGet*` outputs.
Pointer-free commands forward their typed arguments and native results.

The existing default-window capture and guest `glReadPixels` restrictions remain
unchanged. An offscreen framebuffer is not a presented window. Object cleanup
runs through explicit native deletes while its context is current, or through
native context lifetime; no wrong-context provider-destructor deletion is added.

The focused fixture is drafted, **not yet executed**. It compiles actual NDK
callers and compares their translated calls against direct native ANGLE in a
separate owned context. It covers real RGBA4 storage, completeness, nine
renderbuffer and four texture-attachment query parameters, 2D/cube-face
attachments, guarded output arrays, native validation/errors, bound deletion,
and actual tracked-memory write/read behavior. Native-only texture creation and
FBO clear/readback are explicitly fixture setup/observation, not guest texture or
non-default-FBO readback qualification. There is no ARM GPU, capture restoration,
game, or presented-frame claim from this component fixture.

After shared integration is ready, invoke `test_gl_framebuffer.py` from WSL with
explicit `--ndk`, `--lift`, `--semantics-dir`, `--remill`, `--angle`,
`--support-source`, and a fresh `--out` directory. The controller freezes support
sources, compiles strict NDK and native fixture sources, records real native
output, and retains a failing output directory rather than reusing it.

Contracts: the pinned Khronos GLES headers and official GLES2 reference pages
for [renderbuffer queries](https://registry.khronos.org/OpenGL-Refpages/es2.0/xhtml/glGetRenderbufferParameteriv.xml),
[attachment queries](https://registry.khronos.org/OpenGL-Refpages/es2.0/xhtml/glGetFramebufferAttachmentParameteriv.xml),
and [renderbuffer deletion](https://registry.khronos.org/OpenGL-Refpages/es2.0/xhtml/glDeleteRenderbuffers.xml).
