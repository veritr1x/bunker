# Unity pointer sorting and ARM EXT

A separate fresh-data diagnostic of the exact Game29 executable identifies
the native access violation. The loaded PE base is `7ff6ddb80000`; RIP
`7ff6ddc600db` is `__remill_read_memory_32+43`, reading through RBX
`781f277100000018`. Windows reports bad address `ffffffffffffffff` for that
noncanonical operand; those two values are preserved separately. The crashing
thread is UnityMain, not either timed-wait worker. Debugger exception chance
remains unknown. Canonical Game29 evidence is unchanged.

The passively recovered State names original PC `7025505c`,
`LDR W9,[X1,#24]`, with corrupted X1 `781f277100000000`. Original sort FDE
`70255e38..7025603c` swaps adjacent pointers using `EXT V1.16B,V0.16B,V0.16B,#8`
at `70256000` (word `6e004001`). Captured V0 contains valid pointers
`712d6880` and `71271f78`. Captured V1 instead contains each pointer's bytes
reversed; its high lane is exactly the later corrupted X1.

The selected raw IR, polled IR and native COFF all implement that reversal.
Remill's EXT implementation also has incorrect window bounds for other byte
offsets. The repair selects each output byte from the concatenated Vn/Vm
window in ascending order. Both sources are captured before writing the
destination; 8B writes retain zero upper 64 bits. Decoder, selectors and
physical function signatures are unchanged. The recoverable source delta is
[ext-byte-window.patch](../remill/ext-byte-window.patch), based on local Remill
commit `1d0ea03feb85e6a8f6c77e1a1a5939307b340668`.
The one-file repair is committed locally as
`178895dca6a584aee41f9db23dff23bd19aa6e44`; it has not been pushed.

The isolated matched toolchain is
`work/ext-preparation1/toolchains/2aa44c206c3c36b1-06d153f92cbfe3aa`:

- Lifter: `2aa44c206c3c36b1724deb4eb828f5e99916c2dd5f5eacfec6578474adeeec0e`.
- Semantics: `06d153f92cbfe3aa4a37e47a2b6563af2c86a266f6525923eb13ee1eb6486d5a`.

Compiled identity checks retain all 1,376 selector targets and 1,230 function
names. Only the two EXT bodies change; the other 1,228 functions retain their
actual attributes and metadata. State remains 1,200 bytes, aligned to 16.
The component gate compares 12,352 records per host against actual Android
NDK/Bionic ARM64 execution under QEMU, covering all legal 8B/16B offsets,
aliases, flags, upper-lane clearing and the captured pointer example.
Linux and Windows both pass, as do 3,089 decoder cases. Receipt
`work/ext-qualification1/qualification1/acceptance.json` has SHA256
`b4412315ade9aef3bd02aeb1ea0610692cdd52113e2d46c2bd40498ab95acf24`.

The game candidate relifts only the complete original 516-byte sort FDE and
splices it into Unity shard 78. Its other 127 raw bodies, polled bodies and
native function bytes/relocations remain identical. Direct guest references
and unsupported-head set are unchanged. The corrected EXT eliminates one
semantic loop, reducing that shard's poll sites from 180 to 179. The cohort
therefore has 456,684 heads, 122,088 cycle cuts and 578,772 poll sites.
Candidate `work/unity-ext-sort-overlay1/candidate.json` has SHA256
`9ad375fa793aa5ba92ee626abe6316f85a97d31379bd4d6fe34a7b80c267e343`;
the new COFF hash is
`f15e35212a7ea11597c885f990822018be23acf850080b84f919c114e3392327`.
The sort's other 2,591 IR lines retain identical operations, constants, calls,
attributes and control flow after bijective SSA renaming. Only the EXT region
and its proven private temporary allocations differ from the selected input.

An independent numeric-key oracle checks the original function's complete
insertion paths for lengths 0, 1, 2, 3, 7, 27 and 31, five orderings and four
NZCV seeds: 140 cases per executable. Actual original ARM bytes, Linux raw and
polled IR, Windows raw and polled IR, and the exact full 128-function Windows
COFF agree on 800 architectural bytes after identity-checked LR/x18/TLS
normalization. Data/record canaries, saved registers, stack footprint and host
memory token also pass. The old translated sort fails the independent array
oracle on both hosts. Receipt
`work/unity-ext-sort-fixture1/qualification1/acceptance.json` has SHA256
`be2afc2eb5b37e92b45eac72e8aebd5ab1640c8bb12d5060eb6a65acef81ba0f`.
This fixture uses an explicit test comparator. It does not qualify the
original comparator or the recursive/heap branches for lengths above 31.

The v3 consumer inherits the exact v2 prefetch cohort and permits only this
additional shard-78 replacement. It checks the pinned parent proof and plan,
the new plan, fixed component/overlay hashes and all 3,574 inherited object
identities before compilation or launch. This is two cumulative sparse
repairs, with no global semantics refresh. These component results do not
establish a nativeRender return, image, playable client or completed GC.
Frozen v3 cohort acceptance is
`work/game30-ext-cooperative-cohort/acceptance.json`, SHA256
`68017f198f7745a3e31056bf15a01ee9a8c9f11c12bd4b21ec1ab80efa589b67`;
its source-plan hash is
`4e01e9169f4265e1147dc3917e9acd8c7ecd7c5e73a5f9ad4c2b45a09e03cfeb`.
The actual Python and PowerShell guards each pass 117 acceptance/rejection
cases, including the earlier v1/v2 cases, the real v3 proof, changed parent
objects and altered proof/plan files. Validator receipt
`work/game-cohort-v3-validation2/acceptance.json` has SHA256
`bc45d2abb6974833d84a3014e28eebe680c996a82143702e1bb240f697553c94`.
