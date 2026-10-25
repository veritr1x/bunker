#!/bin/bash
# Prints the offsets of AArch64 State's status-register fields (dev image).
cat > /tmp/offsets.cpp <<'EOF'
#include <cstddef>
#include <cstdio>
#include "remill/Arch/AArch64/Runtime/State.h"
#define F(f) printf("%5zu %s\n", offsetof(State, f), #f);
int main() {
  F(sr.n) F(sr.z) F(sr.c) F(sr.v) F(sr.ixc) F(sr.ofc) F(sr.ufc) F(sr.idc) F(sr.ioc) F(sr.dzc)
  F(sr.tpidr_el0)
}
EOF
clang++-$LLVM_VERSION -std=c++17 -Wno-everything -I/remill/include -o /tmp/offsets /tmp/offsets.cpp && /tmp/offsets | sort -n
