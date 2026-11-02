"""Check restored native thumbnails against original notice examples and data."""
import io,json,unittest,zipfile
from pathlib import Path
from PIL import Image,ImageChops,ImageStat
from rich_notice_content import RichNotices

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT/'inputs/bunker-notices-template-based.zip').is_file()
                     and (ROOT/'inputs/historical-apks/artwork/1.5.7/manifest.json').is_file()
                     and Path('C:/GitRepos/bunker-backup-before-replace/inputs/master/EntityMCostumeTable.json').is_file(),
                     'Requires local native assets and the built notice pack.')
class NoticeIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=RichNotices([], {})

    def image(self,family,ident):
        member=self.lib.notice_icons.icon(family,ident)
        return Image.open(io.BytesIO(self.lib.images[member])).convert('RGBA')

    def test_original_notice_geometry_and_colors(self):
        examples=[('costumes',32004,'b8e3672c47594a7987a427d880198e391f7d04521c32bc41d59a1c5de57cd6b1'),
                  ('weapons',320051,'59223a04f8ef1e08908a82ed72dd5dc94b183ec2d3b21869d54d47ab108687c9')]
        for family,ident,filename in examples:
            with self.subTest(family=family):
                actual=self.image(family,ident)
                original=Image.open(ROOT/'artifacts/notice-template-review/img'/f'{filename}.webp').convert('RGBA')
                self.assertEqual(actual.size,original.size)
                # Published web images have different compression from native
                # textures, but matching placement gives a close pixel match.
                self.assertLess(max(ImageStat.Stat(ImageChops.difference(actual,original)).mean[:3]),16)
                self.assertEqual(actual.getextrema()[3],(255,255))

    def test_same_weapon_art_keeps_distinct_evolution_rarity(self):
        first=self.lib.notice_icons.icon('weapons',220051)
        second=self.lib.notice_icons.icon('weapons',220052)
        self.assertNotEqual(first,second)
        proof={p['native_id']:p for p in self.lib.evidence if p.get('composite_key')}
        self.assertEqual(proof[220051]['asset'],proof[220052]['asset'])
        self.assertIn('thumbnail_frame_gold',[r['name'] for r in proof[220051]['native_layers']])
        self.assertIn('thumbnail_frame_rainbow',[r['name'] for r in proof[220052]['native_layers']])

    def test_costume_and_weapon_badges_use_native_identity(self):
        self.image('costumes',32004);self.image('weapons',320051)
        proof={p['native_id']:p for p in self.lib.evidence if p.get('composite_key')}
        self.assertEqual(proof[32004]['weapon_type_offset'],[0,0])
        self.assertEqual(proof[320051]['weapon_type_offset'],[0,34])
        self.assertIn('attribute_water',[r['name'] for r in proof[320051]['native_layers']])
        self.assertIn('weapon_icon_spear',[r['name'] for r in proof[32004]['native_layers']])

    def test_built_pack_has_framed_costumes_and_weapons_only(self):
        from bs4 import BeautifulSoup
        with zipfile.ZipFile(ROOT/'inputs/bunker-notices-template-based.zip') as z:
            proof=json.loads(z.read('templates/rich-assets.json'))
            members={p['member'] for p in proof if p.get('composite_key')}
            bare={p['member'] for p in proof if p.get('source_png') and any(s in p['source_png'] for s in ['/costumes/','/weapons/','\\costumes\\','\\weapons\\'])}
            count=0
            for n in json.loads(z.read('notices.json'))['notices']:
                if n['id']<1500000000:continue
                for img in BeautifulSoup(n['body'],'html.parser').select('img'):
                    self.assertNotIn(img.get('src'),bare,(n['id'],img))
                    if img.get('src') in members:count+=1
            self.assertGreater(count,1000)
            for member in members:
                self.assertEqual(Image.open(io.BytesIO(z.read(member))).size,(110,110))


if __name__=='__main__':unittest.main()
