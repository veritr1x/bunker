# Rooted unlink and empty-directory removal

Unity's managed-data copy at RVA2392cc first calls destination-filesystem slot
0xf0 with W2=1. Its native target2359e0 recursively removes old contents using
individual filesystem operations; even an absent destination reaches unlink.
The host now implements the actual `unlink(const char*)` and `rmdir(const char*)`
imports, appending their markers after setvbuf.

Each call resolves an explicitly writable mount and invokes native DeleteFileW
or RemoveDirectoryW on one entry. The guest owns any recursive walk. Successful
calls return0 without changing guest errno. Missing entries fail with ENOENT2,
unlink on a directory with EISDIR21, rmdir on a file with ENOTDIR20, and nonempty
directories with ENOTEMPTY39. Nonempty directories and their children remain
intact after a failed rmdir. Native access/sharing failures remain real failures.

The rooted adapter protects configured file/directory mount roots with EBUSY16,
rejects parent-traversal components with EACCES13, and refuses final reparse
points with EOPNOTSUPP95. Read-only mounts fail EROFS30. These are explicit
capability policies, not a general Android mount/symlink implementation. The
existing mount resolver's trusted, stable host-namespace boundary still applies;
this is not protection against a hostile concurrent host renaming ancestors.

Windows deletion semantics remain visible: a handle lacking FILE_SHARE_DELETE
can prevent unlink, and native read-only attributes are not cleared. Open-file
unlink and Bionic permission equivalence are not claimed. Ordinary closed files
and empty directories used by this copy path are the supported scope. Calls are
serialized by the filesystem mutex; errors use the existing tracked per-thread
Android errno slots. No guest-memory lock spans the native deletion call.

`test_filesystem_remove.py` compiles real Android NDK direct/indirect callers,
checks native existence and content preservation, and exercises Unicode paths,
type/absence errors, containment, protected roots, native sharing and duplicate
removal races. Its optional existing file-ABI regression uses the same provider.
Fixture cleanup removes only individually named entries under a verified unique
work directory; it never uses recursive host deletion. Symbolic-link coverage
is reported explicitly, with actual privilege absence distinguished from a pass.
The accepted run passes138 checks through four strict NDK trace heads, with zero
unsupported/unresolved targets, plus the existing116-check file regression.
Symbolic-link creation returned ERROR_PRIVILEGE_NOT_HELD on this host, so that
optional native link case was not exercised. The initial failing file-ancestor
test and source are preserved in `work/filesystem-remove/source-revision-01`;
the adapter now checks ancestors so a file used as a parent reports ENOTDIR.

```sh
python recomp/windows/test_filesystem_remove.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --support-source FROZEN_HOST/recomp --regression
```

Primary contracts: [Android declarations](https://android.googlesource.com/platform/bionic/+/android-13.0.0_r1/libc/include/unistd.h),
[DeleteFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-deletefilew),
and [RemoveDirectoryW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-removedirectoryw).
Directory enumeration, original ZIP-backend registration, managed-data copying
and IL2CPP initialization remain separate execution gates.
