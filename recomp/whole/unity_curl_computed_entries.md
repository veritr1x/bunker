# Original Unity curl computed entries

The socket-enabled original startup reaches real network operations on a Unity
worker, then fails on the original untrusted-certificate error path at indirect
target `70b4c100`, LR `70b47730`. The target is the first case in a guarded
47-entry signed-relative jump table inside original FDE
`70b4bfac..70b4c5b8`. The LR belongs to the direct wrapper call at `70b4772c`.
The original instruction bytes and selected dynamic dispatch are intact.

All four computed branches in this FDE have bounded original tables. The
five type-dispatch destinations are selected already. The double, long and
pointer tables contain 40 distinct destinations absent from the selected
595408-entry inventory. [The entry record](unity_curl_computed_entries.json)
lists this complete bounded recovery; it is not a whole-game table inventory.

One fresh sparse Unity object exposes these 40 original suffixes with the
qualified `14f6409b` lifter, `6dd3ed0e` semantics, pre-inliner guest-call
lowering, State 1200/alignment 16 and cooperative polling. Its 15924-byte COFF
defines exactly 40 new entries, has 40 entry poll sites, no unsupported paths
and one external guest reference, the already selected original helper
`70b4a020`. The optimized guard gate checks its one non-tail guest call.

The component execution gate compares 40 entries with six explicit seed
profiles: 240 executions each of untouched original AArch64 code under static
Bionic/QEMU, raw Windows code and the exact proposed polled Windows object.
All output/canary bytes, return values and handle hashes agree. Checks cover
the original stack epilogue, restored GPRs, signed loads, conditional status
and flag paths, and integer-to-double conversions. The helper-dependent case
uses the real original `[handle+0xa98] == 0` path and exact selected helper IR;
other helper callouts fail closed in the fixture. These seeds do not claim
to reconstruct the unlogged game arguments. The first fixture attempt failed
because Bionic required 64-byte TLS alignment; its artifacts remain preserved.

The proposed packet retains all 4653 prior guest object descriptors and
appends one object at index 4653. Its 595448-head header adds exactly 40
declarations and 40 sorted rows; removing those 80 lines recovers the prior
header byte for byte. No host implementation or existing guest object changes.
The root controller owns subsequent composite-host selection and game testing.
This recovery preserves the original certificate-error behavior; proper TLS
trust is a separate change. It does not establish a first frame.

Packet: `work/socket1-indirect-packet1/acceptance.json`, SHA256
`e381797a18aa26dedb61cc4e9e3f24393f298b770bd64a2207a31c0a73c0dd5c`.
Original execution gate: `work/socket1-indirect-execution3/acceptance.json`,
SHA256 `0c3ba364a26155decf55d9b64f9dd96c57bef3a03161ed8511bae98bffd6c468`.
