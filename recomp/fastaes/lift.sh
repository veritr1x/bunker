#!/bin/bash
# Runs in the recomp image: lifts both exports of libFastAES.so to LLVM IR.
# The whole first (R E) segment is handed to Remill at the address the loader
# maps it to, so PC-relative data references (the S-boxes) land in real memory.
set -euo pipefail
LIB=/recomp/work/lib/libFastAES.so
OUT=/recomp/work/fastaes
BASE=$((0x10000000))
SEGMENT=$((0x2170))  # Size of the R E segment (llvm-readelf -l).
mkdir -p "$OUT"
HEX=$(head -c $SEGMENT "$LIB" | od -An -tx1 -v | tr -d ' \n')
lift() {  # name offset
    /opt/trailofbits/remill/bin/remill-lift-11.0 --arch aarch64 --os linux --bytes "$HEX" \
        --address $BASE --entry_address $((BASE + $2)) --ir_out "$OUT/$1.ll" 2> "$OUT/$1.lift.log"
    echo "Lifted $1: $(grep -c '^define' "$OUT/$1.ll") functions"
}
lift enc 0x66c
lift dec 0x1220
