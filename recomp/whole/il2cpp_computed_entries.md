# Four original computed-branch entries

The `uname` startup run stops at indirect target `83f373c4`, LR `83f37378`.
The original FDE `83f372b8..83f374cc` contains two guarded four-entry jump
tables. All four heads of the first table are absent from the595404-head
selection; the second table's four heads already exist. Selected IR correctly
stores and dispatches the original computed target. This repair exposes the
four original entries listed in [the entry record](il2cpp_computed_entries.json).

The candidate freshly lifts the four untouched original suffixes using the
qualified guest-transfer toolchain, then adds cooperative polling and checks
optimized guard behavior. Its4076-byte COFF has exactly four strong guest
definitions, four closed native guest references, no unsupported paths, seven
poll sites and three guarded guest calls. State remains1200bytes/alignment16.
No existing guest object or function is rewritten.

Candidate receipt: `work/uname1-indirect-candidate-preparation1/qualification-result.json`,
SHA256 `dbb6f1f49b0685cc721be6f626f2a67d6c1ab38b49544e9f3f0a21ffcd91978b`.
The independent160-check peer passes, SHA256
`521b165d94fa5e69a1255b6173f7227db31c694154c442e5cb18eec5a2327e15`.

`work/windows-first-frame-uname-indirect1` retains all4652 prior guest objects
and appends one object, for4653 objects and595408 trace heads. The trace
header adds exactly four declarations and four sorted table rows; removing
those eight lines recovers the old header byte for byte. Bootstrap source
is unchanged and recompiled against this header. Metadata headers and the
qualified `uname` implementation remain exact. The final38-check packet peer
passes, SHA256 `1c657473d635f508d8dcf00ef2e579e83bf2f1a9f255eac63ab1a6f1d118fa28`.

Original startup then reaches a missing `mktime` import, LR `82556df0`, and
exits native3/controller1. Two render calls return continue=true, with no
draw, successful presentation, first-frame witness or PNG. Parent pre/post
verification and overlay pin checks pass. No direct execution trace of each
new case head was captured. Current integration details are in
[the first-frame status](../windows/first_frame.md).
