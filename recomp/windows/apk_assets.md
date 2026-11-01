# APK asset reader

`ApkAssets` reads real `assets/` ZIP members directly from a configured APK.
It returns private native bytes; JNI references, streams and guest publication
belong to the caller. No extraction, Java execution or asset success stub is
involved. Independent file streams allow concurrent `Read` calls after construction.
Keep the configured APK unchanged for the reader's lifetime.

The bounded ZIP implementation accepts stored and raw-deflate members, including
empty files and signed/unsigned data descriptors. It verifies directory/local
metadata, member bounds, complete deflate input/output and CRC32. Relative asset
names are case sensitive UTF-8 byte strings; absolute, empty, backslash, NUL and
dot/traversal components are rejected. Duplicate asset names are rejected.
Split archives, ZIP64, encryption and other compression/flag features are
explicitly unsupported. It implements the needed APK subset of the
[PKWARE ZIP format](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT),
not a general archive validator. APK signature verification is outside this
reader. Output allocations follow the member's checked 32-bit declared size.

`test_apk_assets.py` builds with strict compiler warnings and compares an
independent Python `zipfile` writer/reader against the native reader. Both
Windows GCC 15.2 (static pinned zlib 1.3.2) and Linux Clang 18 passed **69 checks**:
stored/deflated/empty/Unicode assets, descriptors, malformed metadata, paths,
duplicates, unsupported features, truncation, corrupt streams and CRCs. The
original game APK's `bin/Data/boot.config` matched all **149 bytes**, CRC32
`f53e2d64`. Original game bytes are not committed.

```powershell
python recomp/windows/test_apk_assets.py --apk C:/path/to/game.apk
```

The default Windows paths use the existing ignored `recomp/work/zlib-native`
source/static backend. Linux can pass `--cxx clang++-18 --zlib-include /usr/include
--zlib-library /usr/lib/x86_64-linux-gnu/libz.a --out /path/to/build`.
