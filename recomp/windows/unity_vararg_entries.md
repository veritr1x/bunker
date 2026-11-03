# Original Unity formatter continuations

Game30's collector profile stops with native exit 3 at unresolved indirect
target `0x70b5b648`. The error supplies no active caller PC, thread, LR or
table index. Those values are not inferred from the preceding worker logs.

The target is executable original Unity code inside FDE
`0x70b5ae80..0x70b5c138`. Original code bounds an index to 0..9, loads a signed
32-bit offset from table `0x70fd0134`, adds that table's address and executes
`BR X15` at `0x70b5b644`. The complete table has five unique destinations:

| Table indices | Original destination |
| --- | --- |
| 0, 1, 2, 4 | `0x70b5b648` |
| 3 | `0x70b5b488` |
| 5, 6, 8 | `0x70b5b674` |
| 7 | `0x70b5b4b0` |
| 9 | `0x70b5b4bc` |

All five are absent from the selected catalog. Selected shard 386 preserves
the original table calculation and `__remill_jump`; these destinations are
internal continuation states. Dispatching them to the FDE prologue would
repeat frame setup with the wrong registers and stack state.

Read-only original/selected-code proof
`work/game30-indirect-target-audit1/proof.json` has SHA256
`67218fa4852147b98ee60a42a0456c2ae139051d8ea19ee660b1bb985cd9ea74`.
Independent table proof
`work/game30-table-target-audit-peer1/proof.json` has SHA256
`ca278261a3fd35a798af68b06d9e274d28adde3cbfae92786d67a4946600777b`.

The additive candidate lifts exactly these five starts from the unchanged
original Unity executable image, using the frozen EXT-corrected matched
toolchain and unchanged cooperative instrumentation. It preserves all 3,575
selected objects, including the prefetch and EXT sort repairs. Candidate
`work/unity-vararg-five-entry-overlay1/candidate.json` has SHA256
`88e29cd4c8853af8a6f9111b8e56504db556b2ef2fa6eb31bc81f310b98e85f2`;
its new five-definition Windows COFF has SHA256
`f2bd9a1606dfc26ccbfa02f331f708df94cab70fe24fcbffbc511ef6d1a181cc`.
No unsupported instruction appears in the new entries. State remains 1,200
bytes, aligned to 16, with the same type closure.

Adding one object produces 456,689 heads in 3,576 objects. Its five entry and
five cycle polls produce 122,093 cycle cuts and 578,782 total poll sites.
The two newly referenced existing heads are `0x70b5b7fc` and `0x70b5c138`;
the global direct-target count becomes 79,438, with no missing targets.
The generated trace header adds exactly five unchanged-signature declarations
and five table rows. Removing only those ten lines recovers the old header
byte-for-byte. Its projected SHA256 is
`7023f214e74a275888963fdee6e2f6c21d48c5a549594f2d32a812bcc17d6680`.
Inherited cached symbol offsets remain historical; the new inventory qualifies
symbol names and kinds rather than asserting refreshed native offsets.

The prefix gate passes 240 cases per executable on original ARM64,
Linux raw/polled code, Windows raw code and the exact five-function Windows
polled COFF. It uses owned vararg
save/overflow areas and record buffers, negative and nonnegative cursors,
flag-directed load widths and a two-record loop. It stops at the first
original `BLR X19` at `0x70b5b81c`, before executing the output callback body.
At that seam the literal-A callback has W0=65, X1=X20 and LR=`0x70b5b820`.
This is deliberately a prefix boundary, with no claim of complete formatting,
callback behavior, a returned nativeRender, image or playable client.
Receipt `work/unity-vararg-five-entry-fixture1/qualification2/acceptance.json`
has SHA256
`ed69b5f9076507a58c57f95ef569172db08e5f94fc9a72215d03ac90d74574ee`.
The first controller attempt failed before compilation or execution because
its QEMU path pointed at the wrong filesystem. The corrected path and all
unchanged implementation sources are preserved in the successful gate.

Frozen additive v4 cohort acceptance is
`work/game31-vararg-cooperative-cohort/acceptance.json`, SHA256
`5aa51b995facc9b9e1dc18997f667c4d7918754d91fc60ae675abda0957b3fd3`;
its source-plan hash is
`57fa0c40d52a3e1e175cff2dd8133935d873d481038845c7aca734352b9d35ae`.
The Python/PowerShell consumers retain the earlier v1/v2/v3 behavior, check
both ancestor proofs/plans and permit only the declared five-entry addition.
Each passes 212 actual acceptance/rejection cases. Validator receipt
`work/game-cohort-v4-validation2/acceptance.json` has SHA256
`9fbfe3699e89f058662537936020b78814ac642f4f3be73bcfa9f5a31ca999ec`.
The v4 cohort and prefix qualification establish build prerequisites; they
do not establish successful original-game formatting or startup.
