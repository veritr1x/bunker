# Remill v6 with LLVM 22, after upstream's Dockerfile minus its test stage, plus
# clang and a C/C++ toolchain to compile and link lifted code in the same image.
# Builds for the host's architecture: ARM64 on Apple Silicon, x86_64 on Windows.
#   docker build -t bunker-remill6 -f recomp/remill/Dockerfile recomp/work/remill-src
ARG LLVM_VERSION=22
FROM ubuntu:24.04 AS builder
ARG LLVM_VERSION
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends lsb-release wget software-properties-common gnupg \
        cmake ninja-build python3 git ca-certificates build-essential \
    && wget -q https://apt.llvm.org/llvm.sh && chmod +x llvm.sh && ./llvm.sh ${LLVM_VERSION} \
    && apt-get install -y --no-install-recommends llvm-${LLVM_VERSION}-dev \
    && rm -rf /var/lib/apt/lists/* llvm.sh
ENV CC=clang-${LLVM_VERSION} CXX=clang++-${LLVM_VERSION}
WORKDIR /remill
COPY . .
RUN git config --global --add safe.directory /remill \
    && cmake -G Ninja -S dependencies -B dependencies/build -DUSE_EXTERNAL_LLVM=ON \
        "-DCMAKE_PREFIX_PATH=$(llvm-config-${LLVM_VERSION} --prefix)" \
    && cmake --build dependencies/build
RUN cmake -G Ninja -B build "-DCMAKE_PREFIX_PATH=$(llvm-config-${LLVM_VERSION} --prefix);/remill/dependencies/install" \
        -DCMAKE_INSTALL_PREFIX=/opt/remill -DCMAKE_BUILD_TYPE=Release -DREMILL_ENABLE_TESTING=OFF \
    && cmake --build build && cmake --install build

FROM ubuntu:24.04
ARG LLVM_VERSION
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends lsb-release wget software-properties-common gnupg \
        ca-certificates build-essential python3 \
    && wget -q https://apt.llvm.org/llvm.sh && chmod +x llvm.sh && ./llvm.sh ${LLVM_VERSION} \
    && apt-get install -y --no-install-recommends llvm-${LLVM_VERSION} clang-${LLVM_VERSION} lld-${LLVM_VERSION} \
    && rm -rf /var/lib/apt/lists/* llvm.sh
COPY --from=builder /opt/remill /opt/remill
ENV PATH="/opt/remill/bin:/usr/lib/llvm-${LLVM_VERSION}/bin:${PATH}"
