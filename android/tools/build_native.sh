#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
sdk_dir="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ndk_dir="${ANDROID_NDK_HOME:-$sdk_dir/ndk/27.2.12479018}"
case "$(uname -s)" in Darwin) host_tag=darwin-x86_64;; Linux) host_tag=linux-x86_64;; *) echo "Use macOS or Linux to build the native library" >&2; exit 1;; esac
export CC="$ndk_dir/toolchains/llvm/prebuilt/$host_tag/bin/aarch64-linux-android26-clang"
version="$(python3 "$root_dir/scripts/version.py")"
export GOOS=android GOARCH=arm64 CGO_ENABLED=1
cd "$root_dir/server"
test -f gen/proto/user.pb.go || { echo "Generate protobuf first: cd server && make proto" >&2; exit 1; }
mkdir -p ../android/app/src/main/jniLibs/arm64-v8a
# Bunker's version for the launcher APK (build_info.py reads it into build.json).
mkdir -p ../android/app/src/main/assets/lunar
printf '%s\n' "$version" > ../android/app/src/main/assets/lunar/bunker-version.txt
# The launcher rebuilds itself for an update (bunker_update.py) with the same
# tools and public signing key as the web builder.
rm -rf ../android/app/src/main/python/bunker_tools && mkdir -p ../android/app/src/main/python/bunker_tools ../android/app/src/main/assets/lunar/signing
cp ../android/tools/apk_sign.py ../android/tools/assemble_apk.py ../android/tools/axml.py ../android/tools/build_info.py ../android/tools/notice_pack.py ../android/app/src/main/python/bunker_tools/
: > ../android/app/src/main/python/bunker_tools/__init__.py
cp ../web/signing/bunker-key.pem ../web/signing/bunker-cert.der ../android/app/src/main/assets/lunar/signing/
go build -buildmode=c-shared -trimpath -ldflags="-s -w -X lunar-tear/server/internal/bunkerversion.Version=$version -extldflags=-Wl,-z,max-page-size=16384,-z,common-page-size=16384" \
  -o ../android/app/src/main/jniLibs/arm64-v8a/liblunar.so ./cmd/android-bridge
# Frame rate and resolution choices, applied in the game's process (DisplayPatch.java).
"$CC" -shared -fPIC -O2 -Wall -Wextra -Werror -s -Wl,-z,max-page-size=16384,-z,common-page-size=16384 \
  -o ../android/app/src/main/jniLibs/arm64-v8a/libbunkerdisplay.so ../android/app/src/main/cpp/display_patch.c ../android/app/src/main/cpp/roulette_ads.c ../android/app/src/main/cpp/text_buffer.c -llog
