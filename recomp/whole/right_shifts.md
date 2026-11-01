# Immediate SIMD right shifts

The Remill fork now implements vector `USHR` and scalar/vector `SSHR` for
allocated ARMv8 forms: 8B/16B, 4H/8H, 2S/4S, 2D and scalar D. Existing scalar
`USHR` remains covered. The decoder rejects a zero `immh`, scalar element sizes
other than 64 bits, and the unallocated 64-bit vector 1D form. Shift amounts
are 1 through the entire element width. The semantics guard full-width shifts
explicitly and compute sign fill with unsigned operations, avoiding C++
overshifts or signed-right-shift assumptions. Input is read before destination
publication, and unused upper Q-register bits are cleared.

`test_right_shifts.py` generates 960 normal/in-place instruction variants and
runs 256 varying input patterns per variant. On November 2, 2026, all
**245,760 records matched original AArch64 execution under QEMU on each of
native Windows x86_64 and Linux x86_64**. Snapshots include both source and
destination registers, output canaries, zero/preset cumulative FPSR and
multiple condition-flag states (including all four flags set).
The fixture seeds and reads condition flags with ordinary arithmetic/CSET;
MRS/MSR NZCV remain an independent unsupported system-register feature.

Both translated fixtures contain 960 traces, zero unsupported traces and zero
unresolved direct targets. Ignored `work/right-shift-{linux,windows}/result.json`
records the frozen lifter, semantics and compiler hashes. Run from WSL with
LLVM 18 and the reference cross-toolchain/sysroot:

```sh
python recomp/whole/test_right_shifts.py \
  --reference-root /path/to/reference-tools/root \
  --remill /path/to/remill-src --lift /path/to/remill-lift-18
# Add --windows for the native MinGW executable.
```

This gate does not add rounding/accumulating shifts, shift-long, narrowing,
saturating shifts or variable signed shifts. Existing engine object snapshots
retain their earlier semantics until refreshed.
