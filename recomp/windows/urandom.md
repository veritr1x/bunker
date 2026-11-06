# Windows entropy for the original IL2CPP RNG

`FileSystem` supplies the normalized `/dev/urandom` path from the Windows system
random generator. An explicit file or directory mount covering that path retains
its existing authority. Other device paths and host paths keep their previous
resolution rules.

The original IL2CPP helper at `0x82551398` opens the literal `/dev/urandom` with
flags zero and caches the signed descriptor at `0x879821f8`. The helper at
`0x825513cc` reads the remaining requested bytes and retries guest `EINTR` (4).
This implementation supplies those existing `open` and `read` imports. It does
not replace the managed RNG, crypto methods, or their results.

The private descriptor backend shares the existing descriptor namespace and open
description ownership. Each read requests at most 65,536 bytes from the genuine
`BCryptGenRandom(nullptr, output, size, BCRYPT_USE_SYSTEM_PREFERRED_RNG)` loaded
from system32. A successful native chunk is published with `WriteGuestMemory`.
A failed native chunk publishes no bytes; the read returns an earlier completed
prefix, or `-1` with guest `EIO` (5). Missing native support fails with
`EOPNOTSUPP` (95). There is no seeded, constant, or other random fallback.
The guarded device read, close, dup, write, seek, stat, and access paths restore
native errno, LastError, and floating environment. Open has that guard after
the existing general flag validation recognizes the device path. This claim does
not cover mmap rejection, general flag rejection, or unknown/closed descriptors.

The supported device profile is read-only. Flags zero and nonmutating
close-on-exec, large-file, no-follow, no-controlling-terminal and nonblocking hints
are accepted; mutation flags are unsupported. Null with count zero returns zero;
positive null, overflowing output ranges, and counts outside signed 64-bit range
are rejected. Writes fail `EBADF`. `dup` creates an independently closeable
descriptor, shares its open description, and clears close-on-exec on the copy.
Closing a descriptor cannot close another duplicate. Existing I/O locks and
shared ownership cover concurrent close/read operations.

`stat` and `fstat` describe a virtual read-only character device, mode `0020444`,
device number 1:9, inode 9, zero size, and block size 4096. These are compatibility
metadata, not an assertion about a Windows filesystem inode or ACL. Valid seek
origins return zero without changing an offset, matching Linux urandom's
`noop_llseek`; invalid origins fail `EINVAL`. Device-backed mmap fails `ENODEV`.
Stream APIs, writable entropy injection, RNG ioctls, and other Linux random-device
features are outside this profile.

The source and whole-file inverse are frozen in
`work/urandom-source-preparation1/production-sources1.json` (SHA-256
`9ec4a5f01506a302a8debc392b1b09074c943c78930c6535a1d92f531925d80a`).
Its syntax qualification covers the candidate with the existing header closure.
The focused runtime qualification is separate; a successful component test does
not establish a visible game frame or a statistical randomness claim.

The focused gate `work/urandom-qualification2/acceptance.json` (SHA-256
`25b13a7b887f846f6fd2e21f435d13f85cc491c39a7c30e1f61bf3092c75183a`)
passes 597 checks. It executes the two original RNG functions, observes real
BCrypt output through installed filesystem imports, and checks two genuine
native failures without publishing the failed chunks. It also checks descriptor
duplication/cleanup and one ordinary-file regression. The fixture's failure route
deliberately omits the algorithm handle while clearing the system-RNG flag; it is test-only and
does not describe an observed production OS failure. The retained fixture and
runner are `urandom_guest.c`, `urandom_test.cpp`, and `test_urandom.py`.

The native API contract is documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptgenrandom).
The Linux random-device file operations use `noop_llseek` in the
[kernel source](https://linux.googlesource.com/linux/kernel/git/torvalds/linux/+/e96493229a6399e902062213c6381162464cdd50/drivers/char/random.c).
