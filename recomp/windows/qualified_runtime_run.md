# Qualified current-runtime launch checks

Full host builds retain their existing complete pre/post input verification.
An independent built-peer still checks the selected sources, guest objects,
generated headers, response file and admitted component evidence.

`work/qualified-runtime-run1/run.py` separately verifies the inputs used by the
compiled process: its EXE, two original ELFs, muted APK and six ANGLE DLLs.
Expected APK/DLL hashes come from authenticated original `game_inputs.json`;
they are not inferred from current disk contents. It also authenticates the
build manifest, built-peer, builder, verifier modules, hash transport, launcher,
run admission and the original baseline script/import/transport. The unchanged
original-parent baseline check runs before and after the process.

The launcher checks the exact native argv and file membership, requires a fresh
data/log/admission path, refuses an existing original game process, and never
automatically retries or times out a live process. Its frame witness parsing
still requires an original render return, successful original presentation,
draw submission and nonuniform captured image.

Historical executables and old source/header copies remain build provenance;
the runtime launcher does not rehash them. Audits explicitly record
`all_overlay_pins_reverified=false`, `historical_artifacts_reverified=false`,
`build_inputs_reverified_at_runtime=false`, and the separate true selected-runtime
verification result. These claims differ from the earlier whole-history runner.

Enabled launcher SHA256:
`f0f12adc178eafdc75cfe76efcbab6e6c265e7922cdafb3031a379469ff390ef`.
Reviewed disabled source: `e20bd846794c0a13afc4095a71be7c549387e44fe10d6dc8816b58e00f925411`.
Independent static receipts:
`work/qualified-runtime-run-peer1/acceptance.json` (`9ca4ebf75964cd69d3d866b552200a0f1ba30f0d5f7049d3813a36f6973d1643`),
and incremental peer2 (`5b6bec7f9edb444684fbc3168a5f85d3d83ba67924a314a22154659010e26dc1`).
Read-only inspection2 (`15b8ec0b70c02bb3a4602b5ffd7bff7d838668772d3faa10adffeedf28aa2fc8`)
verified actual runtime inputs on the completed draw-buffers candidate without
launching a guest. Only the docstring and enable flag changed after review.
