# Reached APK stdio buffering

Original Unity `410ec0` opens the APK through `fopen@b8b30` and immediately tailcalls `setvbuf@b8fb0` with `(stream, NULL, 2, 0)`. This adapter appends the import marker after `mkdir`, retaining every existing marker address.

`FileSystem::FSetBuffer(stream, buffer, mode, size)` accepts an owned live opaque guest FILE token and exactly NULL buffer, Android `_IONBF=2`, size zero, before stream operations. It applies `std::setvbuf(native_stream, nullptr, _IONBF, 0)` using the native macro; this MinGW/UCRT build uses **4**, not Android's 2. Success returns zero and preserves guest errno. Invalid/stale tokens return -1/EBADF; an invalid mode returns -1/EINVAL as an explicit adapter error policy. Current official Bionic's invalid-mode implementation returns EOF without explicitly setting errno, so this error policy is not claimed as bit-for-bit Bionic errno equivalence.

Other valid buffering modes, non-NULL buffers, nonzero sizes and reconfiguration after stream operations fail with explicit diagnostics. No supplied guest buffer is retained or dereferenced. Stream leases and the existing per-stream I/O lock serialize the native call against close; no guest-memory lock spans a CRT call. The private `io_started` flag is accessed under that lock and restricts only the new API.

## Real buffering effect and native boundary

The Windows CRT is genuinely switched to its native unbuffered mode. It is not assumed to reproduce Bionic's internal buffer representation. An isolated native-only probe showed that UCRT `fread` of one byte in `_IONBF` mode advances the underlying binary descriptor by **two bytes**, retaining one lookahead byte. Consequently a host update to byte1 after the first read is hidden until that lookahead is consumed, even without translation or this provider. That failed next-byte expectation and the raw native probe/source/hashes are preserved in ignored `work/setvbuf/native-buffer-boundary/`.

The accepted witness changes **byte2** after an initial one-byte read. The ordinary buffered control subsequently returns old bytes `BC`; the actual unbuffered stream returns `BZ`. No seek, flush or cache-reset workaround is inserted between update and read. Original APK input is a stable read-only file, so this documented one-byte host lookahead does not alter its bytes.

The accepted Windows run passes **76 checks** through **12 strictly lifted NDK trace heads**, with zero unsupported traces or unresolved direct targets. The existing file ABI regression passes **116 checks** against the same provider.

The dedicated fixture uses real Android NDK `fopen`, `setvbuf`, `fread`, `fseek`, `fclose` and `__errno` calls. It verifies NDK constants and eight-byte pointer/size_t layout, output guards, unchanged success errno, negative-mode errors, invalid/stale tokens, supported-shape diagnostics, actual file position and concurrent close leases. The existing 116-check file ABI suite is linked against the same provider as a regression.

Run from WSL:

```sh
python recomp/windows/test_setvbuf.py --ndk /path/to/ndk --lift /path/to/remill-lift-18 --support-source recomp/work/windows-unity-native3/source/recomp --regression
```

The script freezes support/fixture source and records source/binary/toolchain hashes and exact results in `work/setvbuf/acceptance.json`. Managed-data copying, ZIP backend initialization and IL2CPP startup remain separate unproved execution stages.

Primary sources: [Bionic stdio constants/signature](https://github.com/aosp-mirror/platform_bionic/blob/master/libc/include/stdio.h), [Bionic setvbuf implementation](https://github.com/aosp-mirror/platform_bionic/blob/master/libc/upstream-openbsd/lib/libc/stdio/setvbuf.c), [Microsoft setvbuf contract and exact unbuffered example](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/setvbuf?view=msvc-170). No upstream implementation is copied into the adapter.
