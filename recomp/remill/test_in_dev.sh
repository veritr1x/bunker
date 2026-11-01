#!/bin/bash
# Runs in the dev image: builds and runs the AArch64 differential tests. Each test
# runs an instruction natively, then its lifted version, and compares the states.
#   test_in_dev.sh [gtest filter, e.g. '*FADD*']
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
LOG=$HERE/../work/remill-test.log
cmake --build build-dev --target test_dependencies > /tmp/test-build.log 2>&1 || { tail -40 /tmp/test-build.log; exit 1; }
if [[ ! -x build-dev/tests/AArch64/run-aarch64-tests ]]; then
    echo 'AArch64 differential tests are unavailable in this build. Build and run on an ARM64 host/image.' >&2
    echo 'On x86_64, remill/check_addcarry.sh checks ADC/ADCS semantics directly.' >&2
    exit 1
fi
# gflags parses the command line first and rejects --gtest_* flags, so use gtest's environment variables.
status=0
GTEST_FILTER="${1:-*}" GTEST_BRIEF=1 build-dev/tests/AArch64/run-aarch64-tests > "$LOG" 2>&1 || status=$?
{ grep -E "^\[  FAILED  \] GeneralInstrTest" "$LOG" || true; } |
    sed 's/, where.*//; s/.*SemanticsMatchNative\//FAILED /' | sort -u
tail -2 "$LOG"
exit "$status"
