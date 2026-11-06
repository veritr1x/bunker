# Typed indexed draw variants

Run22 reaches the original five-argument base-vertex draw with mode `4`, count
`1758`, unsigned-short indices at byte offset `24`, and signed base vertex `8`.
The original GL function-table slot `3e8` is null because the typed provider
omitted both `glDrawElementsBaseVertex` and its OES alias. ANGLE itself supports
and exports them. The adjacent instanced draw slots are also missing.

The provider appends ten command markers: ordinary `glDrawElementsInstanced`
and core/OES/EXT versions of base-vertex, instanced-base-vertex and
range-base-vertex indexed drawing. Existing markers retain their indices.
Each binding uses the genuinely named ANGLE export with the correct typed
signature, including signed `GLint` base vertices and all seven range arguments.

The existing GPU-only policy remains: enabled attributes require VBOs and indexed
drawing requires an EBO. Index arguments remain byte offsets into that EBO.
Counts, instance counts, index types, range bounds and signed bases are forwarded
to the driver; the bridge does not copy CPU index arrays or emulate the draw.
The ordinary indexed-draw implementation remains unchanged. New commands enter
the existing error, native floating-point environment and diagnostic machinery.

Focused verification uses actual typed marker dispatch and genuine ANGLE
framebuffer/error controls. Synthetic triangles in that fixture qualify the
bridge only. They are not original-game frames. Component qualification and
the next original startup result are recorded separately.

Focused qualification Q4 at `work/gl-base-vertex-focused-qualification4` passes
1,759 checks: 101 exact native pixel/error comparisons, 60 explicitly nonuniform
draws and 20 GPU-buffer policy rejections. All ten APIs, signed bases, byte
offset 24, instance counts and range arguments execute through the State1200 /
Memory64 runtime bridge against the selected ANGLE provider.

`work/gl-base-vertex-regressions-final1` records 2,090 checks across query,
current EGL scaling, scalar, module and capture fixtures. Query and scalar use
documented one-literal fixture copies to replace a stale unavailable-name probe;
canonical fixtures remain intact. The current module test uses a matching fresh
tiny NDK caller. Older fixed-count/scaling assumptions and the unrun legacy draw
fixture are explicitly excluded, with failed attempts preserved. These checks
do not establish an original game frame.
