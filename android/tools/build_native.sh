#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
sdk_dir="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ndk_dir="${ANDROID_NDK_HOME:-$sdk_dir/ndk/27.2.12479018}"
case "$(uname -s)" in Darwin) host_tag=darwin-x86_64;; Linux) host_tag=linux-x86_64;; *) echo "Use macOS or Linux to build the native library" >&2; exit 1;; esac
export CC="$ndk_dir/toolchains/llvm/prebuilt/$host_tag/bin/aarch64-linux-android26-clang"
export GOOS=android GOARCH=arm64 CGO_ENABLED=1
cd "$root_dir/server"
test -f gen/proto/user.pb.go || { echo "Generate protobuf first: cd server && make proto" >&2; exit 1; }
mkdir -p ../android/app/src/main/jniLibs/arm64-v8a
go build -buildmode=c-shared -trimpath -ldflags='-s -w -extldflags=-Wl,-z,max-page-size=16384,-z,common-page-size=16384' \
  -o ../android/app/src/main/jniLibs/arm64-v8a/liblunar.so ./cmd/android-bridge
