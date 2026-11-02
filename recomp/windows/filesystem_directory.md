# Native directory streams and Android dirent

The native destination-filesystem enumerator at RVA236a44 uses opendir/readdir/
closedir, reads NUL-terminated d_name at offset19, filters dot entries, and joins
each name before stat classification. These three imports now have real Windows
directory-stream implementations, appended after unlink/rmdir without changing
existing markers.

OpenDir resolves an explicitly mounted directory, opens an owned native handle
with directory-list/read-attributes access, and validates its actual attributes.
Read-only mounts are enumerable. Final reparse-point opens remain unsupported95;
normal mount containment, Windows case behavior and the trusted stable host
namespace boundary remain unchanged. Missing/non-directory/invalid paths return
actual guest errors. Invalid UTF8 paths return EILSEQ84 instead of replacement.

Enumeration uses GetFileInformationByHandleEx(FileIdBothDirectoryInfo) on the
same handle. It consumes actual native batches, including only the dot entries
the filesystem itself supplies. It does not synthesize names or fall back to an
empty directory. Native FileId supplies the full64-bit inode. Ordinary directory
and file attributes supply DT_DIR4/DT_REG8; reparse/device attributes supply the
valid DT_UNKNOWN0 because those attributes alone do not prove a symbolic link.
The fixture compares each inode with both an independent native file handle and
the actual translated Android stat call.

AndroidDirent has size280 and fields at offsets0/8/16/18/19: inode, signed64
offset, uint16 record length, byte type and name[256]. Each record's length is
its name footprint rounded to8-byte alignment. d_off is this virtual stream's
monotonically increasing opaque forward cursor; it is not Windows FileIndex
(undefined on NTFS), a byte offset or a promise of seekdir/telldir support.
No directory seeking, dirfd, readdir_r or alternate import aliases are provided.

Every native record's header/name range, even UTF16 byte length,8-byte next
offset and UTF16 alignment are checked before publication. Invalid UTF16,
embedded NUL/separators, malformed batches, unsupported native enumeration
classes and names exceeding255 UTF8 bytes fail decisively; they never masquerade
as EOF. Real ERROR_NO_MORE_FILES alone establishes EOF. EOF and successful calls
preserve guest errno; genuine native failures use mapped errors.

FILE and DIR tokens share a non-reused monotonic allocator but have separate
type-checked ownership maps. A shared lease plus per-directory lock serializes
read/close and keeps the actual HANDLE alive during native enumeration. Each
live stream owns one stable record, published through tracked memory writes.
Next successful readdir replaces that record; close/destruction invalidates its
lifetime before freeing. EOF leaves its previous bytes and epoch untouched,
including repeated EOF calls. No guest-memory lock spans a native API call.
As with ordinary readdir, callers must consume a returned record before another
read/close on that stream. Concurrent use of its returned contents after a
second operation is outside this contract; independent streams remain isolated.

The accepted native Windows gate passes **16,309 checks**, **2,839 actual NDK
calls** through **nine strict trace heads**, zero unsupported/unresolved. It
enumerates more than700 entries across native batches, verifies exact names
with independent FindFirstFile/FindNextFile enumeration, compares all IDs/types,
checks Unicode paths and actual stat classification, guards ABI outputs, and
tests per-stream identity, EOF errno/epochs, tracked publication/retirement,
wrong/stale token rejection, handle counts, native close/read leases and a real
90-character Unicode name exceeding the Android UTF8 record capacity. The
existing file-ABI regression passes **116 checks** against the same provider.

```sh
python recomp/windows/test_filesystem_directory.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --support-source FROZEN_HOST/recomp --regression
```

Source/binary/fixture/toolchain hashes and exact output are in ignored
work/filesystem-directory/acceptance.json. The runner freezes support source
and overlays only its owned files. Fixture cleanup removes explicitly named
files and empty directories under a verified unique absolute work path; no
recursive host deletion is used. Original Unity ZIP-backend registration,
managed-data copying, IL2CPP initialization and a game frame remain separate.

Primary contracts:
[Android13 dirent.h](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/dirent.h),
[native query API](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex),
[native directory record](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_both_dir_info),
and [independent name enumeration](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-findfirstfilew).
