# Original Unity ST2 constructor qualification

The complete original function `0x707520c4..0x707521bc` passed 16 cases on actual ARM64/Bionic under QEMU and Linux/Windows raw and polled translations. The Windows polled leg used the exact complete 128-definition candidate COFF. This is a component qualification, with no game or frame claim.

Final receipt: `work/unity-st2-constructor-qualification2/acceptance.json`, SHA256 `6b6dbfb3d20b080b4f029c410a776d088a28dbe7e0f05c9a68b4c739b30f3597`. Candidate receipt: `6791fa803510090f27a2b0d08a2f371fd9b8b2201bf555f14da2214f30d2ce4d`; Windows polled COFF: `ad6b08dbcebe0d007c60a6ccc6a8b71f6a8be8a80693cec4fda0223fab53fe5e`.

The native reference maps the untouched 248-byte original function, original PLT and Q/D readonly literals. The actual GOT slot points to genuine Bionic `memset`. Translated calls use the existing typed bridge and production `provider_memory::Fill`, which performs real standard `memset` under the tracked-memory protocol. The test validates the call tuple `(object+8,0,0x68)`, exactly one translated call, normal return and memory-token preservation. The opaque global is a labelled fixture input, alternating original file bytes with a controlled value; it is not a claim about its game-time value.

An independent oracle verifies every byte of the `0x590` object window, its unwritten padding and the entire 64KiB allocation, including all 32 ST2 interleaved nodes. Stack endpoints are inaccessible. Canaries outside a declared 16KiB original libc/capture budget remain unchanged; no leaf-stack or native-host-stack identity is claimed.

Each platform retains a full 800-byte architectural snapshot as an observation. Cross-platform records compare x19-x29/SP, locally validated return, D8-D15 low64, and original post-call-defined X0/X8-X11/Q0/Q1/final NZCV, plus FPCR rounding preservation. Platform x18/TLS are checked locally. Libc-volatile registers, high64 V8-V15 and FPSR are excluded from equality. Full1200-State equality is not claimed across different libc implementations. The ABI basis is [Arm AAPCS64 2022Q3, sections 6.1.1-6.1.2](https://raw.githubusercontent.com/ARM-software/abi-aa/2022Q3/aapcs64/aapcs64.rst).

Cases combine four W1/W2 and opaque-input patterns with four FPCR/NZCV/FPSR settings. Raw and polled records match; polled hooks are dormant with no slow delivery. The existing 1120-record ST2 family qualification is reused, not repeated.

Attempt1 stopped before any case at Windows strict compilation: three existing misleading-indentation warnings in unchanged provider allocation helpers. Attempt2 marks that frozen provider include directory as a system include while retaining `-Wall -Wextra -Werror` for the new fixtures. All other fixture source bytes are unchanged. Both attempts and logs are preserved.

The five executable source files copied into this directory are byte-identical to the final receipt's frozen `source/` files. The native wrapper is the previously qualified complete register-capture implementation. The controller checks actual ELF `PT_TLS` alignment before reference launch and uses `-fno-emulated-tls`.
