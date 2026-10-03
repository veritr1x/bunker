#!/usr/bin/env bash
# Build LunarTear.framework: the Go server (static archive) plus the launcher.
# Usage: build_framework.sh <patched-master.bin.e> <output-dir> [original-master.bin.e]
# The original master data lets Tools' content presets start from it.
# Set LUNAR_IOS_SIMULATOR=1 for an Apple-silicon simulator build (testing only).
set -euo pipefail
root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
master="$1"; out="$2"; original="${3:-}"
min_ios=14.0
if [ "${LUNAR_IOS_SIMULATOR:-}" = 1 ]; then
    platform=iphonesimulator; target="arm64-apple-ios$min_ios-simulator"; work="$root_dir/.build/ios-simulator"
else
    platform=iphoneos; target="arm64-apple-ios$min_ios"; work="$root_dir/.build/ios"
fi
sdk="$(xcrun --sdk $platform --show-sdk-path)"
clang="$(xcrun --sdk $platform -f clang)"
mkdir -p "$work" "$out"
test -f "$root_dir/server/gen/proto/user.pb.go" || { echo "Generate protobuf first: cd server && make proto" >&2; exit 1; }

# The bridge is shared with Android. Its JNI file is compiled only for Android.
(cd "$root_dir/server" && env GOOS=ios GOARCH=arm64 CGO_ENABLED=1 \
    CC="$clang -isysroot $sdk -target $target" \
    CGO_CFLAGS="-isysroot $sdk -target $target" \
    CGO_LDFLAGS="-isysroot $sdk -target $target" \
    go build -buildmode=c-archive -trimpath -ldflags='-s -w' -o "$work/liblunar.a" ./cmd/android-bridge)

framework="$out/LunarTear.framework"
rm -rf "$framework"; mkdir -p "$framework"
"$clang" -isysroot "$sdk" -target "$target" -fobjc-arc -O2 -Wall -Werror=implicit-function-declaration \
    -dynamiclib -install_name @rpath/LunarTear.framework/LunarTear -I "$work" -I "$root_dir/ios/launcher" \
    "$root_dir/ios/launcher/LunarLauncher.m" "$root_dir/ios/launcher/LunarTools.m" "$root_dir/ios/launcher/rebind.c" "$work/liblunar.a" \
    -framework UIKit -framework WebKit -framework Foundation -framework SystemConfiguration -framework UniformTypeIdentifiers -framework Security -framework CoreFoundation -framework CoreGraphics -lresolv \
    -o "$framework/LunarTear"
cp "$root_dir/ios/launcher/Info.plist" "$framework/Info.plist"
cp "$master" "$framework/20240404193219.bin.e"
if [ -n "$original" ]; then cp "$original" "$framework/original-master.bin.e"; fi
cp "$root_dir/LICENSE" "$framework/LUNAR_TEAR_LICENSE.txt"
echo "Built $framework"
