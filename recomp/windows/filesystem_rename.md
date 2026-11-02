# Reached quarantine rename

Unity's platform removal wrapper4292b0 constructs the sibling name `%s_tmp`, then
calls native236168→rename at2361e8 before opening copy streams. A successful move
selects the temporary path for recursive deletion; failure selects the original.
In the fresh Managed-copy gate, both `files/il2cpp` and `files/il2cpp_tmp` are
absent. A genuine ENOENT must propagate before the original unlink/mkdir flow.

`FileSystem::Rename` appends the import after closedir. It supports one native
MoveFileExW(source,destination,0) within the same explicit writable mount, to an
absent destination. Both regular files and directories/subtrees are moved by
the OS. There is no copy/delete fallback, replacement, reboot scheduling or
recursive host operation. Success preserves guest errno; actual absence/access/
sharing errors remain failures. Different virtual mounts return EXDEV18.

Existing-destination replacement, trailing separators and final dot components
are explicit unsupported shapes. This is the reached absent-target profile,
not general POSIX rename equivalence. Configured mount roots, parent traversal,
read-only mounts and final reparse points retain the filesystem's established
policies. The trusted stable host namespace boundary and native open-handle
sharing limitations remain; the adapter does not clear attributes or close
someone else's handle to force a move.

The gate passes103 checks through four strict Android NDK trace heads, zero
unsupported/unresolved, plus the116-check existing filesystem regression. Tests
verify genuine ENOENT, real file/subtree native identity and exact contents,
Unicode, guarded return ABI/errno, path/mount restrictions, preserved objects
after unsupported replacement, actual sharing failures and duplicate-move races.
All fixture cleanup targets are individually constructed under a verified unique
absolute work directory; no recursive host cleanup is used.

```sh
python recomp/windows/test_filesystem_rename.py --ndk NDK --lift FROZEN/remill-lift \
  --semantics-dir FROZEN --support-source FROZEN_HOST/recomp --regression
```

Ignored evidence: `work/filesystem-rename/acceptance.json`. Original managed-data
copy must still be rerun and checked independently; this import alone does not
establish extraction or game startup.

Primary native contract: [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw).
The actual NDK stdio.h supplies the rename declaration and the original Unity
instruction/path audit is in `work/managed-copy-audit`.
