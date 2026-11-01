# Owned mmap region identities

`FileSystem::MappingRegion(address,length,writable)` returns the owning mmap
base, rounded byte size and lifetime generation only if the complete nonempty
span belongs to that live mapping. It queries actual Windows pages and rejects
uncommitted, inaccessible, guarded or insufficiently writable pages. File
views with Android 4-KiB offsets retain their actual guest-visible base, rather
than exposing the earlier Windows 64-KiB-aligned view prefix.

Generations are monotonic across FileSystem instances in a process, never wrap,
and change for each new map even if an address is reused. Protection changes
keep the same lifetime; successful unmap removes it. Querying metadata does
not touch guest bytes, memory reservations or virtual errno. Unknown CRT heap,
ELF and external mappings are not inferred from VirtualQuery alone.

This supports the nonlocal-context adapter's truthful owning-region validation.
It is not a memory lease: concurrent unmapping/freeing while a caller accesses
a buffer remains outside the contract. A Unity custom arena can keep a mapping
alive while destroying individual C objects inside it, so this identity does
not prove subobject/frame lifetime. Callers must separately track known object
and execution lifetimes, and stack owners must supply their registered stack
identity/bounds.

The Windows file gate passes **116 checks**, including the original APK's
mapped bytes, writable/private file views, interior spans, per-page protection
boundaries, overflow/out-of-range rejection, unchanged errno, unmap revocation,
new-map generations and rejection of unregistered committed heap pages.

```powershell
recomp/windows/test_files.ps1 -BuildDirectory recomp/work/windows-files `
  -Cxx C:/mingw64/bin/g++.exe -Cc C:/mingw64/bin/gcc.exe
```
