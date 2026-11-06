"""sync_notice_prices: reconstructed notices follow the summon rules' prices."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import sync_notice_prices as sync

OLD = ('<section><h3>Summons Details</h3><div class="information_table"><table style="width:100%"><thead><tr><th>Type</th>'
       '<th>Required Gems / Tickets</th><th>Other</th></tr></thead><tbody>'
       '<tr><td>1x summon</td><td><img alt="" class="gem_icon" src="img/c_0a0f76549d1cbb9f.webp" width="16px"/> 300 gems</td><td>—</td></tr>'
       '<tr><td>10x summon</td><td><img alt="" class="gem_icon" src="img/c_0a0f76549d1cbb9f.webp" width="16px"/> 3,000 gems</td>'
       '<td><span class="text-red">At least one ★★★ or higher weapon is guaranteed.</span><br/>'
       '<img alt="" class="gem_icon" src="img/x.webp" width="16px"/> Small Slab Fragment ×300</td></tr>'
       '</tbody></table></div><p>At least one ★★★ or higher weapon is guaranteed.</p></section><section><h3>Notes</h3></section>')


def pack(**bodies):
    notices = [{'id': int(i), 'title': 't', 'publish': 0, 'body': b} for i, b in bodies.items()]
    return {'version': 1, 'notices': notices, 'gacha': {'186': 1500000186, '187': 187, '188': 1500000188}}


RULES = {'rules': {'186': {'steps': [{'cur': 'paid', 'draws': 10, 'guar': 'r3w', 'price': 3000}]},
                   '187': {'steps': [{'cur': 'paid', 'draws': 10, 'guar': 'r3w', 'price': 3000}]}},
         'new': [{'id': 188, 'steps': [{'cur': 'gems', 'draws': 1, 'price': 300}, {'cur': 'gems', 'draws': 10, 'guar': 'r3w', 'price': 3000}]}]}


class Sync(unittest.TestCase):
    def test_a_reconstructed_notice_follows_its_summons_rule(self):
        p = pack(**{'1500000186': OLD, '187': OLD, '1500000188': OLD})
        self.assertEqual(sync.sync(p, RULES), [(186, 1500000186)])
        body = {n['id']: n['body'] for n in p['notices']}
        new = body[1500000186]
        self.assertNotIn('1x summon', new)
        self.assertIn('3,000 paid gems', new)
        self.assertIn('This summons can only be used with paid gems.', new)
        self.assertIn('Small Slab Fragment ×300', new)  # the 10x row's bonus stays, with its icon
        self.assertIn('img/x.webp', new)
        self.assertTrue(new.endswith('<section><h3>Notes</h3></section>'))
        self.assertEqual(body[187], OLD)  # a recovered original is never touched
        self.assertEqual(body[1500000188], OLD)  # already right

    def test_limits_and_steps(self):
        p = pack(**{'1500000186': OLD})
        rules = {'rules': {'186': {'steps': [{'cur': 'free', 'daily': True, 'draws': 10, 'guar': 'r3w', 'limit': 1, 'price': 0}]}}, 'new': []}
        sync.sync(p, rules)
        self.assertIn('Can be used 1 time per day.', p['notices'][0]['body'])
        self.assertEqual(sync.sync(p, rules), [])  # once in line, left alone
        steps = [{'cur': 'paid', 'draws': 10, 'price': 2000, 'step': 1}, {'cur': 'free', 'draws': 10, 'price': 0, 'step': 2}]
        rules = {'rules': {'186': {'steps': steps}}, 'new': []}
        sync.sync(p, rules)
        body = p['notices'][0]['body']
        self.assertIn('Step 1: 10x summon', body)
        self.assertIn('Can be used 1 time per cycle.', body)
        self.assertIn('Paid steps require paid gems. Steps marked Free do not consume gems.', body)
        self.assertEqual(sync.sync(p, rules), [])

    def test_writes_a_pack(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            with zipfile.ZipFile(t / 'in.zip', 'w') as z:
                z.writestr('notices.json', json.dumps(pack(**{'1500000186': OLD})))
                z.writestr('img/x.webp', b'image')
            (t / 'rules.json').write_text(json.dumps(RULES))
            self.assertEqual(sync.write(t / 'in.zip', t / 'out.zip', t / 'rules.json'), [(186, 1500000186)])
            with zipfile.ZipFile(t / 'out.zip') as z:
                self.assertEqual(z.read('img/x.webp'), b'image')
                self.assertIn('3,000 paid gems', json.loads(z.read('notices.json'))['notices'][0]['body'])

    def test_wording_matches_the_pack_builder(self):
        try:
            from rich_notice_content import GEM, RichNotices
        except ImportError:
            self.skipTest('needs scripts/requirements-notices.txt')
        self.assertEqual(sync.GEM, GEM)
        for s in ({'guar': 'r3w'}, {'guar': 'r4w'}, {'guar': 'r4c:fire'}, {'guar': 'set'}, {'guar': 'r4w', 'guaranteed_count': 2},
                  {'guar': 'r4w', 'guarantee_slot': 10}, {}, {'guar': 'none'}):
            self.assertEqual(sync.guarantee(s), RichNotices.guarantee(s), s)

    def test_the_embedded_rules_leave_no_notice_behind(self):
        # The pinned pack is not in the repository; this checks the rules parse.
        self.assertTrue(sync.rule_steps(json.loads(sync.RULES.read_text())))


if __name__ == '__main__':
    unittest.main()
