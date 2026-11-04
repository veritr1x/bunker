# Host system information through Bionic uname

The original libil2cpp caller `825520c8..825521a8` calls `uname` at
`825520ec`, then reads the release field at offset130 to construct its
returned string. On a negative result, the original code uses `0.0.0.0`.
The original bytes and pinned AOSP Android13 header are recorded in
`work/guest-uname-boundary1/acceptance.json`, SHA256
`6f4f22951c180ed8d79d07b4ba2b59b523bcb84fd777f4ae737922d46991ec37`.

The provider writes Bionic's six independent65-byte fields (390bytes,
alignment1). Windows facts come from real NT version, DNS host/domain and
native OS-machine queries. Release is NT major.minor.build; the machine
describes the host OS architecture, separately from the AArch64 guest ISA.
No Android device or Linux kernel identity is invented. Query failures,
unrepresentable strings and inaccessible output buffers return errors.
The entire record is staged before publication, with checked UTF-8 byte
bounds and NUL termination. Guest writes use the tracked memory-write
scope; read-only and guard pages are rejected before the Windows copy.

`LibC` appends the import and binding, preserving all previous marker
addresses and its class header/layout. Existing error-publication policy
is retained. Native errno, LastError and floating-point environment are
preserved through query, publication and the error callback.

The Windows gate passes219 checks,24 actual translated NDK direct/indirect
`uname` calls and eight executed NDK layout calls. Coverage includes real
host facts, signed returns/errno, exactly390 output bytes, unaligned and
page-end buffers, NULL/overflow/read-only/guard/cross-page failures,
UTF-8 boundaries, query failures and native-thread errno isolation.
Receipt: `work/uname-host-qualification1/acceptance.json`, SHA256
`30dc2b49502cf8dac89eeed10b61ebb4a003cef6d3b39fc32e8f4b03e424e783`.

The affected Linux source and strict helper instantiation also pass syntax
checks, SHA256 `052feddee952de6fbe5b0d3c5e23518865d9c4b6afd5c652ec085ea39ba8da19`.
This is no Linux runtime qualification. Windows buffer-fault coverage uses
stable mapped protections; it does not establish arbitrary concurrent
mapping-change behavior. Game startup remains a separate integration gate.
