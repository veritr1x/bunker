#!/usr/bin/env python3
"""On iPhone and iPad there is no Deploy after a change the game reads as it
launches: ios_runtime turns "Close Pod Programs and tap Deploy." into "Close
Pod Programs, then restart the game." on every page that says it, Mods and
Start a new day included. Needs fastapi."""
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import ctypes, sys, unittest
from unittest import mock

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))
sys.path.insert(0, str(root / "ios/python"))
import android_calendar  # noqa: E402
import android_display  # noqa: E402
import android_mods  # noqa: E402
import android_patcher  # noqa: E402
import android_runtime  # noqa: E402

IOS = "Close Pod Programs, then restart the game."


def message(response):
    return parse_qs(urlparse(response.headers["location"]).query).get("message", [""])[0]


class IosMessages(unittest.TestCase):
    def setUp(self):
        # ios_runtime looks up the launcher's functions in its own process as it loads.
        with mock.patch.object(ctypes, "CDLL", lambda name: mock.MagicMock()):
            import ios_runtime
        for module in (android_patcher, android_display, android_calendar, android_mods):
            p = mock.patch.object(module, "redirect", module.redirect)
            p.start()
            self.addCleanup(p.stop)
        for name in ("TEXTURES", "UPSCALE", "WINDOW"):
            p = mock.patch.object(android_display, name, getattr(android_display, name))
            p.start()
            self.addCleanup(p.stop)
        ios_runtime._adapt_patcher()

    def test_display_offers_ios_choices(self):
        # MetalFX in place of Android's upscalers, and keeping the game's shape in a window or on a TV.
        self.assertEqual([key for key, _ in android_display.UPSCALE], ["off", "metalfx"])
        self.assertEqual([key for key, _ in android_display.WINDOW], ["stretch", "fit"])

    def test_mods_messages(self):
        with mock.patch.object(android_runtime, "game_live", lambda: False):
            text = android_mods.saved_message("Saved.", True, {**android_mods.OFF})
        self.assertIn("tap Deploy", text)
        self.assertEqual(message(android_mods.redirect(message=text)), text.replace("Close Pod Programs and tap Deploy.", IOS))

    def test_new_day_message(self):
        with mock.patch.object(android_patcher, "start_new_day", lambda: None):
            text = message(android_patcher.new_day())
        self.assertTrue(text.startswith("A new day has started"), text)
        self.assertTrue(text.endswith(IOS), text)


if __name__ == "__main__":
    unittest.main()
