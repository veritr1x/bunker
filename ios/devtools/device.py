#!/usr/bin/env python3
"""Drive the installed game on a connected iPhone or iPad from the Mac.

  device.py screenshot out.png
  device.py launch | home
  device.py tap X Y              # X and Y are 0-1 fractions of the screen
  device.py gesture              # three-finger double-tap (opens the launcher)
  device.py press LABEL          # tap the button or menu item with this label
  device.py swipe X Y X2 Y2
  device.py type "text"

Screenshots use devicectl. Touch input runs the Control UI test once per
action. Build it first (see docs/IOS.md); set LUNAR_DEVICE and LUNAR_BUNDLE_ID.
"""
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = ROOT / ".build/ios-devtools/Build/Products"
DEVICE = os.environ.get("LUNAR_DEVICE", "")
BUNDLE = os.environ.get("LUNAR_BUNDLE_ID", "")


def xctestrun(environment):
    runs = sorted(PRODUCTS.glob("Control_*.xctestrun"))
    if not runs:
        sys.exit("Build the controller first: see docs/IOS.md")
    with runs[-1].open("rb") as handle:
        data = plistlib.load(handle)
    # Format 1 keeps test targets at the top level; format 2 nests them.
    targets = [value for key, value in data.items() if isinstance(value, dict) and "TestBundlePath" in value]
    for config in data.get("TestConfigurations", []):
        targets += config.get("TestTargets", [])
    for target in targets:
        target.setdefault("EnvironmentVariables", {}).update(environment)
        target.setdefault("TestingEnvironmentVariables", {}).update(environment)
    temp = tempfile.NamedTemporaryFile(suffix=".xctestrun", dir=PRODUCTS, delete=False)
    plistlib.dump(data, temp)
    temp.close()
    return temp.name


def act(environment):
    path = xctestrun({"LUNAR_BUNDLE_ID": BUNDLE, **environment})
    try:
        result = subprocess.run(["xcodebuild", "test-without-building", "-xctestrun", path, "-destination", f"id={DEVICE}",
                                 "-only-testing:Control/ControlTests/testAction"], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if result.returncode:
        lines = [line for line in result.stdout.splitlines() + result.stderr.splitlines() if "error" in line.lower()]
        sys.exit("\n".join(lines[-5:]) or "Action failed")


def main():
    if not DEVICE or not BUNDLE:
        sys.exit("Set LUNAR_DEVICE (UDID) and LUNAR_BUNDLE_ID")
    command, *values = sys.argv[1:] or ["help"]
    if command == "screenshot" and len(values) == 1:
        subprocess.run(["xcrun", "devicectl", "device", "capture", "screenshot", "--device", DEVICE, "--destination", values[0]],
                       check=True, capture_output=True)
    elif command in ("launch", "home") and not values:
        act({"LUNAR_ACTION": command})
    elif command == "tap" and len(values) == 2:
        act({"LUNAR_ACTION": "tap", "LUNAR_X": values[0], "LUNAR_Y": values[1]})
    elif command == "swipe" and len(values) == 4:
        act({"LUNAR_ACTION": "swipe", "LUNAR_X": values[0], "LUNAR_Y": values[1], "LUNAR_X2": values[2], "LUNAR_Y2": values[3]})
    elif command == "type" and len(values) == 1:
        act({"LUNAR_ACTION": "type", "LUNAR_TEXT": values[0]})
    elif command == "gesture":
        act({"LUNAR_ACTION": "gesture"})
    elif command == "press" and len(values) == 1:
        act({"LUNAR_ACTION": "press", "LUNAR_TEXT": values[0]})
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
