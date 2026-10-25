#!/bin/bash
# Runs in the dev image: removes the built AArch64 semantics bitcode and the lifted
# tests, so the next build recompiles them. The semantics build step does not
# track the Semantics/*.cpp files that Instructions.cpp includes.
set -euo pipefail
find build-dev -name '*aarch64*.bc' -print -delete
find build-dev -path '*Arch/AArch64/Runtime*' -name '*.o' -print -delete
