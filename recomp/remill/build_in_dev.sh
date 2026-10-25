#!/bin/bash
# Runs in the dev image: incremental build of remill with the AArch64 tests.
set -euo pipefail
LLVM_PREFIX=$(llvm-config-$LLVM_VERSION --prefix)
if [[ ! -f dependencies/install/.built ]]; then
    cmake -G Ninja -S dependencies -B dependencies/build -DUSE_EXTERNAL_LLVM=ON "-DCMAKE_PREFIX_PATH=$LLVM_PREFIX"
    cmake --build dependencies/build
    touch dependencies/install/.built
fi
if [[ ! -f build-dev/build.ninja ]]; then
    cmake -G Ninja -B build-dev "-DCMAKE_PREFIX_PATH=$LLVM_PREFIX;/remill/dependencies/install" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DREMILL_ENABLE_TESTING=ON -DREMILL_ENABLE_TESTING_AARCH64=ON -DREMILL_ENABLE_TESTING_X86=OFF \
        -DREMILL_ENABLE_TESTING_SLEIGH_THUMB=OFF -DREMILL_ENABLE_TESTING_SLEIGH_PPC=OFF \
        -DREMILL_ENABLE_DIFFERENTIAL_TESTING=OFF
fi
cmake --build build-dev
echo "Built remill: $(ls build-dev/bin/lift/remill-lift-* 2>/dev/null || find build-dev -name 'remill-lift-*' -type f | head -1)"
