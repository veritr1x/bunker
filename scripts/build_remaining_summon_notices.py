"""Cover the remaining 203 summons with labelled summaries or verified links.

Uses reviewed native/history evidence and Bunker 1.7 configuration. Generated
pages do not claim recovered original wording, historical odds or complete pools.
The earlier 125-repair candidate and default packs are preserved.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import build_summon_notice_repair_pack as common

LAUNCH = 1627509600000
HISTORICAL_CUTOFF = 1735689600000


def valid_date(ms):
    return LAUNCH <= ms < HISTORICAL_CUTOFF


def validate_record(r):
    assert r['synthetic_notice_id'] == common.SYNTHETIC_BASE+r['gacha_id']
    assert 0 < r['synthetic_notice_id'] <= 2147483647
    assert not r['original_wording_recovered']
    if r.get('native_title_review'):
        assert r['native_title_review']['asset'] == r['asset']
        assert r['native_title_review']['native_png_sha256'] == r['native_banner']['sha256']
    for b in r['native_banner_periods']:
        row = b['row']
        assert row[2] == 1 and row[4] == r['asset']
        assert row[6] == r['baseline']['start']
        assert valid_date(row[6]) and valid_date(row[7]) and row[6] <= row[7]
    x = r.get('exchange')
    if x and x['confidence'] == 'original_run_native_snapshot':
        m = common.medal_fields(x['medal_raw'])
        assert m['currency'] == x['shard_id']
        assert m['ceiling'] == x['ceiling'] and m['conversion'] == x['conversion']
        found = set()
        for row in x['raw_exchange_rows']:
            assert row['item'][4:6] == [1, x['shard_id']]
            assert row['item'][0] == row['cell'][2] == row['possession'][0]
            assert row['group'][1] == row['cell'][0]
            assert row['shop'][7] == row['group'][0]
            assert row['shop'][9] <= r['baseline']['start'] <= row['shop'][10]
            if row['term']:
                assert row['term'][1] <= r['baseline']['start'] <= row['term'][2]
            assert row['costume_raw'][0] == row['costume_id']
            assert row['costume_raw'][7] == 40
            found.add((row['costume_id'], row['item'][6]))
        assert found == {(c['costume_id'], c['price']) for c in x['lineup']}
        for w in x['other_exchange_weapons']:
            assert w['item_raw'][4:7] == [1, x['shard_id'], w['price']]
            assert w['possession_raw'][1:3] == [2, w['weapon_id']]
    for s in r['bunker_configuration']['steps']:
        assert s.get('draws', 0) > 0 and s.get('price', 0) >= 0
        assert s['cur'] in {'gems', 'paid', 'free', 'ticket'}
    if r.get('event'):
        event = r['event']
        assert event['configuration']['base'] == r['gacha_id']
        assert event['chapter']['EventQuestChapterId'] == event['configuration']['chapter']
    if r.get('direct_notice_id'):
        x=r['exchange'];s=r['historical_schedule_match']
        assert x['confidence']=='original_run_native_snapshot'
        assert s['notice_id']==r['direct_notice_id']
        assert s['start']==r['baseline']['start'] and s['shard']==x['shard_name']
        assert {c['character'] for c in x['lineup']}=={s['character']}
        assert s['end_minute']//60000==(x['conversion']-2*common.DAY)//60000
        assert not r['date_conflict']


def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+common.esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+common.esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'


def availability(r):
    if r.get('event'):
        c = r['event']['chapter']
        return '<h3>Native event quest period</h3><p>'+common.esc(common.date(c['StartDatetime']))+' – '+common.esc(common.date(c['EndDatetime']))+'</p><p>This is the quest period. Bunker keeps its event summons open for the configured grace period after the quests close.</p>'
    if r.get('date_conflict'):
        c = r['date_conflict']
        return '<h3>Historical dates remain unresolved</h3><p>The January weekly schedule and native exchange data disagree about the end of this run. This page does not choose an unverified summon end date.</p>'+table(
            ['Evidence', 'Recorded time'], [('Run start', common.date(r['baseline']['start'])),
             ('Notice 906 schedule end (minute precision)', common.date(c['notice_end_minute'])),
             ('Native shard conversion', common.date(r['exchange']['conversion']))])+ '<p><a href="?informationId=906">Related January schedule</a>. Its association is retained as evidence, rather than a direct replacement for this page.</p>'
    if r['native_banner_periods']:
        rows = [(common.date(b['row'][6]), common.date(b['row'][7])) for b in r['native_banner_periods']]
        variants = '<p>Native snapshots record different display ends; the recorded versions are shown without choosing an unverified final date.</p>' if len(rows)>1 else ''
        return '<h3>Recorded home-banner display</h3>'+table(['Start', 'End'], rows)+variants+'<p>These dates come from native home-banner records. A home-banner display window does not necessarily cover the full summon period.</p>'
    start = r['baseline']['start']
    if valid_date(start):
        return '<h3>Catalog date reference</h3><p>'+common.esc(common.date(start))+'</p><p>This is the start used by the reconstructed catalog. A complete original summon availability window has not been established.</p>'
    return '<h3>Historical availability unknown</h3><p>Usable historical run dates have not been recovered. Placeholder dates in the native data are omitted.</p>'


def body(r, thumb):
    text = '<section><h3>Generated data summary</h3><p>This page was generated from native game data and Bunker’s reconstructed configuration. The original announcement text has not been recovered.</p>'
    if thumb:
        text += f'<img src="img/{thumb}.webp" alt="Extracted native summon banner" width="234">'
    else:
        text += '<p>The original banner artwork has not been recovered for this entry.</p>'
    text += availability(r)
    terms = r['native_banner_terms']
    if terms:
        text += '<h3>Terms visible on the native banner</h3>'
        terms_rows = [('Payment', {'free':'Free', 'paid':'Paid gems only'}[terms['payment']])]
        if terms.get('draws'):terms_rows.append(('Draws', terms['draws']))
        if terms.get('frequency'):terms_rows.append(('Frequency', terms['frequency']))
        text += table(['Banner text', 'Advertised terms'], terms_rows)
    x = r.get('exchange')
    if x:
        text += '<h3>Native shard exchange data</h3>'
        if x['confidence'] == 'original_run_native_snapshot':
            text += '<p>Exchange options recorded in original-run snapshot '+common.esc(x['source']['source_file'])+'. These are the options visible in that snapshot, rather than a claim about every option available throughout the run.</p>'
        elif x['confidence'] == 'final_native_master_only':
            text += '<p>These options come from the final native master. A snapshot within this run was not found, so their exact period-specific availability remains unverified.</p>'
        else:
            text += '<p>The expected currency record was not found in the selected original-run snapshot. An exchange lineup is not asserted.</p>'
        text += '<p>Currency: <b>'+common.esc(x['shard_name'])+'</b>.</p>'
        if x['association'] == 'bunker_shared_catalog_mapping':
            text += '<p>Bunker associates this banner with a shared or paired exchange. That association is part of its reconstructed catalog; a separate historical currency record for this banner has not been established.</p>'
        if x['lineup']:
            text += table(['Character', 'Costume', 'Paired weapon', 'Shards'], [(c['character'], c['costume'], c['weapon'], c['price']) for c in x['lineup']])
        if x.get('other_exchange_weapons'):
            text += '<details><summary>Other recorded weapon exchange entries</summary>'+table(['Weapon', 'Shards'], [(w['weapon'], w['price']) for w in x['other_exchange_weapons']])+'</details>'
        text += '<p>An exchange can be shared by several banners or volumes. This table does not establish this banner’s featured characters, individual rates or full summon pool.</p>'
        if x.get('final_native_roster_difference'):
            text += '<p>The final master contains a different exchange roster. The table above follows the selected historical snapshot; later additions are not silently included.</p>'
        if valid_date(x.get('conversion', 0)):
            text += '<p>Native shard conversion: '+common.esc(common.date(x['conversion']))+'. This is not a verified summon end time.</p>'
    if r.get('event'):
        e = r['event']
        text += '<h3>Event summons</h3><p>Collect the event’s summon tickets through its quests, then spend them at the Event Summons. Collect all target prizes to advance levels. The final level can be replenished.</p>'
        text += table(['Ticket', 'Native item ID'], [(i['name'], i['id']) for i in e['tickets']])
        text += '<h3>Bunker’s reconstructed box rewards</h3><p>The following main prizes describe Bunker’s configuration. Original box stocks, filler rewards and odds have not been recovered; these are not presented as original event facts.</p>'
        rows = []
        for level, prizes in enumerate(e['main_prizes'], 1):
            for i in prizes:
                rows.append((level, i['name'], i['count'], i['stock']))
        text += table(['Level', 'Main prize', 'Per prize', 'Configured stock'], rows)
    steps = r['bunker_configuration']['steps']
    if r['configuration_conflicts']:
        text += '<h3>Payment configuration needs review</h3><p>'+common.esc(' '.join(r['configuration_conflicts']))+'</p><p>The disputed cost table is omitted. The banner terms above are recorded separately; consult the current in-game Summons Details before drawing.</p>'
    elif steps:
        text += '<h3>Bunker summon options</h3><p>These prices and draw counts describe Bunker 1.7.0’s reconstructed configuration. They are not independent verification of the original live-service rules.</p>'
        rows = []
        for idx, s in enumerate(steps, 1):
            cur = {'paid': 'Paid gems', 'gems': 'Gems', 'free': 'Free', 'ticket': s.get('ticket_name', 'Summon ticket')}[s['cur']]
            rows.append((s.get('step', idx), s['draws'], cur, s.get('price', 0)))
        text += table(['Option / step', 'Draws', 'Payment', 'Cost'], rows)
    text += '<h3>Details not established</h3><p>Original individual rates, complete featured pools, step guarantees and bonus, duplicate or awakening rewards are not asserted by this generated page. See Bunker’s current Summons Details for its implemented behavior.</p>'
    text += '<details><summary>Page sources and limitations</summary><p>Native text and artwork identify the catalog entry. Character and weapon names use the available English text and may differ from period wording. Descriptive titles are used where the original title is absent.</p>'
    if x and x.get('source'):
        text += '<p>Exchange snapshot: '+common.esc(x['source']['source_file'])+'. Snapshot filenames are observation labels, not original notice publication dates.</p>'
    if r['bunker_configuration']['source']:
        text += '<p>Bunker configuration source note: '+common.esc(r['bunker_configuration']['source'])+'</p>'
    if r.get('event'):
        text += '<p>Box configuration source note: '+common.esc(r['event']['configuration']['src'])+'</p>'
    text += '<p>This is a synthetic notice for summon '+str(r['gacha_id'])+'. The archive placement date is not an original publication timestamp. No new historical announcement or artwork is claimed.</p></details></section>'
    return text


def make_notice(r, thumb):
    assert not r.get('direct_notice_id'), 'Use the verified surviving notice instead of generating a duplicate.'
    start = r['baseline']['start']
    return {'id': r['synthetic_notice_id'], 'type': 3, 'title': r['display_title'],
            'publish': start if valid_date(start) else LAUNCH,
            **({'thumb': thumb} if thumb else {}), 'body': body(r, thumb)}


def review(folder, pack, source, images, rows):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'img').mkdir(exist_ok=True)
    (folder/'notices').mkdir(exist_ok=True)
    for name in source.namelist():
        if re.fullmatch(r'img/[A-Za-z0-9_-]+\.webp', name):
            (folder/name).write_bytes(source.read(name))
    for name, data in images.items():
        (folder/name).write_bytes(data)
    for n in pack['notices']:
        content = re.sub(r'(["\'])img/', r'\1../img/', n['body'])
        content = re.sub(r'(["\'])\?informationId=(\d+)(["\'])', r'\1\2.html\3', content)
        (folder/'notices'/f'{n["id"]}.html').write_text(common.page(n['title'], '<h1>'+common.esc(n['title'])+'</h1>'+content), encoding='utf-8')
    tr = ''.join('<tr>'+''.join('<td>'+v+'</td>' for v in [str(r['gacha_id']), common.esc(r['display_title'] or r['asset']),
                   common.esc(r['status']), f'<a href="notices/{r["notice_id"]}.html">{r["notice_id"]}</a>', common.esc(r['reason'])])+'</tr>' for r in rows)
    content = '<h1>Complete summon notice candidate</h1><p class="count">108 surviving-notice links · 19 rerun reconstructions · 201 generated data summaries</p><p class="note">All 328 entries in the original missing-link cohort have a page. Generated pages provide available data; they do not recover the original announcements or all historical rules. Three have no recovered banner artwork. Twelve payment conflicts are flagged and their disputed cost tables are withheld. Original-run snapshots resolve the previous January date conflicts, so summons 10073 and 10074 now link directly to notice 906.</p><input id="filter" aria-label="Filter entries" placeholder="Filter by summon, title, page type or payment conflict…"><table><thead><tr><th>Summon</th><th>Identity</th><th>Page type</th><th>Notice</th><th>Source confidence</th></tr></thead><tbody>'+tr+'</tbody></table><script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'
    (folder/'index.html').write_text(common.page('Complete summon notice candidate', content, ''), encoding='utf-8')


def build(args):
    from PIL import Image
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    assert common.sha(args.source_pack.read_bytes()) == evidence['base_pack_sha256']
    source = zipfile.ZipFile(args.source_pack)
    original = json.loads(source.read('notices.json'))
    pack = copy.deepcopy(original)
    ids = {n['id'] for n in original['notices']}
    targets = evidence['generated']
    assert len(targets) == len({r['gacha_id'] for r in targets}) == 203
    generated_targets=[r for r in targets if not r.get('direct_notice_id')]
    direct_targets=[r for r in targets if r.get('direct_notice_id')]
    images, image_checks, links = {}, [], {}
    for r in targets:
        validate_record(r)
        if r.get('direct_notice_id'):
            assert r['direct_notice_id'] in ids
            links[r['gacha_id']]=r['direct_notice_id']
            # Remove only the two superseded previews created by this builder.
            stale=(args.review_dir/'notices'/f'{r["synthetic_notice_id"]}.html').resolve()
            assert stale.is_relative_to(args.review_dir.resolve())
            stale.unlink(missing_ok=True)
            continue
        assert r['synthetic_notice_id'] not in ids
        ids.add(r['synthetic_notice_id'])
        thumb = None
        native = r['native_banner']
        if native:
            path = (args.native_root/native['file']).resolve()
            assert path.is_relative_to(args.native_root.resolve())
            raw = path.read_bytes()
            assert common.sha(raw) == native['sha256']
            image = Image.open(io.BytesIO(raw)).convert('RGBA')
            buf = io.BytesIO(); image.save(buf, format='WEBP', lossless=True, exact=True)
            encoded = buf.getvalue()
            assert Image.open(io.BytesIO(encoded)).convert('RGBA').tobytes() == image.tobytes()
            thumb = common.sha(encoded)
            member = f'img/{thumb}.webp'
            if member in source.namelist():
                assert source.read(member) == encoded
            else:
                images[member] = encoded
            image_checks.append({'gacha_id': r['gacha_id'], 'png_sha256': common.sha(raw), 'webp_sha256': thumb, 'pixel_identity': True})
        pack['notices'].append(make_notice(r, thumb))
        links[r['gacha_id']] = r['synthetic_notice_id']
    common.add_links(pack, links)
    assert pack['notices'][:len(original['notices'])] == original['notices']
    assert all(pack['gacha'][k] == v for k, v in original['gacha'].items())
    assert len({n['id'] for n in pack['notices']}) == len(pack['notices'])
    assert all(v in ids for v in pack['gacha'].values())
    for n in pack['notices'][len(original['notices']):]:
        assert 'Generated data summary' in n['body']
        for member in re.findall(r'src="(img/[^"<>]+)"', n['body']):
            assert member in images or member in source.namelist()
        assert n['publish'] < HISTORICAL_CUTOFF
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert args.output.resolve() != args.source_pack.resolve()
    assert args.output.name == 'bunker-notices-complete-generated.zip'
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        def put(name, raw):
            info = zipfile.ZipInfo(name, (2026, 11, 2, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, raw)
        for name in source.namelist():
            put(name, json.dumps(pack, ensure_ascii=False, separators=(',', ':')).encode() if name == 'notices.json' else source.read(name))
        for name, raw in sorted(images.items()):put(name, raw)
        put('generated/evidence.json', args.evidence.read_bytes())
        put('generated/image-validation.json', json.dumps(image_checks, indent=2).encode())
    with zipfile.ZipFile(args.output) as out:
        assert out.testzip() is None
        assert len(out.namelist()) == len(set(out.namelist()))
        assert all(out.read(name) == source.read(name) for name in source.namelist() if name != 'notices.json')
    rows = list(csv.DictReader(args.previous_audit.open(encoding='utf-8-sig')))
    byid = {r['gacha_id']: r for r in targets}
    notices = {n['id']: n for n in pack['notices']}
    for row in rows:
        g = int(row['gacha_id'])
        if g not in byid:continue
        r = byid[g]
        if r.get('direct_notice_id'):
            row.update(status='direct_existing_notice',notice_id=r['direct_notice_id'],
                       notice_title=notices[r['direct_notice_id']]['title'],
                       display_title='Weekly Summons: '+r['historical_schedule_match']['character'],
                       reason='Original-run medal conversion, start, character and shard match notice 906; final-master date conflict resolved.')
            continue
        row.update(status='generated_'+r['category'], notice_id=r['synthetic_notice_id'],
                   notice_title=notices[r['synthetic_notice_id']]['title'], display_title=r['display_title'],
                   reason=r.get('exchange',{}).get('confidence', 'Bunker reconstructed box configuration' if r.get('event') else 'Native identity and available Bunker configuration'))
        if r['configuration_conflicts']:
            row['reason']='Payment conflict: '+' '.join(r['configuration_conflicts'])
        elif r['date_conflict']:
            row['reason']='End date conflict remains unresolved; native exchange snapshot is shown.'
    assert len(rows) == 328 and all(str(r['notice_id']) != '0' for r in rows)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    with (args.report_dir/'all-328.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (args.report_dir/'payment-conflicts.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['gacha_id','title','native_payment','configured_currencies','configuration_source','notice_id'])
        writer.writeheader()
        for r in targets:
            if r['configuration_conflicts']:
                writer.writerow({'gacha_id':r['gacha_id'],'title':r['display_title'],
                                 'native_payment':r['native_banner_terms']['payment'],
                                 'configured_currencies':','.join(sorted({s['cur'] for s in r['bunker_configuration']['steps']})),
                                 'configuration_source':r['bunker_configuration']['source'],'notice_id':r['synthetic_notice_id']})
    summary = {'new_generated_pages': len(generated_targets),'new_direct_links':{str(r['gacha_id']):r['direct_notice_id'] for r in direct_targets},
               'new_categories': dict(Counter(r['category'] for r in generated_targets)),
               'new_original_run_exchange_snapshots': sum(r.get('exchange',{}).get('confidence') == 'original_run_native_snapshot' for r in generated_targets),
               'new_final_master_only_exchange_pages': sum(r.get('exchange',{}).get('confidence') == 'final_native_master_only' for r in targets),
               'new_native_banner_pages': len(image_checks), 'new_distinct_native_images': len(images),
               'new_pages_without_artwork': [r['gacha_id'] for r in targets if not r['native_banner']],
               'new_pages_with_configured_steps': sum(bool(r['bunker_configuration']['steps']) for r in targets),
               'new_pages_with_payment_conflicts': [r['gacha_id'] for r in targets if r['configuration_conflicts']],
               'new_reviewed_banner_titles': sum(bool(r.get('native_title_review')) for r in targets),
               'resolved_summon_end_conflicts': [r['gacha_id'] for r in direct_targets],
               'original_cohort_total': 328, 'original_cohort_without_page': 0,
               'source_notices': len(original['notices']), 'candidate_notices': len(pack['notices']),
               'source_gacha_keys': len(original['gacha']), 'candidate_gacha_keys': len(pack['gacha']),
               'candidate_sha256': common.sha(args.output.read_bytes()), 'candidate_bytes': args.output.stat().st_size,
               'previous_records_and_assets_preserved': True,
               'deployment': 'Separate generated candidate; no default pack, previous candidate, APK or native DB changed.'}
    (args.report_dir/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (args.report_dir/'evidence.json').write_bytes(args.evidence.read_bytes())
    review(args.review_dir, pack, source, images, rows)
    source.close()
    print(json.dumps(summary, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pack', type=Path, default=Path('inputs/bunker-notices-linked-reconstructed.zip'))
    parser.add_argument('--evidence', type=Path, default=Path('inputs/remaining-summon-notice-evidence.json'))
    parser.add_argument('--native-root', type=Path, default=Path('inputs/native-summon-ui'))
    parser.add_argument('--previous-audit', type=Path, default=Path('artifacts/summon-notice-repair-audit/all-328.csv'))
    parser.add_argument('--output', type=Path, default=Path('inputs/bunker-notices-complete-generated.zip'))
    parser.add_argument('--report-dir', type=Path, default=Path('artifacts/generated-summon-notice-audit'))
    parser.add_argument('--review-dir', type=Path, default=Path('artifacts/generated-summon-notice-review'))
    build(parser.parse_args())


if __name__ == '__main__':
    main()
