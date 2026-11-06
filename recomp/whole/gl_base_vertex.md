# GPU-backed indexed draw variants

The Windows GLES provider appends ordinary `glDrawElementsInstanced` and the
core, OES and EXT forms of BaseVertex, InstancedBaseVertex and
DrawRangeElementsBaseVertex. Every bridge calls the corresponding genuine
ANGLE export. The original 153 marker ordinals remain unchanged; ten markers
append. Existing GPU VBO/VAO fences also apply, and indexed draws require an EBO.

The index argument is a buffer byte offset. Base vertex is a signed 32-bit
addition to fetched vertex indices, rather than to that offset. Range bounds
refer to the unshifted indices. These contracts follow the
[Khronos OES specification](https://registry.khronos.org/OpenGL/extensions/OES/OES_draw_elements_base_vertex.txt)
and [EXT specification](https://registry.khronos.org/OpenGL/extensions/EXT/EXT_draw_elements_base_vertex.txt).

`gl_base_vertex_test.cpp` uses the selected ANGLE scaling build and a genuine
GLES3.1 pbuffer. It uploads GPU vertex/index buffers, retires CPU index upload
memory, then compares each typed Runtime marker draw with the same native API.
Cases cover unsigned16/32 indices at byte offset24, base vertices0/+2/-2,
instance counts0/1/2, range bounds, invalid native arguments and GPU-only fences.
The actual State1200-byte ABI, high-word poison on 32-bit parameters, Range's
seventh argument, normal return PC and opaque Memory64 token are checked.

The final focused execution passes1759 checks,101 exact pixel/error comparisons,
60 strictly nonuniform colored draws and20 rejected CPU/EBO cases. It checks
every old/new marker, genuine export availability and an unavailable optional
procedure. Diagnostic submissions increase without creating a presented-frame
PNG. Existing query, EGL, scalar, module and capture regressions are qualified
separately against the same provider and bound by the combined receipt.

Historical failed fixture attempts and the weaker colored-pixel predicate remain
immutable. Qualification4 explicitly requires differing RGBA pixels and reuses
byte-identical provider objects. No translated NDK caller is claimed for this
focused fixture, and its artificial geometry is not an original game frame.
