#!/usr/bin/env bash
# Launcher smoke test in a temporary iOS Simulator, without the game.
#
# A stand-in app loads a simulator build of LunarTear.framework. The test
# checks the setup screen with no game files, then starts the real embedded
# server with a placeholder catalog and calls its health and sign-in pages.
# The placeholder catalog does not prove gameplay or asset completeness.
# Usage: simulator_smoke.sh <patched-master.bin.e>
set -euo pipefail
root_dir="$(cd "$(dirname "$0")/../.." && pwd)"
master="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
work="$root_dir/.build/ios-simulator"
app="$work/Host.app"
bundle=org.veritr1x.bunker.smoke
# The simulator shares this Mac's network. When the server's ports are taken
# (for example by a web dev server on 3000), move the test's ports instead.
offset=0
for port in 8003 8080 3000; do
    if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then offset=20000; fi
done
for port in 8003 8080 3000; do
    if lsof -nP -iTCP:$((port + offset)) -sTCP:LISTEN >/dev/null 2>&1; then echo "Port $((port + offset)) is in use on this Mac; stop that service first" >&2; exit 1; fi
done
[ "$offset" = 0 ] || echo "Ports 8003/8080/3000 are in use on this Mac; testing on $((8003 + offset))/$((8080 + offset))/$((3000 + offset))"
export SIMCTL_CHILD_LUNAR_PORT_OFFSET=$offset
cdn_port=$((8080 + offset)) auth_port=$((3000 + offset))
LUNAR_IOS_SIMULATOR=1 "$root_dir/ios/tools/build_framework.sh" "$master" "$work/out"
rm -rf "$app"; mkdir -p "$app/Frameworks"
cat > "$work/main.m" <<'EOF'
#import <UIKit/UIKit.h>
@interface HostDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow *window;
@end
@implementation HostDelegate
- (BOOL)application:(UIApplication *)application didFinishLaunchingWithOptions:(NSDictionary *)options {
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    UIViewController *root = [UIViewController new];
    root.view.backgroundColor = UIColor.blackColor;
    UILabel *label = [UILabel new];
    label.text = @"Stand-in game";
    label.textColor = UIColor.whiteColor;
    label.frame = CGRectMake(20, 120, 300, 40);
    [root.view addSubview:label];
    self.window.rootViewController = root;
    [self.window makeKeyAndVisible];
    return YES;
}
@end
int main(int argc, char *argv[]) { @autoreleasepool { return UIApplicationMain(argc, argv, nil, @"HostDelegate"); } }
EOF
cat > "$app/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Host</string>
<key>CFBundleIdentifier</key><string>$bundle</string>
<key>CFBundleName</key><string>Host</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>MinimumOSVersion</key><string>14.0</string>
<key>UIFileSharingEnabled</key><true/>
<key>UILaunchScreen</key><dict/>
</dict></plist>
EOF
sdk="$(xcrun --sdk iphonesimulator --show-sdk-path)"
xcrun --sdk iphonesimulator clang -isysroot "$sdk" -target arm64-apple-ios14.0-simulator -fobjc-arc "$work/main.m" \
    -F "$work/out" -framework LunarTear -framework UIKit -Wl,-rpath,@executable_path/Frameworks -o "$app/Host"
cp -R "$work/out/LunarTear.framework" "$app/Frameworks/"
codesign -f -s - "$app/Frameworks/LunarTear.framework" >/dev/null 2>&1
codesign -f -s - "$app" >/dev/null 2>&1

runtime="$(xcrun simctl list runtimes available | awk '/iOS/ {id=$NF} END {print id}')"
device="$(xcrun simctl create "Lunar Tear smoke" "iPhone 17e" "$runtime")"
cleanup() { xcrun simctl shutdown "$device" >/dev/null 2>&1 || true; xcrun simctl delete "$device" >/dev/null 2>&1 || true; }
trap cleanup EXIT
xcrun simctl boot "$device"
xcrun simctl bootstatus "$device" -b >/dev/null
xcrun simctl install "$device" "$app"

