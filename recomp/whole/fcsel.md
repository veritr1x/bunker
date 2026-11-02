The FCSEL fixture qualifies scalar F32/F64 selection of raw source bits. It does not change or diagnose FMOV immediate as a new feature. The actual original regression is TST W20,#1; FMOV S0,#1.0; FMOV S1,WZR; FCSEL S0,S1,S0,NE, with both W20 bit values.

The old immutable pair's compiled FCSEL implementation incorrectly treats selected scalar bits as an address. A preserved earlier isolated baseline confirmed the exact0x3f800000 fault. The corrected-pair gate runs normal functional checks of both original input values and the complete source-bit matrix; it installs no fault observer and allocates no artificial guard.

The same strict NDK core object is linked into ARM64/QEMU and lifted on both hosts. The matrix covers all16 conditions/all16 NZCV values, opaque IEEE bit patterns including signed zeros, infinities and signaling/quiet NaN payloads, scalar source/destination aliasing and high registers. Local raw-bit oracles validate the complete observed GPR/SIMD/SP/flag state before producing compact record hashes. Native snapshots preserve the caller's ABI, and flag setup uses the native-only wrapper or lifted State rather than unsupported guest NZCV system-register accesses. FPCR.AH remains zero; this is not a qualification of merging/alternate features.

No original engine initialization, mute bypass, arbitrary guest-PC skip, cache behavior or playable-game claim is made. Acceptance files contain actual results and exact immutable source/tool/object inputs; failed candidates remain preserved.
The accepted functional qualification is `work/fcsel-positive2/acceptance.json`,
SHA256 `b2167498327bf7a721b4325bf290e93c287d5a4ad172e3a293c95c46392a254b`.
Its 227 cases each run256 flag/source patterns, producing 58,112 identical records
on ARM64/QEMU, Linux x86_64 and native Windows. An independent full-state oracle
also checks every selected value and normalized 800-byte state hash. The 3,081
decoder checks retain half-precision and neighboring instruction boundaries.
Both lifted cohorts have 455 heads/four objects, zero unsupported instructions
and no unresolved direct targets. Positive runs use normal successful inputs;
the earlier failing runtime/debugger evidence remains separate.

Remill commit `10ab6febe9a37125ba17d460be27c4f37a171c8f` changes only COND.cpp.
The lifter remains byte-identical to the prefetch pair; semantics SHA256 is
`316ab92e11637e57e1f7e7521d44ef1fa24881595d28871ccd47de6cf3aeefa3`.
Exactly 30 selector targets change; all 1,182 other semantic bodies remain exactly
unchanged. Numeric R32/R64 carriers replace pointer-shaped V32/V64 sources;
selection preserves bits without floating arithmetic, conversion or source
memory reads. Destination upper bits are cleared as required, including aliases.
State remains 1,200 bytes/alignment 16. FMOV immediate is not changed.

The sparse Unity shard00168 replacement preserves all 128 definitions, with 124
function bodies byte-identical. Two bodies correct scalar FCSEL; two other
textual differences are only private identifier renaming. Other selected game
objects retain their own immutable toolchains. Game17's original master-mute
request then returns and startup advances to the existing signal-delivery
guard; this does not qualify persistent gain, audio output or a rendered frame.
