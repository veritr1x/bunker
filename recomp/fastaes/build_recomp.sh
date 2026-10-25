#!/bin/bash
# Runs in the recomp image: compiles the lifted IR for x86_64, links it with the
# runtime and records the output. Run lift.sh first.
set -euo pipefail
OUT=/recomp/work/fastaes
CLANG=/opt/trailofbits/remill/bin/remill-clang-11.0
INCLUDE=/opt/trailofbits/remill/include
cd "$OUT"
# Both modules lift the shared helpers (key expansion, PLT stubs) under the same
# names, so give each module's functions its own prefix.
for m in enc dec; do
    sed "s/@sub_/@${m}_sub_/g" $m.ll > $m.renamed.ll
    $CLANG -O2 -c -Wno-override-module $m.renamed.ll -o $m.o
done
# Remill's clang ships without its builtin headers (stddef.h), so the glue builds with GCC.
gcc -O1 -Wall -c /recomp/fastaes/elfload.c -o elfload.o
g++ -O1 -std=c++17 -Wall -Wno-unknown-pragmas -I"$INCLUDE" -I/recomp/fastaes -c /recomp/fastaes/recomp_x86.cpp -o runtime.o
g++ -o recomp enc.o dec.o elfload.o runtime.o -latomic
./recomp > recomp.txt
echo "Recompiled: $(wc -l < recomp.txt) calls ($(uname -m))"
