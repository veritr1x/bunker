#!/usr/bin/env python3
"""Pod Programs › Language, the page.

Needs fastapi, jinja2, python-multipart and httpx (the Android Python requirements) and the prepared
Tools sources (scripts/prepare.py), like test_display.py; skipped without them.
"""
from pathlib import Path
import json, sys, tempfile, unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "android/app/src/main/python"))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from web import config
except ImportError:  # fastapi, or the prepared sources (web/)
    FastAPI = None
if FastAPI is not None:
    import android_language
else:
    android_language = None


def pack(language="pt-BR", name="Português"):
    return json.dumps({"format": 1, "language": language, "name": name, "version": "1", "game": {"a": "x"}}, ensure_ascii=False).encode()


@unittest.skipIf(android_language is None, "needs fastapi and the prepared sources")
class LanguagePageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        base = Path(self.dir.name)
        saved = (config.ASSETS_DIR, config.REVISIONS_DIR, config.DATA_DIR)
        self.addCleanup(lambda: (setattr(config, "ASSETS_DIR", saved[0]), setattr(config, "REVISIONS_DIR", saved[1]),
                                 setattr(config, "DATA_DIR", saved[2])))
        config.DATA_DIR = base / "tools"
        config.ASSETS_DIR = base / "server" / "assets"
        config.REVISIONS_DIR = config.ASSETS_DIR / "revisions"
        (config.REVISIONS_DIR / "0" / "assetbundle" / "text" / "en").mkdir(parents=True)
        self.translation = base / "server" / "translation"
        saved_shipped = android_language.SHIPPED
        self.addCleanup(lambda: setattr(android_language, "SHIPPED", saved_shipped))
        android_language.SHIPPED = base / "shipped"  # not the app's own shipped packs
        app = FastAPI()
        app.include_router(android_language.router)
        self.client = TestClient(app, follow_redirects=False)

    def load(self, data=None):
        return self.client.post("/language/load", files={"pack": ("pack.json", data or pack(), "application/json")})

    def test_page_lists_english_and_packs(self):
        self.load()
        page = self.client.get("/language")
        self.assertEqual(page.status_code, 200)
        self.assertIn("English", page.text)
        self.assertIn("Português", page.text)
        self.assertIn("1 text (", page.text)

    def test_explanations_render_behind_an_info_icon(self):
        page = self.client.get("/language").text
        # the page's intro sits in its title, the pack note beside the file input: closed until tapped
        self.assertRegex(page, r'<h1 data-side>Language<details class="info"><summary aria-label="More information">i</summary>'
                               r'<div>Keep the game set to English: a pack replaces its English text\.[^<]*</div></details></h1>')
        self.assertIn('required><details class="info"><summary aria-label="More information">i</summary><div>A .json pack', page)
        self.assertNotIn('<details class="info" open', page)
        self.assertIn("details.info > summary", page)                     # styled by base.html

    def test_choose_writes_active(self):
        self.load()
        response = self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.assertEqual(response.status_code, 303)
        self.assertIn("message=", response.headers["location"])
        self.assertTrue((self.translation / "active.json").is_file())

    def test_load_rejects_a_bad_file(self):
        response = self.load(b"nope")
        self.assertEqual(response.status_code, 303)
        self.assertIn("error=Not+a+language+pack", response.headers["location"])
        self.assertFalse(any((self.translation / "packs").glob("*.json")) if (self.translation / "packs").exists() else False)

    def test_remove(self):
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        response = self.client.post("/language/remove", data={"language": "pt-BR"})
        self.assertIn("message=", response.headers["location"])
        self.assertFalse((self.translation / "active.json").exists())

    def test_loading_leaves_the_game_alone(self):
        import android_runtime
        self.assertIn("/language/load", android_runtime.LIVE_SAFE)

    def test_removing_a_pack_not_in_use_changes_nothing(self):
        self.load()
        self.load(pack(language="pl", name="Polski"))
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        response = self.client.post("/language/remove", data={"language": "pl"})
        self.assertEqual(response.headers.get("x-bunker-unchanged"), "1")
        response = self.client.post("/language/remove", data={"language": "pt-BR"})
        self.assertIsNone(response.headers.get("x-bunker-unchanged"))
        self.assertIn("English", response.headers["location"])

    def test_counts_read_as_words(self):
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.status('{"state":"ready","language":"pt-BR","name":"Português","version":"1","bundles":1}')
        page = self.client.get("/language").text
        self.assertIn("1 text (", page)
        self.assertNotIn("1 texts", page)
        self.assertIn("1 text file translated", page)

    def test_save_with_nothing_chosen_explains(self):
        response = self.client.post("/language", data={})
        self.assertEqual(response.status_code, 303)
        self.assertIn("error=", response.headers["location"])
        self.assertEqual(response.headers.get("x-bunker-unchanged"), "1")

    def test_saving_the_current_choice_changes_nothing(self):
        response = self.client.post("/language", data={"choice": "en"})
        self.assertEqual(response.headers.get("x-bunker-unchanged"), "1")
        self.load()
        response = self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.assertIsNone(response.headers.get("x-bunker-unchanged"))

    def test_unsupported_client_can_go_back_to_english(self):
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        (config.REVISIONS_DIR / "0" / "assetbundle" / "text" / "en").rmdir()
        response = self.client.post("/language", data={"choice": "en"})
        self.assertIn("message=", response.headers["location"])
        self.assertFalse((self.translation / "active.json").exists())

    def test_update_brings_in_a_revised_shipped_pack(self):
        import android_runtime, bunker_language
        shipped = android_language.SHIPPED
        saved = bunker_language.SHIPPED_DIR
        self.addCleanup(lambda: setattr(bunker_language, "SHIPPED_DIR", saved))
        bunker_language.SHIPPED_DIR = shipped  # what the launchers' update reads
        shipped.mkdir(parents=True)
        (shipped / "pl.json").write_bytes(pack(language="pl", name="Polski"))
        self.client.post("/language", data={"choice": "shipped:pl"})
        revised = pack(language="pl", name="Polski 2")
        (shipped / "pl.json").write_bytes(revised)  # the next Bunker build
        android_runtime.refresh_language()  # update_data, before the server starts
        self.assertEqual((self.translation / "active.json").read_bytes(), revised)

    def status(self, text):
        self.translation.mkdir(parents=True, exist_ok=True)
        (self.translation / "status.json").write_text(text, encoding="utf-8")

    def test_status_of_another_pack_says_the_choice_waits(self):
        # Português was applied; with the game closed the player then chose English, then Polski
        self.status('{"state":"ready","language":"pt-BR","name":"Português","version":"1","bundles":1}')
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.client.post("/language", data={"choice": "en"})
        page = self.client.get("/language").text
        self.assertNotIn("Ready: Português", page)
        self.assertIn("applies the next time Lunar Tear starts", page)
        self.load(pack(language="pl", name="Polski"))
        self.client.post("/language", data={"choice": "loaded:pl"})
        page = self.client.get("/language").text
        self.assertNotIn("Ready: Português", page)
        self.assertIn("applies the next time Lunar Tear starts", page)

    def test_status_of_the_chosen_pack_is_shown(self):
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.status('{"state":"ready","language":"pt-BR","name":"Português","version":"1","bundles":1}')
        self.assertIn("Ready: Português", self.client.get("/language").text)

    def test_unreadable_pack_is_said_plainly(self):
        self.status('{"state":"failed","error":"pack format 2 is not supported"}')
        (self.translation / "active.json").write_text('{"format":2}')  # put there by hand: the page cannot list it
        page = self.client.get("/language").text
        self.assertIn("The chosen pack could not be read: pack format 2 is not supported.", page)
        self.assertNotIn("tried again", page)
        self.assertNotIn("the pack could not", page)

    def test_status_is_shown(self):
        self.load()
        self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.status('{"state":"building","language":"pt-BR","name":"Português","version":"1"}')
        self.assertIn("Building Português", self.client.get("/language").text)
        self.status('{"state":"failed","language":"pt-BR","name":"Português","version":"1","error":"no space left on device"}')
        page = self.client.get("/language").text
        self.assertIn("Português could not be applied: no space left on device", page)

    def test_unsupported_client(self):
        (config.REVISIONS_DIR / "0" / "assetbundle" / "text" / "en").rmdir()
        self.load()
        self.assertIn("Language packs need the global game files.", self.client.get("/language").text)
        response = self.client.post("/language", data={"choice": "loaded:pt-BR"})
        self.assertIn("error=", response.headers["location"])
        self.assertFalse((self.translation / "active.json").exists())

    def test_platform_tree_is_supported(self):
        (config.REVISIONS_DIR / "0" / "assetbundle" / "text" / "en").rmdir()
        (config.REVISIONS_DIR / "0" / "ios" / "assetbundle" / "text" / "en").mkdir(parents=True)
        self.assertNotIn("not supported", self.client.get("/language").text)


class ProgramsPageTest(unittest.TestCase):
    def test_programs_page_links_language(self):
        index = (root / "overlays/python/web/templates/index.html").read_text()
        self.assertIn('program("/language"', index)

    def test_side_menu_links_language(self):
        self.assertIn('href="/language"', (root / "overlays/python/web/templates/base.html").read_text())


if __name__ == "__main__":
    unittest.main()
