# Proven setjmp continuation roots

nonlocal_roots.recover(elf) is an analysis API. It returns entries,
continuations, unresolved and summary. Addresses are ELF virtual addresses,
before the caller adds its chosen guest load base. Each accepted continuation
records the call site, API name, post-call entry and complete import proof.
The compiler uses it by default and implements no longjmp transfer.

Only an aligned direct AArch64 BL to a proved undefined setjmp, _setjmp or
sigsetjmp import seeds site+4. The entire next four-byte instruction must be
inside allocated executable code. The import proof follows a real
R_AARCH64_GLOB_DAT or R_AARCH64_JUMP_SLOT relocation to a 64-bit GOT load and
BR in a decoded PLT sequence. It reuses the register/constant provenance
machinery from callback_roots.py, preserving Base+RVA provenance. No fixed PLT
stride or symbol-order assumption is used. BTI and bounded padding are allowed.
The relevant primary reference is Arm's
[ELF for AArch64 specification](https://github.com/ARM-software/abi-aa/blob/main/aaelf64/aaelf64.rst).

Nonzero addends, duplicate slot relocations, misaligned/unallocated slots,
object symbols, arbitrary data relocations, 32-bit pointer loads and numeric
GOT-looking addresses do not prove import ownership. Undefined FUNC or NOTYPE
symbols can be imported entries; defined symbols are identified as owned local/
interposable functions and excluded, including a defined setjmp shadow. Stub
decoding stops at unknown effects, authenticated branches or unproved loads.
Section headers and recognizable .plt/.iplt sections are required; an image
without those proofs does not get guessed roots.

A direct tail B has no local post-call continuation. BLR remains unresolved
even if its surrounding code happens to look suggestive. The report includes
all indirect BLR calls as unattributed observations, with api=null. These are
not assertions that thousands of setjmp calls were missed. The scan does not
prove reachability of every executable word. Its scope is conservative root
availability, not a whole-program control-flow or nonlocal-unwind proof.

The actual Unity ELF has SHA256
3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f.
It contains 49 proved direct setjmp calls and 34,257 unattributed BLR calls,
with zero unproved PLT calls, tail-setjmp calls or invalid post-call PCs.
The observed surface call is proved as:

- site RVA 0x43a048, return RVA 0x43a04c;
- undefined STT_FUNC setjmp, JUMP_SLOT relocation 1026 at GOT RVA 0x123e920;
- actual PLT RVA 0xb92b0: ADRP X16, LDR X17, ADD X16, BR X17;
- guest continuation 0x7043a04c at the existing 0x70000000 load base.

The current Unity trace header contains entry 0x7043a014 but lacks that return
PC. No Unity object/manifest was refreshed by this task.

The actual IL2CPP ELF SHA256 is
ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522.
It has one proved setjmp continuation: site RVA 0x25b057c, entry 0x25b0580,
PLT RVA 0x20caba0 and GOT RVA 0x740ba50. Its 112,393 unattributed BLR calls
remain unresolved; there are zero unproved PLT calls or rejected direct
setjmp tails. This evidence does not show that execution reaches that call.

test_nonlocal_roots.py builds stripped fixtures with the actual NDK. Fifteen
static cases cover all three APIs, variable-length padded/BTI PLT, tails,
indirect calls, wrong/defined imports, nonexecutable return PCs and the malformed
relocation/load/provenance cases above. The return PCs have neither exported/
local symbols nor containing unwind FDEs.

On native Linux and Windows, both normal and padded fixtures reproduce missing
entry dispatch in a baseline build. The recovered build dispatches
all three return PCs and passes 18 checks per variant, 36 per host, for actual
effects, return value, callee register, SP, PC and registered entry. Tests prepare
the explicit starting State/stack for that availability check; they do not
perform a setjmp/longjmp cycle. Unexpected import execution aborts. No exception
crosses a lifted nounwind intrinsic.

compile.py rebases proved entries into its normal seed/trace-head set and
records nonlocal_roots.enabled/entries/continuations/unresolved in both plan
and final manifest. --no-nonlocal-roots provides a diagnostic baseline. Every
returned entry is independently checked for aligned, complete executable bytes.
Resume cache keys already include seeds and all known trace boundaries; changing
the root option therefore invalidates incompatible shards. Tests exercise the
real CLI default/opt-out, unchanged resume and toggling roots in the same output.
test_nonlocal_compile.py adds 52 plan/manifest/rebasing/CLI checks, including
independent callback flags, analyzer bypass when disabled, and rejection of
forged unaligned, nonexecutable or truncated instruction roots.
Ignored work/nonlocal-roots-{linux,windows}
contains static reports, per-ELF audits, baseline/recovered manifests and native
results. Saved execution lifetimes, actual engine refreshes, mask commit and
controlled unwind/dispatch remain parent-owned work.
