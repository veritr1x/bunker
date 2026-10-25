#!/bin/bash
# Runs in the dev image: builds and runs the AArch64 differential tests. Each test
# runs an instruction natively, then its lifted version, and compares the states.
#   test_in_dev.sh [gtest filter, e.g. '*FADD*']
set -euo pipefail
cmake --build build-dev --target test_dependencies > /tmp/test-build.log 2>&1 || { tail -40 /tmp/test-build.log; exit 1; }
# gflags parses the command line first and rejects --gtest_* flags, so use gtest's environment variables.
GTEST_FILTER="${1:-*}" GTEST_BRIEF=1 build-dev/tests/AArch64/run-aarch64-tests > /recomp/work/remill-test.log 2>&1 || true
{ grep -E "^\[  FAILED  \] GeneralInstrTest" /recomp/work/remill-test.log || true; } |
    sed 's/, where.*//; s/.*SemanticsMatchNative\//FAILED /' | sort -u
tail -2 /recomp/work/remill-test.log
