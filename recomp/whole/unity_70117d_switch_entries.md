# Unity parameter switch entry recovery

Runtime17 reached unresolved interior target `0x70117d90`, with LR
`0x70117c7c`, after 35 original render returns and 33 successful presentations.
These observations do not establish a visible game frame.

The original Unity FDE is `0x70117c5c..0x70117e54`, 504 bytes. It saves a
48-byte frame, calls the original validator at `0x701172fc`, and uses three
four-row signed-relative branch tables. Each table is guarded by unsigned
`w20 <= 3`; `w20` retains the original `w2` argument. The index is copied to
`w9` before the first table and retained for the later tables. The later guards
reuse flags across intervening instructions that do not change them.

| Branch | Table | Targets | Current status |
| --- | --- | --- | --- |
| `0x70117d18` | `0x70e7aa00` | `0x70117d1c`, `0x70117d24`, `0x70117d34`, `0x70117d3c` | Already selected |
| `0x70117d8c` | `0x70e7aa10` | `0x70117d90`, `0x70117dbc`, `0x70117dcc`, `0x70117ddc` | Four missing entries |
| `0x70117e20` | `0x70e7aa20` | `0x70117e24`, `0x70117e34`, `0x70117e3c`, `0x70117e44` | Four missing entries |

The original-byte, selected-head, and retained-IR audit is
`work/runtime17-unresolved-boundary1/acceptance.json`, SHA-256
`30a96908bd44e40d046bf03531c673ab0e6ead2a3e4ed0f2cce7a612970da148`.
All five existing selected functions in this FDE have no unsupported
instructions. Object17 remains
`36880ad00ef1dc10519ae93a7031781c3ca0e082de60440a3743d6ca9bbae57d`.
The validator FDE `0x701172fc..0x70117414` is also present in that object.

`build_unity_70117d_switch_entries_overlay.py` uses the existing qualified
sparse pre-inliner producer and lifter `92ffe26c...` / semantics `3ee3bf8a...`.
Its default invocation is a read-only dry run. `--execute` compiles exactly
the eight missing entries into one new object. It preserves the already
selected outer function, four first-table entries, validator, and all other
current code. Inherited full-partition fields describe a hypothetical partition;
the exact eight-entry qualification job controls the actual sparse build.

The unselected candidate receipt is
`work/unity-70117d-switch-entry-packet1/acceptance.json`, SHA-256
`8cb4538ddc64f3421743c9dd350854782ba41cff7919e700b14237715fcf4c1a`.
The 8,283-byte COFF object is
`f32e3c58f3b49371e179174fab226f84055a314eb98c3eca976f3c244f890a1b`.
It has exactly eight definitions, no external guest references, no unsupported
instructions, eight entry polls, and no cycles or non-tail guest calls. These
suffixes execute their original epilogue and return. State remains 1,200 bytes,
alignment 16, and Memory remains 64-bit.

The actual parent manifest is `316aff1d...`. All 4,659 existing object
descriptors form an unchanged prefix, with physical hashes checked before and
after compilation. The proposed cohort has 4,660 objects and 595,548 heads.
Deleting exactly eight declarations and eight registration rows restores the
entire parent trace header. The other three generated headers remain exact.
No host or SDK production sources change.

Finite original ARM/Bionic and actual candidate Windows qualification passed
in `work/unity-117d-qualification1/acceptance.json`, SHA-256
`73f375cd4e3405e1de9848cfac100be0f25ebb861513dcc2b95c9eed4bc13735`.
It executes the real 504-byte outer function and 280-byte validator, with the
unchanged selected object17 and actual eight-entry candidate linked into the
Windows fixture. It passed 2,383 checks across 88 cases: 64 successes and 24
failures, covering all three tables and all eight new entries. The normal
prologue/epilogue, callee-saved registers, stack guards, and opaque Memory64 are
checked. Native and Windows 4,325,376-byte data corpora match byte for byte and
are also checked against an output-write oracle.

The object readiness virtual method is an explicit test-defined boolean
callback. Invalid-index formatting and logging branches within the validator
remain unqualified. Native execution uses actual Bionic TLS/canary; Windows
uses controlled guest TLS/canary. The compared data prefix is separate from
the respective native and guest stacks. This bounded gate establishes neither
the prior 5,688-byte function's full behavior nor original startup, a visible
frame, backend behavior, or gameplay.
