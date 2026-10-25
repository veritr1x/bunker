#!/bin/bash
# Runs in the ARM64 image: builds the reference harness and records its output.
set -euo pipefail
OUT=/recomp/work/fastaes
mkdir -p "$OUT"
cc -O1 -Wall -o "$OUT/ref" /recomp/fastaes/ref_arm64.c /recomp/fastaes/elfload.c
"$OUT/ref" > "$OUT/ref.txt"
echo "Reference: $(wc -l < "$OUT/ref.txt") calls ($(uname -m))"
