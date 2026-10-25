#!/bin/bash
# Remill development loop, in the dev image with recomp/work/remill-src mounted.
#   recomp/remill/dev.sh image        build the dev image
#   recomp/remill/dev.sh build        dependencies (first time), configure, build remill and the AArch64 tests
#   recomp/remill/dev.sh test [regex] run the AArch64 differential tests (native vs lifted)
#   recomp/remill/dev.sh run <script> run a script from recomp/ inside the container
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RECOMP=$(dirname "$HERE")
SRC=$RECOMP/work/remill-src
# The build directory and ccache live in Docker volumes: git (used by the sleigh
# fetch) fails with "does not match index" on a macOS bind mount, and builds are faster there.
in_dev() {
    docker run --rm -v "$SRC:/remill" -v bunker-remill-build:/remill/build-dev -v bunker-remill-ccache:/ccache \
        -v "$RECOMP:/recomp" -e CCACHE_DIR=/ccache -w /remill bunker-remill-dev "$@"
}
case ${1:-} in
image) docker build -q -t bunker-remill-dev -f "$HERE/Dockerfile.dev" "$HERE" ;;
build) in_dev /recomp/remill/build_in_dev.sh ;;
test) in_dev /recomp/remill/test_in_dev.sh "${2:-}" ;;
run) in_dev "/recomp/${2:?script}" "${@:3}" ;;
*) sed -n 2,7p "$0"; exit 1 ;;
esac