health() { curl -fsS --max-time 2 "http://127.0.0.1:$cdn_port/companion/health" 2>/dev/null; }
wait_for() { for _ in $(seq 1 "$2"); do if eval "$1"; then return 0; fi; sleep 1; done; return 1; }

xcrun simctl launch "$device" "$bundle" >/dev/null
sleep 6
xcrun simctl io "$device" screenshot "$work/no-files.png" >/dev/null 2>&1
if health; then echo "FAIL: server started without game files" >&2; exit 1; fi
echo "PASS: no game files, server stays stopped and setup screen is shown ($work/no-files.png)"

documents="$(xcrun simctl get_app_container "$device" "$bundle" data)/Documents"
test -s "$documents/assets/release/20240404193219.bin.e" || { echo "FAIL: bundled master data was not installed" >&2; exit 1; }
echo "PASS: bundled master data copied into Documents"
mkdir -p "$documents/assets/revisions/0"
printf '\x08\x01' > "$documents/assets/revisions/0/list.bin"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for health 30 || { echo "FAIL: server did not start with a catalog" >&2; exit 1; }
grep -q "log opened" "$documents/logs/server.log" || { echo "FAIL: server log not saved in Documents/logs" >&2; exit 1; }
echo "PASS: embedded server answers on 127.0.0.1:$cdn_port; its log is saved in Documents/logs"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$auth_port/v18.0/dialog/oauth?redirect_uri=fb1://authorize")"
test "$code" = 200 || { echo "FAIL: sign-in page returned $code" >&2; exit 1; }
echo "PASS: sign-in page answers on 127.0.0.1:$auth_port"
sleep 2
xcrun simctl io "$device" screenshot "$work/running.png" >/dev/null 2>&1
test -s "$documents/saves/game.db" && test -s "$documents/saves/auth.key" || { echo "FAIL: saves were not created" >&2; exit 1; }
echo "PASS: saves created in Documents/saves"
# Relaunch must reuse the same save and auth key.
key="$(cat "$documents/saves/auth.key")"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
wait_for '! health' 10
xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for health 30 || { echo "FAIL: server did not restart" >&2; exit 1; }
test "$key" = "$(cat "$documents/saves/auth.key")" || { echo "FAIL: auth key changed across launches" >&2; exit 1; }
echo "PASS: relaunch restarts the server and keeps the auth key"
# Folder import: copy from a user folder (given as its parent), replace the
# current files, keep the current master data, and leave no staging folders.
source_root="$work/import-source"; rm -rf "$source_root"; mkdir -p "$source_root/assets/revisions/0/assetbundle/ui"
printf '\x08\x01' > "$source_root/assets/revisions/0/list.bin"
printf 'bundle' > "$source_root/assets/revisions/0/assetbundle/ui/sample.assetbundle"
printf '[]' > "$source_root/assets/revisions/0/info.json"
master_sum="$(shasum "$documents/assets/release/20240404193219.bin.e" | cut -d' ' -f1)"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$source_root" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -s '$documents/assets/revisions/0/assetbundle/ui/sample.assetbundle'" 30 || { echo "FAIL: import did not copy files" >&2; exit 1; }
wait_for "test ! -e '$documents/.assets-importing' && test ! -e '$documents/.assets-previous'" 30 || { echo "FAIL: import left staging folders" >&2; exit 1; }
test "$(shasum "$documents/assets/release/20240404193219.bin.e" | cut -d' ' -f1)" = "$master_sum" || { echo "FAIL: import lost master data" >&2; exit 1; }
test -s "$source_root/assets/revisions/0/list.bin" || { echo "FAIL: import changed the source" >&2; exit 1; }
echo "PASS: folder import replaces game files, keeps master data and the source"
# A folder without a catalog must be rejected without touching current files.
bad="$work/import-bad"; rm -rf "$bad"; mkdir -p "$bad/assets/revisions/0"; printf 'x' > "$bad/assets/revisions/0/other.bin"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$bad" xcrun simctl launch "$device" "$bundle" >/dev/null
sleep 5
test -s "$documents/assets/revisions/0/assetbundle/ui/sample.assetbundle" && test ! -e "$documents/assets/revisions/0/other.bin" || { echo "FAIL: rejected import changed files" >&2; exit 1; }
echo "PASS: invalid folder rejected and current files kept"
# Archive import: a tar of the assets folder, split into pieces like the
# device transfer, unpacked from inside Documents and removed afterwards.
archive_src="$work/archive-src"; rm -rf "$archive_src"; mkdir -p "$archive_src/assets/revisions/0/assetbundle/deep/path/with/a/very/long/folder/name/to/need/the/ustar/prefix/field"
printf '\x08\x01' > "$archive_src/assets/revisions/0/list.bin"
head -c 300000 /dev/urandom > "$archive_src/assets/revisions/0/assetbundle/deep/path/with/a/very/long/folder/name/to/need/the/ustar/prefix/field/archived.assetbundle"
expected="$(shasum "$archive_src/assets/revisions/0/assetbundle/deep/path/with/a/very/long/folder/name/to/need/the/ustar/prefix/field/archived.assetbundle" | cut -d' ' -f1)"
mkdir -p "$documents/import"
(cd "$archive_src" && COPYFILE_DISABLE=1 tar --format ustar -cf - assets) | split -b 100000 - "$documents/import/assets.tar."
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="import/assets.tar.aa" SIMCTL_CHILD_LUNAR_IMPORT_DELETE=1 xcrun simctl launch "$device" "$bundle" >/dev/null
unpacked="$documents/assets/revisions/0/assetbundle/deep/path/with/a/very/long/folder/name/to/need/the/ustar/prefix/field/archived.assetbundle"
wait_for "test -s '$unpacked' && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: archive import did not unpack" >&2; exit 1; }
test "$(shasum "$unpacked" | cut -d' ' -f1)" = "$expected" || { echo "FAIL: unpacked file differs" >&2; exit 1; }
test ! -e "$documents/assets/revisions/0/assetbundle/ui/sample.assetbundle" || { echo "FAIL: old files were not replaced" >&2; exit 1; }
test -s "$documents/assets/release/20240404193219.bin.e" || { echo "FAIL: archive import lost master data" >&2; exit 1; }
wait_for "test -z \"\$(ls '$documents/import')\"" 10 || { echo "FAIL: archive pieces were not removed" >&2; exit 1; }
echo "PASS: split archive import unpacks long paths, replaces files, keeps master data"

