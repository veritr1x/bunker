"""Telemetry binary guards and preservation of game/messaging code."""
import struct
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

import axml
from axml import Attr, Document, Element
import privacy


def manifest():
    app = Element("application", children=[
        Element("meta-data", [Attr.string("name", "firebase_analytics_collection_deactivated", 0x01010003),
                              Attr.boolean("value", False, 0x01010024)]),
        Element("meta-data", [Attr.string("name", "com.facebook.sdk.AutoLogAppEventsEnabled", 0x01010003),
                              Attr.boolean("value", True, 0x01010024)]),
        Element("meta-data", [Attr.string("name", "game.setting", 0x01010003), Attr.string("value", "keep", 0x01010024)]),
        Element("provider", [Attr.string("name", "com.google.firebase.provider.FirebaseInitProvider", 0x01010003)]),
        Element("provider", [Attr.string("name", "com.facebook.internal.FacebookInitProvider", 0x01010003)]),
        Element("provider", [Attr.string("name", "com.applovin.sdk.AppLovinInitProvider", 0x01010003)]),
        Element("provider", [Attr.string("name", "org.veritr1x.bunker.GameProcessProvider", 0x01010003)]),
        Element("meta-data", [Attr.string("name", "firebase_messaging_auto_init_enabled", 0x01010003),
                              Attr.boolean("value", True, 0x01010024)]),
        Element("service", [Attr.string("name", "com.google.firebase.messaging.FirebaseMessagingService", 0x01010003)]),
        Element("receiver", [Attr.string("name", "com.adjust.sdk.AdjustReferrerReceiver", 0x01010003)]),
        Element("receiver", [Attr.string("name", "game.Notifications", 0x01010003)]),
        Element("service", [Attr.string("name", "com.google.firebase.components.ComponentDiscoveryService", 0x01010003)], [
            Element("meta-data", [Attr.string("name", "com.google.firebase.components:com.google.firebase.crashlytics.CrashlyticsRegistrar", 0x01010003)]),
            Element("meta-data", [Attr.string("name", "unrelated.component", 0x01010003)]),
        ]),
    ])
    return Element("manifest", children=[
        Element("uses-permission", [Attr.string("name", "android.permission.INTERNET", 0x01010003)]),
        *(Element("uses-permission", [Attr.string("name", name, 0x01010003)]) for name in sorted(privacy.AD_PERMISSIONS)), app])


def elf():
    # Small synthetic ELF: each original instruction sequence gets its own
    # executable mapping at the real RVA; no copyrighted game file is needed.
    count = len(privacy.SITES)
    start = 64 + count * 56
    data = bytearray(start + count * 32)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, count)
    offsets = []
    for index, site in enumerate(privacy.SITES):
        offset = start + index * 32
        struct.pack_into("<IIQQQQQQ", data, 64 + index * 56, 1, 5, offset, site["rva"], 0, 16, 16, 4)
        data[offset:offset + 16] = bytes.fromhex(site["original"])
        offsets.append(offset)
    return data, offsets


