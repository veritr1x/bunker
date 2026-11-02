"""Check restored presentation against native assets and target-run evidence."""
import hashlib,io,json,re,unittest,zipfile
from pathlib import Path
from PIL import Image
from rich_notice_content import soup

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'inputs/bunker-notices-template-based.zip'


@unittest.skipUnless(PACK.exists(),'Requires the built local notice candidate.')
class RichContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.z=zipfile.ZipFile(PACK)
        cls.pack=json.loads(cls.z.read('notices.json'))
        cls.notices={n['id']:n for n in cls.pack['notices']}
        cls.proof=json.loads(cls.z.read('templates/rich-assets.json'))
        cls.mapping=json.loads(cls.z.read('templates/base-map.json'))['matches']

    @classmethod
    def tearDownClass(cls):cls.z.close()

    def test_prisoner_restores_own_promotion_and_mechanics(self):
        doc=soup(self.notices[1500000039]['body']);text=doc.get_text(' ',strip=True)
        proof=next(m['rich_content'] for m in self.mapping if m['gacha_id']==39)
        self.assertTrue(proof['title_graphic'])
        self.assertEqual(len(proof['promotion_panels']),1)
        self.assertGreaterEqual(len(doc.select('img')),12)
        for phrase in ['063y (Fractured Prisoner)','Faulty Greatsword','3,000 paid gems',
                       '5 times','200 shards','At least one ★★★ or higher weapon',
                       'Whenever a ★★★★ character weapon appears','Each summon gives one shard']:
            self.assertIn(phrase,text)
        for wrong in ['Marie','Passionflower','Black Pearl','1.5','Aurora','Season 005']:
            self.assertNotIn(wrong,text)
        self.assertEqual(len(doc.select('body')),1)
        self.assertTrue(doc.select('.holding-period'))

    def test_prisoner_art_is_pixel_identical_to_native_files(self):
        proof=next(m['rich_content'] for m in self.mapping if m['gacha_id']==39)
        pairs=[(proof['title_graphic'],'title_logo-Sprite.png'),
               (proof['promotion_panels'][0],'limited_39-Sprite-4541812388906258265.png')]
        for member,filename in pairs:
            with self.subTest(member=member):
                actual=Image.open(io.BytesIO(self.z.read(member))).convert('RGBA')
                expected=Image.open(ROOT/'.build/notice-audit/rich-notices'/filename).convert('RGBA')
                self.assertEqual(actual.size,expected.size)
                self.assertEqual(actual.tobytes(),expected.tobytes())

    def test_all_new_images_have_integrity_and_no_missing_body_references(self):
        names=set(self.z.namelist())
        for p in self.proof:
            raw=self.z.read(p['member']);im=Image.open(io.BytesIO(raw)).convert('RGBA')
            self.assertEqual(hashlib.sha256(raw).hexdigest(),Path(p['member']).stem)
            self.assertEqual(hashlib.sha256(im.tobytes()).hexdigest(),p['rgba_sha256'])
            self.assertTrue(p['lossless_roundtrip_verified'])
        for m in self.mapping:
            if m['action']!='adapt_template':continue
            doc=soup(self.notices[m['target_notice_id']]['body'])
            for img in doc.select('img'):
                self.assertIn(img['src'],names,(m['gacha_id'],img['src']))

    def test_old_roster_price_and_player_cleanup_survive(self):
        self.assertNotIn('Bloody Captain',self.notices[1500010030]['body'])
        self.assertIn('200 shards',self.notices[1500000008]['body'])
        for n in self.notices.values():
            if n['id']<1500000000:continue
            for removed in ['Details not established','Page sources and limitations',
                            'This table does not establish','This is not a verified summon end time',
                            'Exchange options recorded in original-run snapshot',
                            'These dates come from native home-banner records']:
                self.assertNotIn(removed,n['body'])

    def test_original_notices_and_asset_bytes_stay_unchanged(self):
        with zipfile.ZipFile(ROOT/'inputs/bunker-notices-complete-generated.zip') as original:
            pack=json.loads(original.read('notices.json'))
            unchanged=[n for n in pack['notices'] if n['id']<1500000000]
            self.assertEqual(len(unchanged),951)
            for n in unchanged:self.assertEqual(self.notices[n['id']],n)
            for name in original.namelist():
                if name!='notices.json':self.assertEqual(self.z.read(name),original.read(name))


if __name__=='__main__':unittest.main()
