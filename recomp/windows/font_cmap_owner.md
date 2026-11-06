# Original Unity font cmap automatic environment

The Runtime14 fatal occurs while saving a new setjmp buffer, before a saved
allocation generation is compared. Its logged address, `0x1e667690430`, is inside
the registered thread stack `[0x1e667591000, 0x1e667691000)`. Neither the mmap
owner nor the existing IL2CPP-specific automatic-object certificate admits this
buffer. This is a missing automatic invocation owner; widening admission to an
entire stack would not establish the buffer's lifetime.

The original Unity FDE is `708d905c..708d92a8` (588 bytes). It allocates a
`0x1a0`-byte frame and calls the actual setjmp PLT at `708d923c`, with return PC
`708d9240` and environment `SP+0x10`. The original ELF's dynamic relocation
identifies that PLT as setjmp. The 256-byte environment fits within the frame.
The loop can save the same buffer for successive records; empty, invalid-version
and unknown-format input can return without saving it. The structure and calls
match FreeType's [tt_face_build_cmaps](https://android.googlesource.com/platform/external/freetype/+/f720f0db/src/sfnt/ttcmap.c).
This identifies the operation by correspondence, not an assertion of the exact
FreeType source revision used to build Unity.

`GameFontCmapEnvironments` wraps the actual selected original entry. Every
invocation receives its own owner identity, virtual thread token/generation,
fresh invocation generation, entry SP and return PC. Only the exact original
setjmp return PC, `SP=entrySP-0x1a0`, and `environment=SP+0x10` establish this
object. Repeated saves must name that same environment. A true function return
must restore its actual entry SP and return PC; retirement forgets the save if
one occurred. Native exception escape revokes bookkeeping and remains a failure,
not a guest continuation. Thread storage destruction only deletes passive
metadata and never invokes guest/provider cleanup.

The selected trace table, the exact linker-wrapped `sub_708d905c` symbol and the
static `__bunker_guest_call` fast path select the same owner. The original guest
body and its callbacks still execute. The existing IL2CPP automatic owner and
the shared guest-call routing header are unchanged. The additional link flag is
`-Wl,--wrap=sub_708d905c`.

This adds no arbitrary stack, heap or file-mapping admission. It does not enable
longjmp: the existing guard remains in place. A future real validation error
must use a separately qualified restored-State transfer with truthful signal
mask semantics; it must not be converted into a fabricated successful result.

Source preparation and original static proof are recorded in
`work/font-cmap-owner-preparation1`. Qualification Q5 at
`work/font-cmap-owner-qualification5/acceptance.json` passes 267 focused checks,
including six executions of the selected original FDE compared with six real
Bionic cases, repeated saves, early returns and 18 negative checks. The unchanged
nonlocal provider also passes 563 existing checks, 512 NDK caller records and the
separate original-assembly save/restore reference.

Q5 binds bootstrap `cb127e94` and detail header `b0e4202e`. The later combined
bootstrap `295596a4` additionally stages the original APK Firebase configuration.
`work/font-firebase-integration1/font-integration-addendum.json` proves that
strictly removing that isolated block and its iterator include recovers the
entire tested font bootstrap. It does not claim that Q5 functionally tested the
new SDK setup block or the entire combined bootstrap. An original game run is
still required, and no visible game frame is claimed here.