class PrivacyTests(unittest.TestCase):
    def test_manifest_removals_preserve_sdk_settings_and_other_components(self):
        root = manifest()
        app = root.find_all("application")[0]
        preserved = [entry for entry in app.children if entry.name != "receiver"]
        privacy.harden_manifest(root)
        self.assertEqual([entry for entry in app.children if entry.name != "receiver"], preserved)
        self.assertEqual([x.get("name").raw for x in root.find_all("uses-permission")], ["android.permission.INTERNET"])
        self.assertEqual([x.get("name").raw for x in app.find_all("receiver")], ["game.Notifications"])

    def test_binary_manifest_round_trip_and_idempotence(self):
        root = manifest()
        privacy.harden_manifest(root)
        namespaces = [("android", axml.ANDROID_NS, 0)]
        first = axml.serialize(Document(root, namespaces))
        doc = axml.parse(first)
        privacy.harden_manifest(doc.root)
        self.assertEqual(first, axml.serialize(doc))

    def test_apktool_manifest_removals_preserve_other_components(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "AndroidManifest.xml"
            permissions = ''.join('<uses-permission android:name="' + name + '"/>' for name in sorted(privacy.AD_PERMISSIONS))
            path.write_text('<manifest xmlns:android="' + axml.ANDROID_NS + '"><uses-permission android:name="android.permission.INTERNET"/>'
                            + permissions + '<application><meta-data android:name="firebase_analytics_collection_deactivated" android:value="true"/>'
                            '<provider android:name="com.google.firebase.provider.FirebaseInitProvider"/>'
                            '<receiver android:name="game.Notifications"/>'
                            '<receiver android:name="com.adjust.sdk.AdjustReferrerReceiver"/></application></manifest>')
            privacy.harden_text_manifest(path)
            first = path.read_bytes()
            privacy.harden_text_manifest(path)
            self.assertEqual(first, path.read_bytes())
            root = ET.parse(path).getroot()
            name = "{" + axml.ANDROID_NS + "}name"
            self.assertEqual([x.get(name) for x in root.findall("uses-permission")], ["android.permission.INTERNET"])
            app = root.find("application")
            self.assertEqual([x.get(name) for x in app.findall("receiver")], ["game.Notifications"])
            self.assertEqual(app.find("provider").get(name), "com.google.firebase.provider.FirebaseInitProvider")
            self.assertEqual(app.find("meta-data").get("{" + axml.ANDROID_NS + "}value"), "true")

    def test_native_patches_are_checked_idempotent_and_localized(self):
        source, offsets = elf()
        original = bytes(source)
        patched = privacy.patch_library(source)
        self.assertEqual(bytes(source), original)
        allowed = set()
        for site, offset in zip(privacy.SITES, offsets):
            replacement = bytes.fromhex(site["replacement"])
            self.assertEqual(patched[offset:offset + len(replacement)], replacement)
            allowed.update(range(offset, offset + len(replacement)))
        self.assertTrue(all(a == b or index in allowed for index, (a, b) in enumerate(zip(original, patched))))
        self.assertEqual(privacy.patch_library(patched), patched)

    def test_unknown_instruction_fails_before_mutating_input(self):
        source, offsets = elf()
        source[offsets[-1] + 12] ^= 1
        original = bytes(source)
        with self.assertRaisesRegex(ValueError, "Unsupported game binary"):
            privacy.patch_library(source)
        self.assertEqual(bytes(source), original)

    def test_non_executable_mapping_and_wrong_architecture_are_rejected(self):
        source, _ = elf()
        struct.pack_into("<I", source, 64 + 4, 4)
        with self.assertRaisesRegex(ValueError, "outside executable"):
            privacy.patch_library(source)
        struct.pack_into("<H", source, 18, 62)
        with self.assertRaisesRegex(ValueError, "ARM64"):
            privacy.patch_library(source)

    def test_real_game_messaging_and_rewards_boundary(self):
        apk = Path(__file__).resolve().parents[2] / "inputs/game-3.7.1.apk"
        if not apk.is_file():
            self.skipTest("requires the user's original APK")
        with zipfile.ZipFile(apk) as archive:
            library = archive.read("lib/arm64-v8a/libil2cpp.so")
            patched = privacy.patch_library(library)
            self.assertEqual(privacy.patch_library(patched), patched)
            segments = privacy._segments(library)
            # Messaging, ad display and IronSource availability/reward callbacks
            # retain the original game's instructions.
            for rva in (0x53C8CD4, 0x53C9600, 0x53C903C, 0x53C9110,
                        53027100, 53027280, 53028000, 53027640,
                        53026144, 53025940, 53026920, 53025564,
                        0x3291FB4, 0x4AA866C, 0x2808430):
                offset = next(file + rva - address for file, address, size in segments
                              if address <= rva < address + size)
                self.assertEqual(patched[offset:offset + 16], library[offset:offset + 16])


if __name__ == "__main__":
    unittest.main()
