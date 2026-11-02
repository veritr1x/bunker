# Local index snapshots for relative jump tables

Original Unity's hash-tail dispatch at `4fb2d0` was unresolved because the
symbolic index reaching its load was ambiguous through an earlier loop. The
target expression and table address were already known. Both the global
expression at CMP `4fb2b4` and at indexed LDRSW `4fb2c8` were None; those unknowns
must never be treated as equal values.

The original instructions compare X13 with 15, take the unsigned B.HI default
edge, then load a signed32 table offset using X13 and overwrite X13 with that
offset. The original pre-load X13 read is the same locally bounded value even
though its earlier history is unknown. The load's destination write happens
after that read.

The planner now retains an immutable RegisterSnapshot (normalized GPR, effective
read width, instruction PC) alongside the existing global index expression.
It tries the complete original symbolic bound proof first and preserves that
proof exactly when available. Only if that proof fails can the local snapshot
fallback apply. It requires:

- The comparison and indexed load read the same GPR at the same effective W/X
  width. This does not equate a W comparison with an X load.
- CMP dominates the load. A bounded backward walk on every relevant CFG path
  reaches that CMP without a GPR alias write, an ABI caller clobber, an unknown
  root, or analysis-budget exhaustion. A W write also clobbers its X alias.
- Existing unsigned condition/flag, guard-edge coverage, incoming-range union,
  load stride, file-backed table, and executable containing-function target
  checks all remain mandatory. Disconnected case loops still require the
  existing closed-CFG verification.

No unknown expression equals None, and no original instruction or table byte
is changed. Only newly needed proofs gain index_snapshot metadata recording
the source width/load and the actual comparison/branch PCs. Interfaces of
previous successful table reports are unchanged.

## Dedicated validation

`snapshot_switch_fixture.S` is assembled into real Android NDK API24 ELF images.
A fixed-count pre-guard loop produces genuinely ambiguous global index history.
Seven positives cover X64, W32/UXTW, guarded W32/SXTW, separate load destination,
unsigned B.LO/B.LS guards, and both signs of relative table offsets. SXTW is safe
here because the unsigned bound limits the W value to 0..15.

Each variant executes 4,096 selector/seed pairs, including all case indices,
out-of-range indices, upper32-bit differences, and integer wraparound. Results
match an independent ARM64 QEMU reference built from the same assembly on both
Linux and Windows x86_64 hosts: 28,672 records per host /57,344 translated records.
PC, SP, and the saved X19 canary are checked for every translated call. Every
baseline without recovered table entries stops at a real unresolved indirect
target; every recovered variant has zero unsupported/unresolved direct traces.

Sixteen NDK safety variants emit no table or case seed: source/partial-W/conditional
and caller clobbers, flag clobber, different source register, both read-width
mismatches, guard bypass, wrong/signed/no condition, an unguarded case backedge,
stride mismatch, table extent truncation, and an outside-function destination.
The existing byte/half/word, masked-loop, and joined-guard fixtures (28 existing
ELFs across both host cohorts) retain exactly their old reports. Existing byte
mutation safety checks also pass. Those legacy artifacts are read-only; their
already accepted runtime binaries were not rebuilt or reexecuted by this audit.

Run with a fresh output directory:

```sh
python test_snapshot_jump_tables.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --reference-root ARM64_ROOT --remill REMILL_HEADERS \
  --out NEW_RESULT
```

## Original Unity result

For original Unity SHA256
`3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f`,
the complete old recovery report exactly matches the accepted 59,610-root cohort.
All 692 old table records and 5,238 old case seeds remain identical. Recovery
adds three tables /24 case seeds, reducing unresolved sites from 3,016 to 3,013:

| BR / containing function | Guard / pre-load snapshot | Entries |
| --- | --- | ---: |
| `4fb2d0` / `4fb0ac` | CMP `4fb2b4`, B.HI `4fb2bc`, X13/64 at `4fb2c8` | 16 |
| `4fbf9c` / `4fbcd4` | CMP `4fbf7c`, B.HI `4fbf80`, X27/64 at `4fbf84`; closed CFG | 4 |
| `4fc7d0` / `4fc630` | CMP `4fc7b0`, B.HI `4fc7b4`, X27/64 at `4fc7b8`; closed CFG | 4 |

The first table's targets exactly match the independently audited 16-case
hash-tail overlay that already passed Native7's observed missing-entry boundary.
The two neighboring tables are new static recovery results, not a runtime claim.
Original signed table bytes and target-entry bytes were independently decoded
and recorded for all three. All 469 accepted Unity object hashes remain
unchanged. The explicit union of old heads and new table entries has 59,634
heads; no full engine cohort was rebuilt and no final closure count is implied.

Ignored evidence: `work/snapshot-jump-tables-candidate2/acceptance.json`,
`work/snapshot-jump-table-audit/unity-acceptance.json`,
`work/snapshot-jump-table-audit/new-table-byte-proof.json`, and
`work/snapshot-jump-table-audit/legacy-regressions.json`. Lifter/semantics remain
the accepted immutable 78e33/098d2 pair. No engine frame was executed by this
planner task, and no existing frozen engine artifact was modified.
