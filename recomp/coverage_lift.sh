#!/bin/bash
# Runs in a Remill image: lifts each chunk that coverage.py prepared.
#   coverage_lift.sh <library> <tag>
set -uo pipefail
DIR=/recomp/work/coverage/$1
TAG=$2
LIFT=$(ls /opt/trailofbits/remill/bin/remill-lift-* /opt/remill/bin/remill-lift-* 2>/dev/null | head -1)
[[ -x $LIFT ]] || { echo "No remill-lift in this image"; exit 1; }
for hex in "$DIR"/chunk_*.hex; do
    base=${hex%.hex}
    if ! "$LIFT" --arch aarch64 --os linux --bytes "$(cat "$hex")" --address $((0x10000000)) \
            --ir_out "$base.$TAG.ll" > "$base.$TAG.log" 2>&1; then
        echo "$(basename "$hex"): remill-lift failed, see $base.$TAG.log"
    fi
done
echo "Lifted $(ls "$DIR"/chunk_*."$TAG".ll 2>/dev/null | wc -l) chunks with $(basename "$LIFT")"
