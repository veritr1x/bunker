# Original IL2CPP save-only helper component

This NEW isolated variant follows the accepted corrected stack4 diagnostic.
It calls original825b0544 through a strict translated Android NDK caller and
an explicitly synthetic translated callback. It is not a collector callback,
root scan, collection, suspension, managed initialization or nonlocal transfer.

The original100-byte function creates its actual0x140-byte frame, clears its
own256-byte environment atSP+8, calls real setjmp, then invokes the callback
with the original opaque argument and zero. The callback observes actual high
frame spills and real saved wire state while that frame is live. Nonzero seeded
X19..X28 and lowerD8..D15 values exercise normal ABI preservation. Current FPCR/
FPSR/system flags are observed separately; the Bionic wire does not claim to
save FPCR/FPSR/NZCV or upper SIMD lanes.

The original helper Entry is forwarded unchanged. Its observed automatic
environment has an invocation-specific owner generation and exact256-byte
range inside the actual Pthreads stack. On return from that original Entry,
the forwarding wrapper revokes this owner and calls NonlocalJumps::Forget
BEFORE returning to the suspended outer NDK caller. The stale registration is
then rejected without reading expired environment bytes. Thread retirement is
additional cleanup, not this automatic object's lifetime authority.

Original87cb1e60 receives the actual environment pointer after the callback.
The raw value remains untouched after the automatic object expires. It is
never dereferenced as a surviving root, reset to fabricate pristine state, or
used after thread retirement. No process-reuse or general GC-root claim follows.
The actual bound SignalHost mask is saved and restored; no signal is delivered.
The selected USR bits are blocked on top of the observed existing mask, retaining
the real Android-reserved timer bit. The first candidate's incorrect exact-mask
expectation stopped before the original helper and is preserved separately.

Nine real constructors, the existing actual stack-top helper, both reverse
finalizers and TLS/token cleanup remain in the gate. Init/GC/record flags and
all256 thread buckets stay pristine. Missing old entry825b0580 is not needed
for the original trace's normal inline setjmp return; no dispatch or longjmp
to that saved continuation is attempted.

The preparation script requires a fresh directory and the exact corrected
stack4 input/executable. It copies frozen sources, headers and the accepted
3079-object/validated01066-overlay composition, adds only the new harness and
strict disjoint fixture, and compares recursive LLVM State layouts. Old engine
objects are never rewritten. Current full-IL2CPP refresh/parity remains separate.
The test reverifies all old artifacts, frozen source/header/support files,
strict fixture objects and executable before/after, and checks fixture-hash
rejection before constructors. Callback/import failures terminate explicitly;
no C++ exception unwinds through lifted nounwind frames.

Prepare in WSL with il2cpp_save_prepare.py --base-build CORRECTED_STACK4 --out
NEW_DIRECTORY --ndk NDK --lift FROZEN_LIFTER --semantics-dir FROZEN_SEMANTICS.
Build using il2cpp_save_build.ps1 -BuildDirectory NEW_DIRECTORY, then run
test_il2cpp_save.py --build NEW_DIRECTORY --apk ORIGINAL_APK from WSL.
