import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import audit_notices


class NoticeAuditTests(unittest.TestCase):
    def test_absolute_and_relative_archive_paths_identify_the_same_image(self):
        path = "/images/en/operations/banner/" + "a" * 64
        values = [path, "https://web.app.nierreincarnation.com" + path,
                  "/https://web.app.nierreincarnation.com" + path.replace("/en/", "//en/")]
        self.assertEqual({audit_notices.canonical_image_path(value) for value in values}, {path})
        self.assertEqual(audit_notices.image_key(path), "a" * 64)

    def test_shared_icon_key_matches_the_existing_pack_naming(self):
        path = "/images/common/icon/thumbnail_rarity_icon_rainbow.png"
        self.assertEqual(audit_notices.image_key(path), "c_c0591a6ed6321ab9")
        self.assertEqual(audit_notices.canonical_image_path("/images"), "")
        self.assertEqual(audit_notices.canonical_image_path("https://other.example/images/a.png"), "")

    def test_profile_background_art_is_a_source_image_without_an_img_tag(self):
        path = "/images/en/operations/character/" + "b" * 64
        body = '<div style=\'background-image: url("https://web.app.nierreincarnation.com' + path + '")\'></div>'
        self.assertEqual(audit_notices.ImagePaths(body).paths, [path])

    def test_reused_body_art_is_distinct_from_a_missing_thumbnail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = "/images/en/operations/banner/" + "a" * 64
            background = "/images/en/operations/character/" + "b" * 64
            body = '<img src="img/body.webp"><div style="background-image:url(' + background + ')"></div>'
            pack = root / "pack.zip"
            with zipfile.ZipFile(pack, "w") as archive:
                archive.writestr("notices.json", json.dumps({"notices": [
                    {"id": 1, "thumb": "body", "body": body},
                    {"id": 9, "thumb": "", "body": ""}]}))
                archive.writestr("img/body.webp", b"existing art")
            guide = [{"notification_id": 1, "thumbnail_path": path, "body": ""},
                     {"notification_id": 2, "thumbnail_path": None, "body": ""}]
            (root / "guide-all-details.json").write_text(json.dumps(guide))
            result = audit_notices.audit(pack, root)
            self.assertEqual(result["guide"]["missing_from_pack"], [2])
            self.assertEqual(result["guide"]["pack_only"], [9])
            self.assertEqual(result["guide"]["thumbnail_styles_in_pack"], {"another_packed_image": 1})
            self.assertEqual(result["pack"]["blank_thumbnails"], 1)
            self.assertEqual(result["pack"]["broken_local_image_references"], [])
            self.assertEqual(result["pack"]["unmapped_original_image_references"], [{"id": 1, "paths": [background]}])
            self.assertEqual(result["original_images"]["missing_from_pack"], 2)

    def test_modified_or_missing_recovery_files_are_not_counted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "image.png"
            image.write_bytes(b"verified original")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            records = [{"key": "a", "file": str(image), "sha256": digest},
                       {"key": "b", "file": str(image), "sha256": "0" * 64},
                       {"key": "c", "file": str(root / "absent.png"), "sha256": digest}]
            (root / "recovered-images.json").write_text(json.dumps(records))
            self.assertEqual(set(audit_notices.verified_recoveries(root)), {"a"})

    def test_exported_corpus_resolves_portable_image_filenames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            (root / "images/original").mkdir(parents=True)
            image = root / "images/original/a.png"
            image.write_bytes(b"preserved payload")
            row = {"key": "a", "file": "images/original/a.png",
                   "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
            profile = {**row, "original_paths": ["/images/en/operations/character/" + "b" * 64], "notice_ids": [1]}
            portrait = {**profile, "original_paths": ["/images/en/operations/character/" + "c" * 64],
                        "mapping_scope": "character identity only"}
            promotion = {**row, "notices": [1], "family": "promotion"}
            (root / "data/image-manifests.json").write_text(json.dumps({"original": [row], "profiles": [profile, portrait],
                                                                       "promotions": [promotion]}))
            self.assertEqual(set(audit_notices.verified_recoveries(root / "data")), {"a"})
            with zipfile.ZipFile(root / "pack.zip", "w") as archive:
                archive.writestr("notices.json", json.dumps({"notices": [{"id": 1, "body": "", "thumb": ""}]}))
            (root / "data/guide-all-details.json").write_text(json.dumps([]))
            report = audit_notices.audit(root / "pack.zip", root / "data")
            self.assertEqual(report["original_images"]["validated_recovered_files"], 1)
            self.assertEqual(report["profile_artwork"]["validated_textures"], 2)
            self.assertEqual(report["profile_artwork"]["mapped_original_paths"], profile["original_paths"])
            self.assertEqual(report["profile_artwork"]["entity_portrait_paths"], portrait["original_paths"])
            self.assertEqual(report["game_artwork"]["validated_textures"], 1)
            self.assertEqual(report["game_artwork"]["notice_ids"], [1])

    def test_contextual_item_art_does_not_become_an_original_or_global_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            image = root / "icon.png"
            image.write_bytes(b"native game sprite")
            path = "/images/en/operations/thumbnail/possession/04/" + "a" * 64
            icon = {"file": "icon.png", "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                    "scope": "notice", "asset": "memory482", "original_paths": [path], "notice_ids": [1]}
            changed = {**icon, "asset": "memory488", "notice_ids": [2], "sha256": "0" * 64}
            (root / "data/image-manifests.json").write_text(json.dumps({"native_icons": [icon, changed]}))
            (root / "data/guide-all-details.json").write_text(json.dumps([
                {"notification_id": 1, "body": '<img src="' + path + '">'},
                {"notification_id": 2, "body": '<img src="' + path + '">'}]))
            with zipfile.ZipFile(root / "pack.zip", "w") as archive:
                archive.writestr("notices.json", json.dumps({"notices": [
                    {"id": 1, "body": "", "thumb": ""}, {"id": 2, "body": "", "thumb": ""}]}))
            report = audit_notices.audit(root / "pack.zip", root / "data")
            self.assertEqual(report["original_images"]["validated_recovered_files"], 0)
            self.assertEqual(report["original_images"]["unrecovered_original_paths"], 1)
            self.assertEqual(report["item_artwork"]["validated_textures"], 1)
            self.assertEqual(report["item_artwork"]["mapped_original_paths"], [])
            self.assertEqual(report["item_artwork"]["contextual_mapped_paths"], [path])
            self.assertEqual(report["item_artwork"]["contextual_mappings"], [
                {"paths": [path], "notice_ids": [1], "asset": "memory482"}])


if __name__ == "__main__":
    unittest.main()
