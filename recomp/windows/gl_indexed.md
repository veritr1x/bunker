# Bounded indexed compute-limit queries

The original loader associates `glGetIntegeri_v` at string `0x70efd5b5` with
its table slot `0x5f8` (store at `0x70473018`). The adjacent original capability
path uses that slot at `0x70488474`, `0x70488494`, and `0x704884b4`, with
`GL_MAX_COMPUTE_WORK_GROUP_SIZE` and indices 0, 1, and 2. These static arguments
do not add unlogged runtime-register claims.

This command is appended after the prior 114 markers. The provider admits only
`GL_MAX_COMPUTE_WORK_GROUP_COUNT` (`0x91be`) and
`GL_MAX_COMPUTE_WORK_GROUP_SIZE` (`0x91bf`), each one GLint. All indices are
passed to actual ANGLE validation; a failed native query preserves guest output
and retains the actual error. A successful result publishes exactly four tracked
guest bytes. Other indexed targets remain named unsupported, including targets
whose other widths have not been qualified. No native value is synthesized.

The first actual fixture execution passes88 checks, receipt
`work/gl-indexed-qualification1/acceptance.json`, SHA256
`09d8be9ba1d3206270a21680f601218e708214b8de5c954ce632f1894e850316`.
It uses strict NDK calls and direct
native ANGLE comparisons for both targets at indices 0..2 and invalid indices
3/UINT_MAX, a four-byte output ending at a no-access page, prior-error
preservation, a real cross-thread guest-exclusive invalidation check, and an
explicit guard against an unqualified target. It performs no compute workload,
ARM GPU comparison, game execution, or frame qualification.

Primary authority: the pinned Khronos `GLES3/gl32.h` typedef and enums, and the
[Khronos GLES3.1 glGet contract](https://registry.khronos.org/OpenGL-Refpages/es3.1/html/glGet.xhtml).
The actual NDK header is `GLES3/gl31.h`; Windows calls the same checked ANGLE
module already owned by the EGL and GL providers.
