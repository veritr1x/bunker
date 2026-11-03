"""What a Bunker APK records about itself, so it can update in place.

Every APK carries assets/lunar/build.json (and the game's original binary
manifest as assets/lunar/game-manifest.xml). An update keeps the game's
entries as they are and replaces Bunker's: the dex files after the game's
own, the libraries the launcher brought, and assets/chaquopy and assets/lunar.
The notices (assets/notices/, notice_pack.py) stay unless the update brings a
new pack; build.json's "notices" names the pack the APK carries.
"""
import re
import branding

# Bump when a release changes how the game itself is patched (its library,
# metadata, master data or manifest edits): such an update needs the web builder.
GAME_PATCH = 1
VERSION_ENTRY = "assets/lunar/bunker-version.txt"
COMPANION_PATCH_ENTRY = "assets/lunar/game-patch.txt"


def check_companion(companion):
    """A newer web patcher must not package an older on-device updater."""
    names = companion.namelist()
    if COMPANION_PATCH_ENTRY not in names or companion.read(COMPANION_PATCH_ENTRY).decode().strip() != str(GAME_PATCH):
        raise RuntimeError("The launcher bundle is out of date for this game patch. Rebuild the launcher with this builder before packaging.")


def describe(companion, game_dex, port_offset, notices=None):
    """build.json for an APK made from the companion (launcher) APK; notices is the notice pack's sha256."""
    names = companion.namelist()
    version = companion.read(VERSION_ENTRY).decode().strip() if VERSION_ENTRY in names else "dev"
    info = {"version": version, "gamePatch": GAME_PATCH, "portOffset": int(port_offset), "gameDex": int(game_dex),
            "bunkerLibs": sorted(n for n in names if n.startswith("lib/arm64-v8a/"))}
    if notices:
        info["notices"] = notices
    return info


def is_bunker_entry(name, info):
    """Whether an APK entry came from Bunker rather than the game."""
    m = re.fullmatch(r"classes(\d*)\.dex", name)
    if m:
        return int(m.group(1) or 1) > info["gameDex"]
    return name == branding.ICON_PATH or name in info["bunkerLibs"] or name.startswith(("assets/chaquopy/", "assets/lunar/"))


if __name__ == "__main__":
    print(GAME_PATCH)