# The raw extracted dump: only revision 0 is imported; revisions 1+ hold old
# catalogs the server never uses. A folder and a split archive of it are tried.
raw="$work/raw-dump"; rm -rf "$raw"; mkdir -p "$raw/revisions/0/assetbundle/raw" "$raw/revisions/5"
printf '\x08\x01' > "$raw/revisions/0/list.bin"
printf '[{"from-name": "a", "to-revision": 0, "to-name": "b"}]' > "$raw/revisions/0/info.json"
printf 'raw' > "$raw/revisions/0/assetbundle/raw/raw.assetbundle"
head -c 200000 /dev/urandom > "$raw/revisions/5/info.json"; printf '\x08\x01' > "$raw/revisions/5/list.bin"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$raw" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -s '$documents/assets/revisions/0/assetbundle/raw/raw.assetbundle' && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: raw dump folder import" >&2; exit 1; }
test ! -e "$documents/assets/revisions/5" || { echo "FAIL: raw dump import copied other revisions" >&2; exit 1; }
(cd "$work/raw-dump" && COPYFILE_DISABLE=1 tar --format ustar -cf - revisions) | split -b 100000 - "$documents/import/raw.tar."
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="import/raw.tar.aa" SIMCTL_CHILD_LUNAR_IMPORT_DELETE=1 xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -z \"\$(ls '$documents/import')\" && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: raw dump archive import" >&2; exit 1; }
test -s "$documents/assets/revisions/0/assetbundle/raw/raw.assetbundle" && test ! -e "$documents/assets/revisions/5" || { echo "FAIL: raw dump archive kept other revisions" >&2; exit 1; }
echo "PASS: raw dump folder and archive import only revision 0"
bad="$work/raw-bad"; rm -rf "$bad"; cp -R "$raw" "$bad"; printf '[{"from-name": "a", "to-revision": 5, "to-name": "b"}]' > "$bad/revisions/0/info.json"
printf 'other' > "$bad/revisions/0/assetbundle/raw/raw.assetbundle"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$bad" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test ! -e '$documents/.assets-importing'" 30; sleep 2
test "$(cat "$documents/assets/revisions/0/assetbundle/raw/raw.assetbundle")" = raw || { echo "FAIL: dump needing other revisions was imported" >&2; exit 1; }
echo "PASS: a dump that needs other revisions is refused and current files kept"
# The resource dump's .7z and a .zip, unpacked by the shared Go code. Only
# revision 0 is extracted; the 7z fixture keeps revision 5 in its own block.
cp "$root_dir/overlays/server/mobile/testdata/nested.7z" "$documents/import/dump.7z"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="import/dump.7z" SIMCTL_CHILD_LUNAR_IMPORT_DELETE=1 xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -z \"\$(ls '$documents/import')\" && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: 7z import" >&2; exit 1; }
test "$(cat "$documents/assets/revisions/0/assetbundle/ui/one.assetbundle")" = bundle-one && test ! -e "$documents/assets/revisions/5" \
    && test ! -e "$documents/assets/revisions/0/assetbundle/raw" && test -s "$documents/assets/release/20240404193219.bin.e" || { echo "FAIL: 7z import result" >&2; exit 1; }
