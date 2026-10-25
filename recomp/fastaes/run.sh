#!/bin/bash
# Host side: builds the images and runs one stage, or all of them.
#   recomp/fastaes/run.sh [images|lift|ref|recomp|all]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RECOMP=$(dirname "$HERE")
stage=${1:-all}
# Each image is single-platform (set in its Dockerfile). Passing --platform here makes
# Docker Desktop's containerd store miss the locally built image, so leave it out.
in_recomp() { docker run --rm -v "$RECOMP:/recomp" bunker-recomp "$@" 2> >(grep -v "requested image's platform" >&2); }
in_ref() { docker run --rm -v "$RECOMP:/recomp" bunker-recomp-ref "$@"; }
if [[ $stage == images || $stage == all ]]; then
    docker build -q -t bunker-recomp -f "$HERE/Dockerfile.recomp" "$HERE"
    docker build -q -t bunker-recomp-ref -f "$HERE/Dockerfile.ref" "$HERE"
fi
[[ $stage == lift || $stage == all ]] && in_recomp /recomp/fastaes/lift.sh
[[ $stage == ref || $stage == all ]] && in_ref /recomp/fastaes/build_ref.sh
[[ $stage == recomp || $stage == all ]] && in_recomp /recomp/fastaes/build_recomp.sh
exit 0
