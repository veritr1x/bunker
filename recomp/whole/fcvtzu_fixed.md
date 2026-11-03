# Unsigned scalar fixed-point conversion

This component adds four FCVTZU fixed-point forms: S/D floating source to W/X unsigned result, with 1–32 or 1–64 fractional bits. Sources use numeric R32/R64 carriers and the decoded unsigned64 immediate is `fbits=64-scale`. W writes zero-extend; register31 is ZR, never SP. Half, signed and vector fixed-point forms are outside scope.

The same patch corrects numeric source transport for the four existing unsigned **unscaled** S/D→W/X FCVTZU forms. Their integer-bit numerical helper remains unchanged. The pinned parent bitcode had converted scalar source bits into an address before reading them; the corrected selectors receive numeric source bits. This includes the adjacent original `FCVTZU X8,S0` word `9e390008`.

The fixed helper scales the integer exponent before truncation and saturation. Qualification covers signed zeros, both signs of subnormal and max-finite inputs, scale-relative fractional/saturation boundaries, infinities and quiet/signaling NaNs. It checks IOC, IXC, FZ/IDC and preexisting sticky status with all 16 FPCR rounding/FZ/DN combinations. The conversion uses toward-zero independently of FPCR rounding. The original `9e19d809` and its following `9e230120` UCVTF are tested both separately and as an actual two-instruction core.

Acceptance: `recomp/work/fcvtzu-fixed-qualification1/acceptance.json`, SHA256 `73a166570129008d44061237cea546504534c0f6c79f59d4242ca17b4506e675`.

- 42 same-object NDK cores; 43,008 records each on ARM64/QEMU, native Linux and native Windows, with identical saved record streams.
- Every record checks complete before/after 800-byte architectural snapshots against an independent integer-bit oracle before pointer/SP normalization. The 32 scale-relative patterns cross 16 FPCR combinations and two initial FPSR values; all GPR/SIMD neighbors, SP, NZCV and FPCR are checked, with expected FPSR changes only. Input/output guards and native callee-save restoration are checked.
- Each translated host separately checks 42 raw cores against all 1200 State bytes without normalization and verifies the same opaque memory token returns. An ordinary load/store control retains its real memory effect. These 42 host checks are distinct from the 800-byte ARM reference snapshots.
- 531 initialized public-decoder checks: all192 legal scales, 256 representative Rd/Rn rows at #10 including ZR, four structured unscaled forms, the original fixed word, invalid W scales, reserved/half and supported separate neighbors.
- Each translated host has 85 trace heads/one object, zero unsupported traces and zero unresolved direct targets.

Qualified immutable pair: `recomp/work/fcvtzu-fixed-preparation2/toolchains/3d6beaa96e010c7b-0d5c2c427b2f43d2`.

- Lifter: `3d6beaa96e010c7b5424fba8960fe19eca3c261d6da164df08e4adadd75fbf88`.
- Semantics: `0d5c2c427b2f43d2f5b01db564e3141837c86df0afe79dee5c32ae48c3237409`.
- Compiled scope receipt: `recomp/work/fcvtzu-fixed-preparation2/compiled-semantic-proof.json`, SHA256 `2886ee6e5252abe176a99a2f0ae429fb6d8f89cfd2b869fc59e19c4de796cac9`. The only old-function changes are the four disclosed unsigned unscaled carriers; four new fixed selectors are added. The old numerical helper and other old functions/selectors are preserved.

Executed from the repository in WSL, using a fresh output directory:

```sh
/home/user/bunker-recomp/recomp/work/tools/bin/python recomp/whole/test_fcvtzu_fixed.py \
  --out /mnt/c/GitRepos/bunker/recomp/work/fcvtzu-fixed-qualification1 \
  --reference-root /home/user/bunker-recomp/recomp/work/reference-tools/root \
  --toolchain /mnt/c/GitRepos/bunker/recomp/work/fcvtzu-fixed-preparation2/toolchains/3d6beaa96e010c7b-0d5c2c427b2f43d2
```

The controller freezes its six fixture sources, support archive, tool inputs and actual outputs. Earlier strict precheck warnings were fixture indentation only and remain preserved in `fcvtzu-fixed-precheck1`; the immutable family qualification passed its first attempt. The reference uses the identical NDK core object linked to the pinned ARM64 reference environment. It is QEMU execution, not a claim of physical ARM hardware coverage.

Primary semantics are the pinned official Arm DDI0602 ID032025, `recomp/work/game14-next-boundary-audit/arm-arm-ddi0487.{pdf,txt}`: FCVTZU scalar fixed-point pp 1335–1337 and FPToFixed p 5916. Scope is baseline FP enabled with traps and AFP alternate/merging controls disabled. Component success makes no game, public-initialization, EGL, rendering or frame claim and does not itself select a cohort object.
