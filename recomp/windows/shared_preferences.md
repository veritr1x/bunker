# Bounded Android SharedPreferences for original Unity startup

`AndroidSharedPreferences(host, actualContext, package, backend)` binds the
originally requested Context method and a real preference store/editor surface.
Construct it after AndroidContext (Uri metadata) and before guest startup. Pass
the actual Activity returned by AndroidContext, not a fabricated Context. The
adapter accepts mode0 and exactly `package` / `package+.v2.playerprefs`.

`MakeWindowsSharedPreferencesBackend(package)` fixes the independent per-user
HKCU64 namespace `Software\Bunker\Apps\<package>\SharedPreferences`. It is not
the CLI cache/DataRoot. Construction never opens, reads or writes storage. The
Windows backend requires a canonical lowercase package spelling (the actual
approved APK package has this spelling); other spellings are explicitly
unsupported before I/O, preventing case-insensitive registry package aliasing.
The
first original getSharedPreferences opens the exact named value; only actual
ERROR_FILE_NOT_FOUND is absence. Read/corruption errors remain decisive. The
first original guest apply performs the first production write; no provider
initializer manufactures a version marker or pre-migrates data.

Storage is a single REG_BINARY snapshot value per store. It starts with the
eight bytes `BNKPREF\x01`, then little-endian uint32 entry count. Each entry is
uint32 key length + exact UTF16LE code units, uint8 type, then its typed value:
1 string (length+UTF16); 2 int32 bits; 3 float32 bits; 4 boolean byte0/1;
5 int64 bits; 6 string set (uint32 count plus length-prefixed strings). Keys are
case-sensitive inside the blob. Duplicate keys/set members, trailing bytes,
unknown versions/types, invalid bool/high integer bits and truncation fail.
Limits: 4MiB blob,16,384 entries/set items,262,144 code units per string. No
implicit UTF8 normalization or NaN payload conversion occurs in storage.

The backend reads existing snapshots, performs one actual RegSetValueEx for a
complete replacement and RegFlushKey for bounded synchronous persistence. It
opens the writer with QUERY_VALUE as required by
[RegFlushKey](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regflushkey).
It
does not claim a transaction across stores or multi-process update support.
Only a uniquely owned temporary package namespace is created/deleted in tests.
An ordinary production store is never cleared or treated as fresh without a
real read. This format is a host backing, not a claim to import Android XML.

The provider cache explicitly roots one Java object per store, matching the
process singleton contract. Prefs/editor payloads own native Store state;
Map/Set/Iterator/Entry payloads own detached typed snapshots. No native Store
points back to a Java object or adapter. Original Unity JNI global references
and its retained editor remain owned by original code. No payload destructor
calls guest native cleanup. `edit` returns independent pending batches;
`put` returns the same editor; apply merges the batch, clears pending changes,
and leaves that editor reusable. Native commit turns serialize memory/write
ordering without holding a mutex across backend I/O. Backend callbacks are
native storage only and may not drive JNI or recursively apply/open a store.
Host calls and Java root retirement occur outside state/store locks.

Synchronous apply is explicitly allowed to third-party implementations by
Android13 SharedPreferences.java234–238. Memory changes commit before writing;
apply remains void. Any native write failure is diagnosed and permanently
recorded, including a failure followed by a successful later write. After
callers quiesce, integration **must call CheckPersistence before reporting
normal completion**. It does no write and rejects any recorded failure. No
asynchronous scheduling, Java listener, commit(), clear(), remove(), arbitrary
preference store or general Java collection implementation is claimed.

Destroy the adapter after guest callers/workers/JNI/module callbacks quiesce,
on an attached JNI thread while Host and Context remain alive. It deletes its
weak Context reference and releases cache roots; original native refs are not
intercepted. Callback bodies retain only weak adapter state and stop after
retirement. CheckPersistence is a quiesced snapshot, not a concurrent close
fence. JNI numeric support must be the separately accepted strict I/F core
checkpoint; F arguments/results use exact binary32 bits.

Original migration facts and pinned Android13 contracts are preserved in
`work/playerprefs-audit/PROPOSAL.md` and its evidence ledger. Uri.encode uses
the original android/net/Uri owner and percent-escapes UTF8 bytes, preserves
null and unchanged object identity, allows `_-!.~'()*` plus letters/digits,
and follows Java UTF8 malformed-surrogate replacement. It does not use form
encoding, Base64, or URLEncoder.

`test_shared_preferences.py --out <NEW-directory> --host <accepted-numeric-commit>`
freezes committed support plus only the seven owned executable overlays.
Strict NDK TEST callers exercise direct/V/A, real store/editor data flow and
the decoded migration API sequence. They do not execute Unity's original
migration body or substitute for the later natural game frame. Windows tests
also prove persistence/reload and corrupt registry rejection in exclusively
owned temporary keys. Linux uses an explicitly labelled TEST memory backend;
the Windows factory remains unsupported there. Existing JNI/frame regressions
are run once each with the same exact frozen sources.

Actual game10 continued after the original missing getSharedPreferences method
error: Unity's original JNI TLS error policy suppressed that scope's later
operations, then cleared the error at scope exit. Natural IL2CPP loading was
observed afterward. That is neither a preference initialization/persistence
proof nor evidence that this provider is the current load blocker; the
read-only follow-up is `work/playerprefs-game10-catch-audit/REPORT.md`.

Accepted numeric support freeze `a4a99d93ac2b21d0beff869baf8d080f0598f676`
plus seven owned executable overlays ran in `work/shared-preferences1`:
Windows1,052 focused checks, Linux643; five expected named boundaries each;
strict NDK21 healthy traces/one object each, zero unsupported/direct gaps.
Existing JNI36/callback464/constructor362 passed once per host. The runner
rehashed every frozen support/owned source and all evidence after execution.
Windows-only extra checks use real exclusively owned registry keys; Linux's
backing is explicitly TEST memory and does not claim Windows persistence.
