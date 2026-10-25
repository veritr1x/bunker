#!/bin/bash
# Clones Remill v6.0.1 into recomp/work/remill-src and applies our patches on a
# `bunker` branch. To refresh the patches after committing in remill-src:
#   recomp/remill/fetch.sh export
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(dirname "$HERE")/work/remill-src
if [[ ${1:-} == export ]]; then
    rm -f "$HERE"/patches/*.patch
    git -C "$SRC" format-patch -q -o "$HERE/patches" v6.0.1..bunker
    ls "$HERE/patches"
    exit 0
fi
[[ -d $SRC ]] && { echo "$SRC already exists"; exit 1; }
git clone -q --branch v6.0.1 https://github.com/lifting-bits/remill "$SRC"
git -C "$SRC" switch -q -c bunker
git -C "$SRC" am -q "$HERE"/patches/*.patch
git -C "$SRC" log --oneline v6.0.1..bunker
