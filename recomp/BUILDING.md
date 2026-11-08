# Building from a fresh clone

The port source and Remill changes are published, but the latest verified game
executable is **not yet reproducible from a fresh clone using one documented
build command**. This is a development branch, not a standalone release.

## Get both repositories

Run in an empty parent directory; do not replace an existing checkout:

```sh
git clone --branch recomp-x86_64 --single-branch https://github.com/veritr1x/bunker.git bunker
cd bunker
git clone --branch bunker --single-branch https://github.com/veritr1x/remill.git recomp/work/remill-src
git -C recomp/work/remill-src checkout --detach 1187c09aef09e130a2abe4605fced3cfb5a62bf9
```

Remill is a separate repository, not a submodule. Cloning Bunker alone does not
download it. The pinned commit above is the pushed compiler source revision at
this checkpoint. Generated lifters and semantics must be built and kept as a
matching pair; a source commit alone is not an accepted binary snapshot.

## What contributors can build

The generic ELF planner/compiler, Remill source, Windows providers and component
fixtures are tracked. Start with [whole-library instructions](whole/README.md)
and [Windows component instructions](windows/README.md). Python dependencies are
pinned in `whole/requirements.txt`.

The native port used WSL/Linux LLVM/Clang18, Python3.12, Android NDK
27.2.12479018 and native Windows MinGW GCC/G++15.2. ARM64 reference tests also
need the appropriate cross-sysroot and QEMU. The existing Dockerfiles default
to LLVM22; that default is not the accepted LLVM18 game-build snapshot. Do not
mix objects or semantics from incompatible compiler snapshots.

The game APK/libraries and required data must be supplied separately. They are
not distributed by this repository. Runtime dependencies such as ANGLE and the
matching Firebase SDK are also separate inputs.

## Remaining reproducibility gap

The frame-verified executable uses a selected, qualified combination of generated
guest objects and overlays. Its manifests, acceptance receipts, link responses,
compiler binaries and execution controllers live in ignored `recomp/work/`.
Several producers depend on those prior artifacts and machine-specific paths.
For example, `windows/game_bootstrap_build.ps1` requires a prepared
`game_inputs.json`; it does not generate the latest selected cohort from an APK.

A new contributor therefore cannot currently clone this branch and reproduce
the latest frame-verified executable without reconstructing that local build
state. A portable, tracked entry point must still regenerate the selected
cohort, propagate its new qualification hashes, assemble the host/runtime inputs
and run the original startup test. Copying a local command or ignoring failed
provenance checks does not close this gap.

Accepted local artifacts remain preserved. They were intentionally not committed
or uploaded as part of the source push. See [current status](TODO.md) and
[execution evidence](windows/first_frame.md) for what has actually run.