python3 - "$documents/import/dump.zip" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1], "w") as z:
    z.writestr("dump/revisions/0/list.bin", b"\x08\x01")
    z.writestr("dump/revisions/0/info.json", '[{"to-revision": 0}]')
    z.writestr("dump/revisions/0/assetbundle/zip/zipped.assetbundle", "zipped")
    z.writestr("dump/revisions/5/list.bin", b"\x08\x05")
PY
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="import/dump.zip" SIMCTL_CHILD_LUNAR_IMPORT_DELETE=1 xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -z \"\$(ls '$documents/import')\" && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: zip import" >&2; exit 1; }
test "$(cat "$documents/assets/revisions/0/assetbundle/zip/zipped.assetbundle")" = zipped && test ! -e "$documents/assets/revisions/5" \
    && test ! -e "$documents/assets/revisions/0/assetbundle/ui" || { echo "FAIL: zip import result" >&2; exit 1; }
echo "PASS: .7z and .zip of the dump import only revision 0"
# A folder already in Documents is moved, not copied. One that cannot be used
# stays where the player put it.
mkdir -p "$documents/moved/revisions/0/assetbundle/moved"
printf '\x08\x01' > "$documents/moved/revisions/0/list.bin"; printf 'moved' > "$documents/moved/revisions/0/assetbundle/moved/moved.assetbundle"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="moved" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -s '$documents/assets/revisions/0/assetbundle/moved/moved.assetbundle' && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: move import" >&2; exit 1; }
test ! -e "$documents/moved/revisions/0" && test ! -e "$documents/assets/revisions/0/assetbundle/zip" \
    && test -s "$documents/assets/release/20240404193219.bin.e" || { echo "FAIL: move import result" >&2; exit 1; }
