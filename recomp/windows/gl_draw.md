# Typed GLES shader and GPU-buffer draws

This gate expands `GlHost` by the 29 exact signatures in `gl_draw_commands.inc`. It runs actual Android NDK callers recompiled to native Windows against the accepted, pinned `work/angle-native/bundle/bin` Vulkan ANGLE build. It does not execute a Unity frame.

The current provider also forwards compute shader creation through the existing
typed `GLuint(GLenum)` native binding. The original game reached stage `0x91b9`
and was stopped by an earlier host policy guard. Removing that guard leaves
native stage validation, errors and context capabilities to the actual driver.
Shader source copying, compilation, program linking/use and reflection already
use the same typed paths. Compute dispatch and workload execution remain outside
this qualification.

`work/gl-compute-stage-qualification2/acceptance.json`, SHA256
`8211a15a1beaa16799578064eeb6caa090009e5b7674ed6a36ec9ff8aae3065b`,
passes592 checks on real ANGLE/Vulkan. Actual NDK direct, pointer and procedure
calls create compute objects and compile/link/query a program against independent
native calls. Invalid-stage errors, scalar widths and the existing vertex/fragment
indexed/array triangle, shader-error, readback and lifetime checks pass. Reversing
the single production binding line recovers the entire parent GL source; command
order, capabilities and capture code remain exact. These tests establish no
compute dispatch or original game frame. The first controller attempt stopped
at a namespace-parser regex before compilation and is retained.

The existing six query and 28 scalar-command marker indices remain unchanged. `eglGetProcAddress` resolves these supported names to installed guest import markers, never native code pointers. Unknown names still fail explicitly.

The Unity bootstrap uses `GlHost::Commands()` for both direct-import selection
and installation of forwarding bridges, covering all 63 supported commands in
the same marker order. Dynamic lookup returns those same installed markers.
This replaces its older six-query-only forwarding list. The updated bootstrap
compiles against the accepted Unity cohort, and the updated GL provider retains
all 286 native draw-gate checks. This integration has not executed a Unity draw.

## Guest memory and ABI

GL enums, GLuint names, signed GLint/GLsizei values and output lengths occupy four bytes; GLboolean occupies one byte; ARM64 guest pointer tables and signed GLsizeiptr/GLintptr values occupy eight. Shader/program query widths are enumerated explicitly, including the three-component compute-work-group-size information query; unknown widths are rejected before touching output memory. Compute shader objects are supported; compute dispatch/execution remains outside the guest bridge.

Shader source tables and optional signed lengths are copied through tracked reads. Nonnegative lengths copy exactly that many bytes, including embedded NUL bytes; negative or omitted lengths use a bounded NUL scan. The native call receives owned staging storage. Buffer uploads likewise snapshot their inputs; NULL `BufferData` allocates native storage, and zero-size/count operations do not read guest arrays. Staging is bounded to 64 MiB per transfer and 4096 shader-source strings. These are explicit host scope limits, not reported GLES capabilities.

Name arrays publish exactly four bytes per GLuint. Query results and logs publish through tracked writes only after a successful native call; log publication includes the actual terminating NUL, excludes the unused suffix, and writes an optional four-byte length. Same-value native output still counts as a guest write. No guest-memory lock spans a driver call.

VAO state, resource deletion, namespace reuse, sharing and GLuint validation belong to the actual ANGLE context/share group. There is no process-global shadow ownership map. `VertexAttribPointer` requires a real nonzero ARRAY_BUFFER and interprets its last argument only as a byte offset. Draw preflight verifies every enabled attribute has a native buffer binding; indexed draws additionally require a real element buffer. Retained CPU arrays, mapped memory, textures, uniforms, framebuffer object commands and compute execution are unsupported.

## Bounded readback

`ReadPixels` currently supports only RGBA/UNSIGNED_BYTE, default read framebuffer zero, no pixel-pack buffer, and a rectangle fully inside an owned current read pbuffer. `EglHost::CurrentReadPbufferExtent` returns opaque context/surface tokens and positive native EGL logical dimensions. It excludes window, foreign, missing and surfaceless bindings; a deferred-deleted surface remains observable while actually current/native-live. Internal observation preserves the existing singular per-thread public EGL error result, including native-pending precedence.

The footprint uses actual pack alignment, row length and row/pixel skips, with overflow and transfer-size checks before allocation or guest access. Row lengths smaller than the read width can overlap. Only the union of actual pixel bytes is published: padding and skipped bytes are not initialized or copied over the guest. Clipped/out-of-bounds rectangles, nondefault read FBOs, PBOs and other format/type combinations produce explicit diagnostics. Window resize races are avoided by excluding window readback rather than inferring extent from viewport state.

Native GL errors are collected into the existing context-owned flag set before internal queries. Preexisting errors remain observable but do not suppress publication from a successful operation. Native validation errors do suppress output publication. Context migration and lifetime retain the previous provider error model.

## Repeatable gate

Run from WSL, with the task venv Python and the installed NDK/lifter paths:

```sh
python recomp/windows/test_gl_draw.py --ndk /path/to/ndk --lift /path/to/remill-lift-18 --support-source recomp/work/windows-unity-native3/source/recomp --regressions
```

The support source is frozen separately from the graphics overlays; the accepted run uses the `92bea35` native3 support cohort. The script writes `work/gl-draw/acceptance.json` with source, binary, driver DLL and compiler hashes plus exact output and regression results. Existing query/scalar/EGL generated fixture artifacts must exist for `--regressions`; their ELF hashes and linked test binary hashes are recorded. No ANGLE bundle is modified.

The accepted native Windows run passes **286 checks** through **10 strictly lifted NDK trace heads**, with zero unsupported traces or unresolved direct targets. The once-only regressions against the same frozen providers pass query **976**, scalar **342** and EGL **49** checks. The driver reports OpenGL ES 3.2, ANGLE commit `890b5d8fa298`, Vulkan on NVIDIA RTX 4090.

The fixture resolves all 29 entrypoints through actual NDK calls, compiles split explicit-length/NUL-terminated shaders, uploads VBO/EBO data, protects all input pages NOACCESS, then compiles/links and renders both array and indexed triangles. All 64 RGBA pixels match an independent raw-native call sequence, with independent red-interior/black-exterior expectations. Invalid shader status/logs, canaries, overlapping pack rows, untouched padding, zero/negative counts, signed buffer sizes, unaligned output, three-component query widths, share-group/local-VAO behavior, program/surface deferred deletion, native/cached errors and cross-thread tracked reservations are covered.

## Primary specifications

- [Khronos GLES registry header](https://github.com/KhronosGroup/OpenGL-Registry/blob/main/api/GLES3/gl32.h): exact native signatures and scalar widths.
- [ShaderSource](https://github.com/KhronosGroup/OpenGL-Refpages/blob/main/es3.0/glShaderSource.xml): pointer/length arrays, exact byte lengths and copy-at-call lifetime.
- [VertexAttribPointer](https://github.com/KhronosGroup/OpenGL-Refpages/blob/main/es3.0/glVertexAttribPointer.xml) and [DrawElements](https://github.com/KhronosGroup/OpenGL-Refpages/blob/main/es3.0/glDrawElements.xml): CPU pointer versus buffer-offset interpretation.
- [ReadPixels](https://github.com/KhronosGroup/OpenGL-Refpages/blob/main/es3.0/glReadPixels.xml): read format/extent, pixel packing and error behavior.
- [GetShaderInfoLog](https://github.com/KhronosGroup/OpenGL-Refpages/blob/main/es3.0/glGetShaderInfoLog.xml): returned length and NUL semantics.
