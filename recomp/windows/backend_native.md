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

These are archive-I/O fixtures, rather than a usable game catalog. The test
starts no service and binds no port; status stays stopped. Actual backend
startup with owned master/revision files, matching client endpoint/port setup,
native networking and game integration remain pending. The smoke keeps the
Go DLL loaded until child exit and does not qualify DLL unloading.
