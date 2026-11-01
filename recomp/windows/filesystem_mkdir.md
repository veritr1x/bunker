# Rooted Windows directory creation

`FileSystem::Mkdir` creates one directory below an explicitly writable mounted
root. It is exposed through the typed Android `mkdir(const char *, mode_t)`
bridge. Actual Unity calls at RVAs `0x2359ac` and `0x237158` request `0755`
and `0700`, respectively. Parents must already exist.

The supported requests are `0700`, `0755` and `0777`. Each is narrowed to an
owner-private Windows creation policy: the current process user owns the
directory and receives full control through a protected, inheritable DACL.
The descriptor is supplied to `CreateDirectoryW` at creation. Existing objects
return `EEXIST` without changing their owner or ACL. Filesystems without
persistent ACLs and other restrictive/special modes return `EOPNOTSUPP`.
This is a Windows policy, with no Android UID, group, umask or chmod emulation.
The existing virtual `stat` mode remains compatibility metadata.

The mount resolver checks canonical containment and rejects Windows device/path
aliases. This operation also rejects parent traversal components. As with the
existing resolver, the host mount namespace must remain stable during use;
the path checks do not provide a handle-relative defense against another host
process racing a reparse-point replacement.

The strict Android NDK fixture passes 33 checks through five translated traces,
with no unsupported instructions or unresolved direct targets. Independent
Windows security queries verify owner, ACE, DACL protection and inherited file
permissions. Tests also cover existing-object preservation, missing/file
parents, read-only/unmounted roots, errno, Unicode, trailing slash, concurrent
callers and the 128-byte Android stat layout. All 116 existing filesystem
checks pass with this implementation.

```sh
python recomp/windows/test_mkdir.py --ndk <linux-ndk> --lift <remill-lift> --remill <remill-source>
```

Run the script in WSL with native Windows MinGW available at
`/mnt/c/mingw64/bin`. Evidence and source/binary hashes are saved in
`recomp/work/mkdir/acceptance.json`; work artifacts are intentionally ignored.
