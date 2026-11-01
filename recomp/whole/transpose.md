# SIMD transpose gate

The Remill fork implements `TRN1` and `TRN2` for 8B/16B, 4H/8H, 2S/4S and
2D arrangements. It reads both sources before writing, supports overlapping
registers, and clears the unused upper Q-register bits in 64-bit vector forms.
The existing permutation decoder also rejects the unallocated 1D arrangement.

On November 2, 2026, `test_transpose.py` matched **17,920 original AArch64
reference records on each of native Windows x86_64 and Linux x86_64**.
Seventy variants cover both operations and all arrangements with distinct
registers, either destination overlap, identical sources, and all registers
identical. Snapshots include source/destination Q registers and output canaries.
Both fixtures lift to 70 traces with zero unsupported traces or unresolved
direct targets. Frozen toolchain hashes are in ignored
`work/transpose-{linux,windows}/result.json`.

Run from WSL with LLVM 18 and the reference cross-toolchain/sysroot:

```sh
python recomp/whole/test_transpose.py \
  --reference-root /path/to/reference-tools/root \
  --remill /path/to/remill-src --lift /path/to/remill-lift-18
# Add --windows for the native MinGW executable.
```

This adds no structure stores or other permutation operations. Existing engine
objects retain their frozen semantics until refreshed.
