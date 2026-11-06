# Unity guarded switch entry recovery

Runtime16 reached unresolved interior target `0x701078e8`, with LR
`0x701078cc`. The original Unity FDE is `0x701068d8..0x70107f10`, 5,688
bytes. The selected full-function translation has no unsupported instructions;
its three indirect branches dispatch through original signed relative tables.
Only the outer function head was registered in the selected trace inventory.

The actual failure follows `ldr w8,[x0,#0x18]`, `sub w8,w8,#1`, an unsigned
`cmp w8,#7` / `b.hi` guard, and a signed 32-bit offset load from table
`0x70e7a0c4`. `br x8` at `0x701078e4` reaches the missing first-row target.
This is a computed switch entry, rather than an exception landing pad.

All three guarded tables in the FDE form this closed entry inventory:

| Branch | Table | Guarded rows | Distinct targets |
| --- | --- | --- | --- |
| `0x70106fbc` | `0x70e7a0b4` | 4 | `0x70106fc0`, `0x70107030`, `0x70107058` |
| `0x701078e4` | `0x70e7a0c4` | 8 | `0x701078e8`, `0x701078f0`, `0x701078f8`, `0x70107920`, `0x70107948`, `0x70107954` |
| `0x70107be0` | `0x70e7a0e4` | 4 | `0x70107be4`, `0x70107bf4`, `0x70107c04` |

The static original-byte and selected-translation receipt is
`work/runtime16-unresolved-boundary1/acceptance.json`, SHA-256
`70cd411005108ed4309b2a3953f9d767d856a7f107f2cd8dfb6098f16c5cdff7`.
Its original ELF is `3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f`.
All 16 rows resolve to twelve distinct interior targets, all missing from the
current 595,528-head inventory. Selected object13 remains
`b96472f5e0f45572c333943f0fd893d7d9f6b8388eb208629bb4818bec7007ad`.

`build_unity_701078_switch_entries_overlay.py` uses the qualified sparse
pre-inliner GuestCall producer, with SSHLL-qualified lifter `92ffe26c...` and
semantics `3ee3bf8a...`. Its default invocation is a read-only dry run.
`--execute` builds exactly one object with the twelve authorized entries;
inherited full-partition and legacy entry fields are hypothetical metadata.
The exact qualification job and sparse scope control the executed build.

The unselected candidate receipt is
`work/unity-701078-switch-entry-packet1/acceptance.json`, SHA-256
`90aa845f41112df64d74a85171813b6aec5e5985cc4320a272590531bda58a7a`.
Its 177,057-byte COFF object is
`88e21e57f84ad1b0c4c8bf5e722268d0e06a59b56af3887a5dfc2eb8b31caae3`.
It has twelve definitions, nineteen external original guest references, no
unsupported instructions, 66 poll sites including 54 cycle cuts, and 297
optimized GuestCall/pending-query pairs. State remains 1,200 bytes, alignment
16; Memory remains 64-bit.

The parent is the actual SSHLL/Crashlytics build manifest `239b08f3...`.
All 4,658 old object descriptors form an exact prefix, and their physical bytes
were hashed before and after candidate compilation. Object301 remains the
qualified SSHLL object `333b419d...`. The proposed cohort has 4,659 objects and
595,540 heads. Deleting exactly twelve declarations and twelve registration
rows restores the entire parent trace header. The other three generated
headers remain byte exact. No SDK or host source changes are part of this
producer.

Finite original ARM/Bionic and Windows dispatch/successor qualification passed
in `work/unity-switch-qualification-final1/acceptance.json`, SHA-256
`d9fc70aa3f57b40367ccae66b525e2c195664ff329c24db283b5cfff284f84b7`.
It binds the unchanged candidate COFF to 3,861 checks, 384 target cases covering
all twelve entries, sixteen original table rows, and twelve unsigned default
controls. Native and Windows memory corpora each contain 21,921,792 bytes and
were compared byte for byte in execution and again while sealing the receipt.

The guard slices use explicit fixture exit veneers at successor addresses.
Separately, the original unmodified FDE bytes and actual candidate object run
from synthetic interior states until one of three genuine outgoing calls.
Explicit fixture observers capture registers, arguments, and memory and stop
without executing those callees. The compared memory intervals and excluded
input/snapshot/scratch intervals are disclosed in the final receipt. This gate
does not establish whole outer-prologue/epilogue ABI, full-FDE coverage,
original startup, visible frames, or gameplay.
