# Retained IL2CPP numeric min/max refresh

Run 19 reached `TextMeshProUGUI.GenerateTextMesh` at `0x841e4bc4` and stopped
at the retained error for `FMAXNM S1,S13,S0` at `0x841e55e8` (reported next
PC `0x841e55ec`). The current qualified Remill tools already implement the
numeric min/max family. This repair refreshes stale translated bodies; it
does not add instruction semantics.

The approved first component contains eight IL2CPP FDE starts, in objects
1572, 2695, 2950, 3251, 3733, 3734, 3842 and 4168. The broader census of 149
Unity bodies remains separate. Each replacement preserves the other 127
raw and polled function bodies and the old module through an exact inverse.
Native preservation requires instruction, relocation and resolved constant
read checks; matching relocation fields alone do not establish matching
constant data.

Object 1572 is explicitly partial. Refreshing its numeric min/max prefix
exposes `FCCMP D4,D7,#4,NE` at `0x825c2dc8`, which remains a fail-closed
unsupported instruction. Its single emitted error reports `0x825c2dcc`.
Three later vector FNEG instructions occur in the original 632-byte FDE,
beyond the currently truncated path. Neither those instructions nor the
complete helper are claimed supported by this refresh.

The two large TMP methods also contain guarded runtime jump tables. The
approved sparse component adds exactly eight missing table destinations:
`83aaac0c`, `83aaae24`, `83aaae98`, `83aaaf28`, `841ebd8c`, `841ebfa0`,
`841ec024`, and `841ec09c`. It appends one object, adds eight declarations
and eight registration rows, and preserves the old 4660 objects and other
three generated headers. Its independent guard fixture executes both
original dispatch prefixes and checks all eight rows and unsigned defaults;
it does not execute the destination suffixes or entire TMP methods.

The historical primitive qualification is reused through exact current
compiled-function and source identity. A separate 1024-case Bionic/current
Windows fixture executes the original reached 32-byte instruction cluster
through its true fallthrough. It does not execute the complete 38,572-byte
method. Actual full-function behavior must be checked with the original
game and data after the combined candidate passes admission.

Failed attempts and completed compilation artifacts remain immutable in
`work/il2cpp-numeric-minmax-overlay*`. Native constant-pool proofs and final
combined admission are recorded separately; a component compilation is not
an original startup, visible-frame or gameplay result.
