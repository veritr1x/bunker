# Unsigned CMHI component qualification

Scope: seven valid vector arrangements and scalar D, in the existing AdvSIMD-enabled profile. The primary Arm DDI0602 ID032025 pages 1150–1151 define unsigned lane comparison, all-ones/zero results, invalid vector 1D and scalar size restrictions. This does not add privileged trap emulation.

Both source vectors are snapshotted before writing a possibly aliased destination. The inactive upper 64 bits clear for Q0 and scalar D; NZCV, FPCR and FPSR remain unchanged. Scalar source transport uses numeric R64 values rather than vector-address wrappers.

The shared NDK object provides the exact original `CMHI V16.4S,V5.4S,V16.4S` word 0x6eb034b0 from 8261b694, all eight supported forms and eight register/alias arrangements. Each of 65 cases runs 256 full-state seeds. Both native ARM64 and lifted hosts independently check all GPR/SIMD registers, SP, flags and floating status against the unsigned bit oracle before comparing normalized records. The adjacent scalar memory copy remains a real memory-effect control.

No game execution, original function invocation, cohort change or authority promotion occurs in this isolated qualification.

Qualification3 passed 16,640 records on each of actual ARM64/QEMU, Linux, and Windows. The record streams match exactly. Its decoder checks passed 1,038 cases, including every register position and all valid forms; each lifted host has 131 heads / two objects, zero unsupported traces and zero missing direct targets. Existing signed CMGT and other adjacent supported controls remain supported, and invalid vector 1D/scalar sizes plus currently unimplemented CMHS remain rejected.

The compiled supplement proves all 1,368 previous selectors and 1,222 function bodies/actual attributes unchanged, with exactly eight additions. Prior qualification1 and qualification2 are preserved fixture-expectation failures: rejected decodes retain descriptive names, and signed CMGT was already supported. Production source bytes did not change between these attempts.

## Reviewed source promotion

The exact three tested Remill source files were promoted locally after independent
review in commit `1d0ea03feb85e6a8f6c77e1a1a5939307b340668`, based on
`22466cfdb061b6851bccf611950e67862eaf7d45`. The scratch qualification and its
immutable toolchain remain preserved. This source promotion does not select a
new game cohort or refresh any existing guest object.

Independent receipt `work/cmhi-preparation1/independent-peer.json` has SHA256
`26ba5e14a058a1307341ea349575ac1ba68dae9f7d4739f43935f43d66e1e679`
and binds final qualification3 acceptance
`586922316af5121ca9524544662f8bac18ee1a6e6fe8d65cacf539d5f71392a7`.
Its separate Python unsigned-lane oracle reconstructed all 16,640 normalized
800-byte state digests, not only the selected destination. Actual saved records
match across ARM64/QEMU and both translated hosts. The review also rehashed
770 compiled sources, 201 support files, 223 tool files, six external inputs,
74 evidence files and 19,286 dependency files.

The repository controller uses `ROOT=HERE.parent.parent` so support archives
follow the actual checkout. This is the only controller change from tested SHA256
`0d267e470adb07b57e5740f515bb488993841353dab1f5929d504d3671780ab7` to promoted SHA256
`c6eb7718b66c7ee182caa851701d6552957ae0396e9f4156e6297116b35af7b7`. All other AST nodes and five
fixture/reference/decoder files are identical. A metadata-only load verified
the actual repository path; no broad gate was repeated for this portability change.
No main-repository commit, current toolchain replacement, original-function run,
cohort selection or game execution is part of this promotion.