mkdir -p "$documents/moved-bad/revisions/0"; printf '\x08\x01' > "$documents/moved-bad/revisions/0/list.bin"
printf '[{"to-revision": 7}]' > "$documents/moved-bad/revisions/0/info.json"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="moved-bad" xcrun simctl launch "$device" "$bundle" >/dev/null
sleep 5; wait_for "test ! -e '$documents/.assets-importing'" 30
test -s "$documents/moved-bad/revisions/0/info.json" && test -s "$documents/assets/revisions/0/assetbundle/moved/moved.assetbundle" || { echo "FAIL: refused move lost files" >&2; exit 1; }
echo "PASS: folder in Documents is moved; a refused one stays in place"
# Use in place: revisions/0 is linked, not copied. The link survives relaunch,
# a missing folder stops the server, and a later copy removes only the link.
inplace="$work/in-place"; rm -rf "$inplace" "$inplace-away"; mkdir -p "$inplace/revisions/0/assetbundle/linked"
printf '\x08\x01' > "$inplace/revisions/0/list.bin"; printf 'linked' > "$inplace/revisions/0/assetbundle/linked/linked.assetbundle"
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$inplace" SIMCTL_CHILD_LUNAR_IMPORT_LINK=1 xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -L '$documents/assets/revisions/0' && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: in-place link" >&2; exit 1; }
test "$(cat "$documents/assets/revisions/0/assetbundle/linked/linked.assetbundle")" = linked && test -s "$documents/assets/release/20240404193219.bin.e" \
    && test -s "$inplace/revisions/0/list.bin" || { echo "FAIL: in-place result" >&2; exit 1; }
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true; wait_for '! health' 10
xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for health 30 || { echo "FAIL: server did not start from the in-place folder" >&2; exit 1; }
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true; wait_for '! health' 10
mv "$inplace" "$inplace-away"
xcrun simctl launch "$device" "$bundle" >/dev/null; sleep 8
if health; then echo "FAIL: server started without the in-place folder" >&2; exit 1; fi
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
mv "$inplace-away" "$inplace"
xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for health 30 || { echo "FAIL: server did not start once the folder was back" >&2; exit 1; }
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true; wait_for '! health' 10
SIMCTL_CHILD_LUNAR_IMPORT_FROM="$source_root" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for "test -s '$documents/assets/revisions/0/assetbundle/ui/sample.assetbundle' && test ! -e '$documents/.assets-importing'" 30 || { echo "FAIL: copy after in-place" >&2; exit 1; }
test ! -L "$documents/assets/revisions/0" && test "$(cat "$inplace/revisions/0/assetbundle/linked/linked.assetbundle")" = linked || { echo "FAIL: copy after in-place touched the folder" >&2; exit 1; }
echo "PASS: in-place folder is linked, survives relaunch, needs the folder, and a later copy leaves it intact"

# Save import: a backup from another device, in the export's ZIP layout. The
# imported player takes this device's game ID; the old save is kept.
xcrun simctl terminate "$device" "$bundle" >/dev/null 2>&1 || true
saves="$documents/saves"
sqlite3 "$saves/game.db" "DELETE FROM users; INSERT INTO users (user_id, uuid, player_id) VALUES (1, 'this-device', 1);"
backup="$work/save-backup/lunar-tear-saves-test"; rm -rf "$work/save-backup"; mkdir -p "$backup"
sqlite3 "$saves/game.db" ".backup '$backup/game.db'"
sqlite3 "$backup/game.db" "UPDATE users SET uuid = 'other-device', player_id = 77;"
cp "$saves/auth.db" "$saves/auth.key" "$backup/"
rm -f "$documents/save.zip"; (cd "$work/save-backup" && zip -qr "$documents/save.zip" lunar-tear-saves-test)
SIMCTL_CHILD_LUNAR_IMPORT_SAVE="save.zip" xcrun simctl launch "$device" "$bundle" >/dev/null
wait_for health 30 || { echo "FAIL: server did not start after the save import" >&2
    xcrun simctl spawn "$device" log show --last 2m --style compact --predicate 'eventMessage CONTAINS "[LunarTear]"' >&2; exit 1; }
test "$(sqlite3 "$saves/game.db" "SELECT uuid || '/' || player_id FROM users")" = "this-device/77" || { echo "FAIL: imported player did not take this device's ID" >&2; exit 1; }
test "$(sqlite3 "$documents/saves.before-import/game.db" "SELECT player_id FROM users")" = "1" || { echo "FAIL: previous save was not kept" >&2; exit 1; }
echo "PASS: save backup import replaces the save, adopts this device's player ID, keeps the old save"
echo "Simulator smoke test passed. Screenshots: $work/no-files.png, $work/running.png"
