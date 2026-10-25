#!/bin/bash
# Runs in a Remill image: lifts every sample coverage.py prepared, on all cores,
# and writes "<index> ok|error|fail" per sample to results.<tag>.txt.
#   coverage_lift.sh <library> <tag>
set -uo pipefail
DIR=/recomp/work/coverage/$1
TAG=$2
LIFT=$(ls /opt/trailofbits/remill/bin/remill-lift-* /opt/remill/bin/remill-lift-* 2>/dev/null | head -1)
[[ -x $LIFT ]] || { echo "No remill-lift in this image"; exit 1; }
export LIFT
lift_one() {
    local ir
    ir=$(mktemp)
    if ! "$LIFT" --arch aarch64 --os linux --bytes "$2" --address $((0x10000000)) --ir_out "$ir" > /dev/null 2>&1; then
        echo "$1 fail"
    elif grep -q "@__remill_error(" "$ir" && grep -q "call.*@__remill_error(" "$ir"; then
        echo "$1 error"
    else
        echo "$1 ok"
    fi
    rm -f "$ir"
}
export -f lift_one
xargs -P "$(nproc)" -L 1 bash -c 'lift_one "$0" "$1"' < "$DIR/samples.txt" | sort -n > "$DIR/results.$TAG.txt"
echo "Lifted $(wc -l < "$DIR/results.$TAG.txt") samples with $(basename "$LIFT") on $(nproc) cores"
