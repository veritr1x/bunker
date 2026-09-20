# Bundled launcher tools

Lunar Base is a pinned submodule from <https://github.com/NMeliksah/lunar-base>, commit
`b39154099b8f09f5926239e5838abc37260b9b9b` (version 2.10.0).
The build copies its MIT license and third-party notices into
`app/src/main/python/web/`. Android changes are maintained in `../overlays/`
and `../patches/`; generated copies are ignored by Git.
The Go grant engine is generated in `../server/internal/lunarbase/`, with its license. Android grant validation rejects batches which would overflow
the game's 32-bit inventory counts before making any changes.
The Python web app uses an Android adapter for private paths, JNI grants,
serialized requests, session authentication, database restoration and snapshots.
Templates and CSS are adapted for the launcher and small screens.

The content patcher is a pinned submodule from
<https://github.com/NavHobbyDev/lunar-tear-masterdata-patcher>, commit
`9b6cd167b51dd3b84be200faf92877b4408c1901`.
The build copies its source, MIT license, config, README and ID reference into
`app/src/main/python/patcher/`. The launcher exposes all six standard presets
and all eighteen advanced splits, generating a selected variant on demand.

Both upstream projects identify `lunar-scripts` as the source of some included
files and note that it has no explicit license. Their notices are preserved.
No game data is included in the source tree intended for Git.

Chaquopy 17.0.0 supplies Python 3.11 inside the APK; no external Python app is
needed. Python dependencies include their own package license metadata.
`vendor/wheels/msgpack-1.1.1-py3-none-any.whl` is the upstream MessagePack 1.1.1
pure Python distribution, built with:

```sh
MSGPACK_PUREPYTHON=1 python3.11 -m pip wheel --no-deps --no-binary msgpack \
  msgpack==1.1.1 -w android/vendor/wheels
```

The native server comes from the pinned
[Lunar Tear](https://gitlab.com/walter-sparrow-group/lunar-tear) submodule,
with its MIT license preserved in `../LICENSE` and inside the APK.
[Lunar Scripts](https://gitlab.com/walter-sparrow-group/lunar-scripts) is also a
pinned submodule, used to patch local copies of the APK and master data.
All four exact commits are recorded in `../upstream.lock.json` and Git's submodule entries.
The launcher does not execute a downloaded grant binary or expose editing on LAN.
