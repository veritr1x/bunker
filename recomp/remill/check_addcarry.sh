#!/bin/bash
# Run on an x86_64 Linux host with clang++, or inside the dev image.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(dirname "$HERE")/work/remill-src
WORK=$(dirname "$HERE")/work
[[ $(uname -m) == x86_64 ]] || { echo 'This check requires x86_64.' >&2; exit 1; }
"${CXX:-clang++}" -std=c++17 -O2 -DADDRESS_SIZE_BITS=64 \
    -ffunction-sections -fdata-sections -Wl,--gc-sections \
    -I"$SRC/include" -I"$SRC" "$HERE/check_addcarry.cpp" -o "$WORK/check-addcarry"
"$WORK/check-addcarry"
