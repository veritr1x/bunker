#!/bin/bash
# Clones our Remill fork (the `bunker` branch: Remill v6.0.1 plus our AArch64
# work) into recomp/work/remill-src. Changes are committed and pushed there.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(dirname "$HERE")/work/remill-src
[[ -d $SRC ]] && { echo "$SRC already exists"; exit 1; }
git clone -q --branch bunker https://github.com/veritr1x/remill "$SRC"
git -C "$SRC" remote add upstream https://github.com/lifting-bits/remill
git -C "$SRC" log --oneline -4
