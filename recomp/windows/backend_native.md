# Native Windows backend preparation

The existing C exports in `overlays/server/cmd/android-bridge` now build as a
Windows x86_64 Go shared library. The isolated preparation uses Lunar Tear
63df7d70556a7180f04312abbafc56494cf70545, Lunar Base
b39154099b8f09f5926239e5838abc37260b9b9b, the Bunker server overlay/patches,
Go1.25.8, protoc33.5 and the repository's pinned Go protobuf generators.
`work/windows-backend1/prepare-server.ps1` records the source preparation;
native-build1's Windows syscall.Dup failure remains preserved.

Archive/log descriptor operations use a platform helper. POSIX retains its
original syscall.Dup body. Windows duplicates the native HANDLE returned by
os.File.Fd with DuplicateHandle/SAME_ACCESS and noninheritance, preserving the
caller's handle, access and shared file position. It accepts real pipes and
characters as well as disk files; it does not reinterpret a CRT descriptor
index or reopen a path. Test cleanup also releases the Go runtime's retained
crash-output descriptor before deleting temporary directories.

Focused native Windows6/Linux5 tests pass, including the existing archive-FD
and log export tests. Receipt `work/windows-backend1/dup-portability1/acceptance2.json`
SHA256 is `266c540f587ec545e3da19e79d733698724347c25d54d7e7449b254926aac6fc`.
The prepared server builds with Go's `-buildmode=c-shared`, CGO_ENABLED=1,
GOOS=windows, GOARCH=amd64 and the existing MinGW/UCRT compiler. DLL SHA256 is
`62b99ae6aedf7435ba48e6759dad6104fe718d73b06d7db66ecc3e0c680ea4e1`.

The actual generated-header C ABI passes a short-lived native child test:
absolute safe DLL loading, stopped status/ports JSON, Unicode archive paths,
and a real CreateFileW HANDLE transported through the existing C.int export.
Both import routes copy exactly two labelled fixture files/58 bytes. The
original handle remains readable at offset7 and closes independently. Seven
returned C strings are freed after verifying the host and DLL resolve free to
the same UCRT function. Receipt `work/windows-backend1/dll-smoke1/acceptance.json`
SHA256 is `7093b7ebb3c2b152b93169f493bd8fb6b7187647a6c95e8a2d87445f7bc3eb6e`.

Those first tests are archive-I/O fixtures; their test starts no service and
binds no port. The Go DLL stays loaded until child exit; unloading is unqualified.

The actual Downloads inputs have now been prepared separately under
`work/download-assets1/backend-root`: resource_dump_android.7z is imported
through the same native DLL path API, selecting only revision0. All201073
output paths/sizes match the real archive inventory, totaling20907771934 bytes;
the catalog and five compressed-stream samples also pass CRC checks. Original
archive size/mtime/header are unchanged; no full archive hash comparison is
claimed. Receipt `work/download-assets1/acceptance.json` SHA256 is
`287498d406a598b36577a1dec98c3c6fcd18b26e92de2acf92757e75acffa949`.

Pinned Lunar Scripts942dced617ea836a0e3abcfc0e0befec42baab11 patches a separate
master copy with the existing build recipe. Original master SHA256 remains
`60555788242de9a0580b0d86f6d109d67bd9cabd16d7bcda9b9a99745f270778`;
the patched7763264-byte output SHA256 is
`bfe4b83eb69cc907c028ed4b627c2b6861abfcd28e27973d93a88ed1522f7385`.
Neither Downloads original is replaced.

The real DLL now passes Start, SelfTest and Stop with those assets and fresh
`work/download-assets1/backend-data1` save storage. Explicit offset30000 uses
loopback38003/38080/33000. Actual gRPC game health and both HTTP service checks
pass, with status stopped→running→stopped. Selected listeners are absent before
startup, after Stop while the child is alive, and after child exit. The actual
new SQLite databases pass read-only integrity/migration checks. No existing
save or account rows are inspected. Receipt
`work/windows-backend1/backend-smoke1/acceptance.json` SHA256 is
`576d29c0047a75bd5b5cee10fbaa65da6601599bb916a5942126687ad15ad3e6`.
The test leaves no service running and does not qualify DLL unloading.

The game has not connected to this backend. Matching client endpoints, a
separately qualified derived application profile, real native networking and
actual login/catalog/download/gameplay integration remain pending. The current
game cohort still uses the original ELF and APK/metadata bytes.
