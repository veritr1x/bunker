#!/bin/bash
# Runs in the dev image: regenerates the AArch64 test harness's checked-in state
# save/restore assembly from tests/AArch64/Print{Save,Restore}State.cpp.
set -euo pipefail
for which in Save Restore; do
    clang++-$LLVM_VERSION -std=c++17 -Wno-everything -I/remill/include -I/remill \
        -o /tmp/print$which tests/AArch64/Print${which}State.cpp
    /tmp/print$which > generated/Arch/AArch64/${which}State.S
    echo "generated/Arch/AArch64/${which}State.S: $(wc -l < generated/Arch/AArch64/${which}State.S) lines"
done
