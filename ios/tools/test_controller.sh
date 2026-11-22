#!/usr/bin/env bash
# Exercise the real UIKit and GameController adapters without distributing game files.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
work="$(mktemp -d)"
app="$work/ControllerTest.app"
bundle=org.veritr1x.bunker.padtest
mkdir -p "$app"
sdk="$(xcrun --sdk iphonesimulator --show-sdk-path)"
xcrun --sdk iphonesimulator clang -isysroot "$sdk" -target "$(uname -m)-apple-ios14.0-simulator" \
    -fobjc-arc -I "$root/android/app/src/main/cpp" "$root/ios/devtools/ControlHost/PadInputTest.m" \
    -framework UIKit -framework Foundation -framework CoreGraphics -framework GameController -framework QuartzCore -framework WebKit -o "$app/ControllerTest"
python3 - "$app/Info.plist" "$bundle" <<'PY'
import plistlib,sys
with open(sys.argv[1],"wb") as f:
    plistlib.dump(dict(CFBundleExecutable="ControllerTest",CFBundleIdentifier=sys.argv[2],
        CFBundleName="ControllerTest",CFBundlePackageType="APPL",CFBundleVersion="1",CFBundleShortVersionString="1",
        MinimumOSVersion="14.0",UILaunchScreen={},UIDeviceFamily=[1,2],
        UIApplicationSceneManifest={"UIApplicationSupportsMultipleScenes":False,"UISceneConfigurations":
        {"UIWindowSceneSessionRoleApplication":[{"UISceneConfigurationName":"Default","UISceneDelegateClassName":"Scene"}]}}),f)
PY
codesign -f -s - "$app"
# Use the runtime and device type of an installed, available iPhone simulator.
read -r type runtime < <(xcrun simctl list devices available -j | python3 -c '
import json,sys
pairs=[(d["deviceTypeIdentifier"],r) for r,ds in json.load(sys.stdin)["devices"].items()
       for d in ds if ".iOS-" in r and d["name"].startswith("iPhone")]
print(*pairs[-1])')
device="$(xcrun simctl create "Bunker controller test" "$type" "$runtime")"
trap 'xcrun simctl shutdown "$device" >/dev/null 2>&1 || true; xcrun simctl delete "$device"; rm -rf "$work"' EXIT
xcrun simctl boot "$device"
xcrun simctl bootstatus "$device" -b
xcrun simctl install "$device" "$app"
xcrun simctl launch "$device" "$bundle"
data="$(xcrun simctl get_app_container "$device" "$bundle" data)"
for _ in $(seq 1 45); do
    if [ -f "$data/Documents/result" ]; then
        result="$(cat "$data/Documents/result")"; echo "Controller test: $result"; test "$result" = PASS; exit
    fi
    sleep 1
done
echo "Controller test did not finish" >&2; exit 1
