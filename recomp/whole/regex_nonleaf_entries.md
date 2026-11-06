# RegexInterpreter table-entry recovery

The original `System.Text.RegularExpressions.RegexInterpreter.Go` FDE is
`0x84315734..0x84316890` (4,444 bytes). The selected full-function entry has no
unsupported instructions. Its three computed branch tables have 34, 6, and 43
guarded rows, resolving to 58 distinct interior addresses. The actual run reached
the missing `0x84315bd4` entry with LR `0x843167fc`.

The static boundary is frozen in
`work/runtime9-unresolved-boundary1/acceptance.json`, SHA-256
`3d4bd2f04a004e02d77003786883a41df0333ed0bc1bfca8666e66cbfbd4b002`.
The tables and their unsigned guards come from the original IL2CPP ELF. No live
regex object, opcode array, or unlogged arguments are assumed.

`build_regex_nonleaf_entries_overlay.py` pins that boundary and the current
entropy-device parent `71ae305452fbc7a3436ff825e79cdf5c0b4fbbe78da810a8ca3ca4cec0f17de6`.
It uses the established sparse pre-inliner GuestCall producer with frozen
`f967bf3b57f889d7` / `469903ec4d84cbd3` lifter/semantics, unchanged poll
instrumentation, and the existing optimized guard audit. Default invocation is a
read-only dry run; `--execute` requires fresh output directories and emits only
one new 58-function object. It does not regenerate old shards, select a cohort,
build a full host, or execute the game.

For example, from the retained WSL environment:

```sh
/home/user/bunker-recomp/recomp/work/tools/bin/python \
  /mnt/c/Users/user/.codex/worktrees/bunker-recomp-native/bunker/recomp/whole/build_regex_nonleaf_entries_overlay.py \
  --execute
```

The static packet is
`work/regex-nonleaf-entry-packet1/acceptance.json`, SHA-256
`ce02a9c53cbf05dddc26762e80ab16d711377e06e1bfc4f16c250db9e5654a82`.
Its object is `14d6d1efe6f4cef5900c2220fa25aa7f343d4da49fe4c37e753244b55e41578b`
(121,938 bytes). It contains exactly 58 definitions and 39 external original
guest references, all already selected. There are no unsupported instructions.
The polled IR has 66 entry/cycle sites, including eight cycle cuts; the optimized
audit verifies 311 GuestCall/pending-query pairs. State remains 1,200 bytes,
alignment 16, and Memory remains 64-bit.

All 4,657 parent object descriptors form an exact unchanged prefix. The proposed
cohort has 4,658 objects and 595,528 heads. The proposed trace header adds 116
sorted declaration/registration lines; deleting exactly those lines restores
the whole parent header. Other generated headers and host source files are
unchanged. The preexisting untracked FMOD nonleaf tool is read-only and retains
SHA-256 `40f852fa45f180956200afa835d9a21ca250409bec621f46ff3fd6511651e4e0`.

The inherited producer plan includes historical full-partition fields and an
old twelve-head `new_indirect_heads` list. Those are not the selection contract:
the exact `qualification_jobs` entry file, global head inventory, `sparse_scope`,
58-function result, and top-level packet describe this recovery. No old object
replacement or broad partition build is authorized by that legacy metadata.
In the frozen `preparation/build_candidate.py`, line 93 selects
`p['qualification_jobs']` for qualification mode; lines 122-126 read that job's
`entries` and check its exact count and membership. Line 210 requires the COFF
definitions to equal those exact entries. The emitted result records
`p['sparse_scope']` at line 302. That producer never reads `new_indirect_heads`.

Finite original execution passed in
`work/regex-nonleaf-qualification3/acceptance.json`, SHA-256
`90fd894dc272b2d673a86d1e4b5b81ac9fc8fea98a5a6194ec74989099f4aa64`.
Original ARM, raw Windows, and the exact production polled object produced 16
byte-exact records each. The bounded whole-entry profile uses TEST-owned code
`[23, unused, 40]`, genuine selected Go/Goto/TrackPush/Advance/CheckTimeout code,
four run-text positions, two status profiles, and explicit timeout/opcode flags.
A separate profile executes the helper-free Stop entry with the original saved
96-byte frame. Each Windows host reports 50 checks, eight TrackPush hits, 16 Stop
hits, and 40 real helper calls, with 16 KiB of owned bytes and full State/Memory
comparison. Unused helpers are abort-only link sentinels, not result stubs.

The final wrapper is `work/regex-nonleaf-entry-packet1/final-acceptance.json`.
It binds that execution evidence to the unchanged static packet and exact new
object. Only `0x84315bd4` and `0x84316814` are dynamically covered; recovery of
all 58 heads is a static closure claim. No exhaustive regex, allocator, exception,
clock, live-input, game, or first-visible-frame claim follows from this gate.
