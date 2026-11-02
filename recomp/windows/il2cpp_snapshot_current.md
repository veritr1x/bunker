# Refreshed full IL2CPP diagnostic snapshot

`whole-il2cpp-current` contains397,058 traces in3,105 AMD64 objects,101 unsupported
traces and zero unresolved direct targets. It uses the same frozen lifter and
indexed-FP semantics as the current Unity snapshot. It is a complete fresh
translation run, without the older one-shard overlay. All393,781 old trace heads
remain present; the old mixed diagnostic and every prior executable are retained.

The plan preserves original ELF/import/export/range/lifecycle data and every old
seed. It adds3,272 proved seeds from improved jump-table recovery, callbacks and
the actual setjmp return825b0580. The final trace set adds3,277 heads after direct
closure. All3,105 COFF headers/hashes and397,058 unique definitions were checked;
58,457 distinct direct guest targets are closed. Canonical recursive State layout
remains1200 bytes/alignment16 with SHA256
`ba607ad5aab3a61164b08c8fa4a07c9273c5b9a788d5789ad580e5396b898d8d`.

One added head84785f58 is unsupported. It is a proved jump-table case inside the
already-unsupported old84785c7c..8478637c function. Independent original-byte/CFG
and alpha-equivalent IR-block comparison identifies exactly the same FRINTP at
847862c8 and FRINTM at847862d4 as before. Their instructions remain unimplemented;
this is an exposed existing limitation, not a claim of full instruction coverage.
No previously supported old head became unsupported. The original snapshot had
192 unsupported heads; its separately accepted atomic overlay reduced that to189.

Native Windows default lifecycle and actual parameterless25b3020 signal-init
profiles both exit0. Each executes all nine original constructors and both
finalizers. The latter verifies actual30/24 signal handlers/thunks, an empty
acknowledgment semaphore and an unblocked mask. Frozen host commit is
`e74feb234dd5aa769b824fd6b5f4a576143b8f06`; it predates the later gettimeofday and
directory/PackageItemInfo changes. All3,105 copied objects and70 frozen build
source/include files were rehashed after execution.

| Artifact | SHA256 |
| --- | --- |
| Original IL2CPP ELF | `ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522` |
| Fresh manifest | `afbbd86190c72dfac7f5fba7959c7b40f5c0ab339a46063b56c465e74d3451f6` |
| Lifter | `78e33b4cc37e8b2d34e7b6f2adf2a549ccc2590199f8c41a9758a039e09a5a54` |
| Semantics | `098d2e4b3214af9b3e4a7a39053acf44bc04ab94527b549874fd7d69710bab1e` |
| Native executable | `0443c493b901d631e3ee3ac5a8b1ad51b73672b963a3c8e17d89c4b65fe36d59` |

Ignored evidence: `work/il2cpp-current-lineage/result.json`,
`work/il2cpp-unsupported-split/proof.json`, and
`work/windows-il2cpp-current/{parity-acceptance,post-run-integrity}.json`.

This snapshot is unpolled. These checks do not run il2cpp_init, metadata/domain
loading, managed code, suspension/collection, restored longjmp or a game frame.
The earlier combined/API-loader/component executables retain their independently
frozen older engine composition until explicitly rebuilt and verified.
