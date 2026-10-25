#!/bin/bash
# Host side: lifts the prepared samples of each library with one Remill image and reports.
#   recomp/coverage.sh <image> <tag> <library>...
set -euo pipefail
RECOMP=$(cd "$(dirname "$0")" && pwd)
image=$1 tag=$2
shift 2
for lib in "$@"; do
    [[ -f $RECOMP/work/coverage/$lib/samples.txt ]] || (cd "$RECOMP" && python3 coverage.py prepare --lib "$lib")
    docker run --rm -v "$RECOMP:/recomp" "$image" /recomp/coverage_lift.sh "$lib" "$tag" \
        2> >(grep -v "requested image's platform" >&2)
    (cd "$RECOMP" && python3 coverage.py report --lib "$lib" --tag "$tag")
done
