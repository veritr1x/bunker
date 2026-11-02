"""Build a separate, provenance-labelled notice candidate from reviewed evidence.

Never edits the source pack, default pack, lock file, native DB or installed APK.
Python 3 + Pillow are required. Prepared evidence includes scoped historical rows.
"""
import argparse
import copy
import csv
import hashlib
import html
import io
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PST = timezone(timedelta(hours=-8))
DAY = 86400000
SYNTHETIC_BASE = 1500000000


def sha(data):
    return hashlib.sha256(data).hexdigest()


def medal_fields(row):
    """2021 lacks trailing ConversionRate, not CeilingCount."""
    if len(row) not in (5, 6):
        raise ValueError('Unsupported historical medal schema')
    return dict(zip(('id', 'ceiling', 'currency', 'gacha', 'conversion', 'rate'), row))


def validate_history(target):
    h = target['history']
    medal = medal_fields(h['historical_medal_raw'])
    expected = target['medal']
    assert medal['currency'] == expected['ConsumableItemId']
    assert medal['conversion'] == expected['AutoConvertDatetime']
    assert medal['ceiling'] == expected['CeilingCount']
    assert sorted(h['historical_exchange_lineup']) == sorted(target['fingerprint'])
    assert not h['missing_expected_costumes'] and not h['extra_historical_costumes']
    assert not h['unpaired_ceiling_weapons']
    assert h['historical_exchange_prices'] == [medal['ceiling']]
    # Check raw rows as well as the earlier extractor's verdict.
    found = set()
    for e in h['historical_exchange_evidence']:
        assert e['item'][4:7] == [1, medal['currency'], medal['ceiling']]
        assert e['shop'][9] <= target['start'] <= e['shop'][10]
        assert e['shop'][7] == e['group'][0]
        assert e['group'][1] == e['cell'][0]
        assert e['cell'][2] == e['item'][0] == e['possession'][0]
        if e['term'] is not None:
            assert e['term'][1] <= target['start'] <= e['term'][2]
        found.add(e['costume_id'])
    assert found == set(target['fingerprint'])
    historical_skins = {r[0]: r for r in h['historical_costume_rows']}
    historical_weapons = {r[0]: r for r in h['historical_weapon_rows']}
    for c in target['costumes']:
        r = historical_skins[c['costume_id']]
        assert r[1] == c['character_id'] and r[7] == 40
        assert c['asset'] == f'ch{r[4]:03d}{r[5]:03d}'
        assert c['weapon_id'] in historical_weapons
    if target['date_evidence'] == 'historical_native_home_banner':
        banners = h['historical_banner_rows']
        assert len(banners) == 1
        assert banners[0][3] == target['gacha_id']
        assert banners[0][6:8] == [target['start'], target['end']]
    else:
        assert target['date_evidence'] == 'inferred_from_exchange_start_and_conversion_minus_two_days'
        assert target['end'] == medal['conversion'] - 2 * DAY
        assert min(r[9] for r in h['historical_shop_rows']) == target['start']
    removed = sorted(set(target['reference_fingerprint']) - set(target['fingerprint']))
    assert removed == target['roster_removed_from_reference']


def date(ms):
    return datetime.fromtimestamp(ms / 1000, PST).strftime('%b %d, %Y %H:%M:%S PST')


def esc(value):
    return html.escape(str(value), quote=True)


def reconstructed_notice(target, thumb):
    """Generate a factual summary; never clone a later announcement's rules."""
    verified = target['date_evidence'] == 'historical_native_home_banner'
    date_note = ('Availability is verified by the original run’s native home-banner record.' if verified else
                 'Availability is inferred from the native exchange opening and shard conversion two days after the summon end, following Bunker’s catalog convention. An original summon-end announcement has not been recovered.')
    price = target['history']['historical_exchange_prices'][0]
    rows = ''.join('<tr><td>'+esc(c['character'])+'</td><td>'+esc(c['costume'])+'</td><td>'+esc(c['weapon'])+'</td></tr>'
                   for c in target['costumes'])
    corrections = []
    if target['reference_exchange_prices'] != [price]:
        corrections.append(f'This run’s exchange cost is {price} shards per listed character weapon; the reference rerun uses {target["reference_exchange_prices"][0]}.')
    if target['roster_removed_from_reference']:
        corrections.append('The later reference includes an additional costume. This summary includes only the original run’s verified exchange lineup.')
    correction_html = '<ul>'+''.join('<li>'+esc(s)+'</li>' for s in corrections)+'</ul>' if corrections else ''
    source = target['history']['source']
    nid = target['reference_notice_id']
    body = f'''<section>
<h3>Reconstructed historical summary</h3>
<p>This page was reconstructed from native game data and a surviving rerun notice. It is not recovered original announcement text.</p>
<img src="img/{thumb}.webp" alt="Original native summon banner" width="234">
<h3>Historical availability</h3>
<p>{esc(date(target['start']))} – {esc(date(target['end']))}</p>
<p>{esc(date_note)}</p>
<h3>Verified shard exchange lineup</h3>
<p>{esc(target['shard_name'])}: <b>{price} shards</b> per listed character weapon. These are verified exchange options; no individual appearance rates are asserted.</p>
<table><thead><tr><th>Character</th><th>Costume</th><th>Paired weapon</th></tr></thead><tbody>{rows}</tbody></table>
<p>Native shard conversion time: {esc(date(target['medal']['AutoConvertDatetime']))}.</p>
{correction_html}
<h3>Details not recovered</h3>
<p>The original gem costs, individual summon rates, step guarantees, bonus rewards, duplicate rewards and awakening rewards have not been verified for this run and are omitted. Check Bunker’s current Summons Details for its implemented rules.</p>
<details><summary>Reconstruction sources</summary>
<p>Related rerun: <a href="?informationId={nid}">{esc(target['reference_notice_title'])}</a>. Its later dates and rules have not been copied to this run.</p>
<p>Original-run native snapshot: {esc(source['source_file'])}. Its filename is a snapshot observation label, not a notice publication timestamp. Character and weapon names use the available native English text; period-specific spelling may differ.</p>
<p>This page is placed at the run’s start in the offline archive. The original publication time is unknown. The banner is extracted native artwork.</p>
</details></section>'''
    return {'id': target['synthetic_notice_id'], 'type': 3,
            'title': target['display_title'],
            'publish': target['start'], 'thumb': thumb, 'body': body}


def add_links(pack, links):
    ids = {n['id'] for n in pack['notices']}
    for g, n in links.items():
        assert str(g) not in pack['gacha'], f'Existing link must not be replaced: {g}'
        assert n in ids and 0 < n <= 2147483647
        pack['gacha'][str(g)] = n


CSS = '''body{font:16px/1.55 system-ui,sans-serif;color:#222;background:#f7f5ef;margin:0 auto;padding:28px;max-width:1160px}a{color:#174e74}h1{font-size:28px;line-height:1.2}h2,h3{margin-top:28px}table{border-collapse:collapse;width:100%;background:white}th,td{padding:10px 12px;border:1px solid #d5d0c5;text-align:left;vertical-align:top}th{background:#e9e5da}img{max-width:100%;height:auto}.thumb{width:234px}.note{background:#e8eee6;padding:16px;border-left:4px solid #48634d}.muted,small{color:#666}input{padding:10px;width:min(600px,90%);font:inherit;margin:14px 0}.count{font-size:24px;font-weight:650}details{margin:20px 0}section{overflow-wrap:anywhere}.holding-period{padding:10px;background:#e9e5da}@media(max-width:700px){body{padding:14px}th,td{padding:6px;font-size:14px}}'''


def page(title, body, root='../'):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(title)+'</title><style>'+CSS+'</style><body><p><a href="'+root+'index.html">Summon notice repair audit</a></p>'+body+'</body></html>'


def write_review(folder, pack, source_zip, new_images, evidence, audit_rows):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'img').mkdir(exist_ok=True)
    (folder/'notices').mkdir(exist_ok=True)
    for name in source_zip.namelist():
        if re.fullmatch(r'img/[A-Za-z0-9_-]+\.webp', name):
            (folder/name).write_bytes(source_zip.read(name))
    for name, data in new_images.items():
        (folder/name).write_bytes(data)
    for n in pack['notices']:
        body = re.sub(r'(["\'])img/', r'\1../img/', n['body'])
        body = re.sub(r'(["\'])\?informationId=(\d+)(["\'])', r'\1\2.html\3', body)
        (folder/'notices'/f'{n["id"]}.html').write_text(page(n['title'], '<h1>'+esc(n['title'])+'</h1>'+body), encoding='utf-8')
    rows = []
    for r in audit_rows:
        title = esc(r['display_title'] or r['original_title'] or r['asset'])
        link = f'<a href="notices/{r["notice_id"]}.html">{esc(r["notice_id"])}</a>' if r['notice_id'] else '—'
        rows.append(f'<tr><td>{r["gacha_id"]}</td><td>{title}<br><small>{esc(r["asset"])}</small></td><td>{esc(r["status"])}</td><td>{link}</td><td>{esc(r["reason"])}</td></tr>')
    body = '''<h1>Summon notice repairs</h1><p class="count">106 direct links · 19 reconstructed summaries · 203 unresolved</p>
<p class="note">Candidate pack for the original 328 unlinked entries. Reconstructed pages are visibly labelled. No default pack, APK or native English database has been changed.</p>
<p>74 weekly links use actual announcement schedules, 17 event boxes use same-run event notices, 11 recover explicit rules lost by loader precedence, and 4 use matching run dates, format and costume rosters. Two end-date conflicts remain unresolved.</p>
<p>Notice 756’s title is corrected to Aurora Phantom, matching its original body and artwork. Summon 556001 links to Resolute Dress; its stale native Replicant title is recorded for separate correction.</p>
<input id="filter" aria-label="Filter audit entries" placeholder="Filter by summon, title, status or reason…">
<table><thead><tr><th>Summon</th><th>Identity / asset</th><th>Status</th><th>Notice</th><th>Evidence / remaining gap</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<script>document.querySelector('#filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'''
    (folder/'index.html').write_text(page('Summon notice repair audit', body, ''), encoding='utf-8')


def build(args):
    from PIL import Image
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    assert sha(args.source_pack.read_bytes()) == evidence['source_pack']['sha256']
    source = zipfile.ZipFile(args.source_pack)
    original = json.loads(source.read('notices.json'))
    pack = copy.deepcopy(original)
    existing = {n['id']: n for n in pack['notices']}
    baseline = {r['gacha_id']: r for r in evidence['baseline']}
    assert len(baseline) == 328
    direct = {r['gacha_id']: r for r in evidence['direct']}
    reconstructed = {r['gacha_id']: r for r in evidence['reconstructed']}
    review = {r['gacha_id']: r for r in evidence['review_only']}
    assert not set(direct) & set(reconstructed)
    assert not (set(direct) | set(reconstructed)) & set(review)
    assert set(direct) | set(reconstructed) | set(review) <= set(baseline)
    images, image_checks = {}, []
    for correction in evidence['notice_title_corrections']:
        n = existing[correction['notice_id']]
        assert n['title'] == correction['original']
        n['title'] = correction['corrected']
    for g, target in reconstructed.items():
        validate_history(target)
        nid = target['synthetic_notice_id']
        assert nid == SYNTHETIC_BASE + g and nid not in existing and nid <= 2147483647
        assert target['reference_notice_id'] in existing
        native = target['native_banner']
        path = (args.native_root/native['file']).resolve()
        assert path.is_relative_to(args.native_root.resolve())
        raw = path.read_bytes()
        assert sha(raw) == native['sha256']
        image = Image.open(io.BytesIO(raw)).convert('RGBA')
        assert image.size == (native['width'], native['height'])
        buf = io.BytesIO()
        image.save(buf, format='WEBP', lossless=True, exact=True)
        encoded = buf.getvalue()
        assert Image.open(io.BytesIO(encoded)).convert('RGBA').tobytes() == image.tobytes()
        key = sha(encoded)
        image_name = f'img/{key}.webp'
        if image_name in source.namelist():
            assert source.read(image_name) == encoded
        else:
            images[image_name] = encoded
        image_checks.append({'gacha_id': g, 'native_png_sha256': sha(raw), 'webp_sha256': key,
                             'pixel_identity_verified': True, 'image_member': image_name})
        n = reconstructed_notice(target, key)
        pack['notices'].append(n)
        existing[nid] = n
    links = {g: r['notice_id'] for g, r in direct.items()}
    links.update({g: r['synthetic_notice_id'] for g, r in reconstructed.items()})
    add_links(pack, links)
    # Every original record except the reviewed title correction stays identical.
    corrections = {r['notice_id']: r for r in evidence['notice_title_corrections']}
    for n in original['notices']:
        expected = copy.deepcopy(n)
        if n['id'] in corrections:
            expected['title'] = corrections[n['id']]['corrected']
        assert existing[n['id']] == expected
    assert all(pack['gacha'][g] == n for g, n in original['gacha'].items())
    assert len(existing) == len(pack['notices'])
    assert all(n in existing for n in pack['gacha'].values())
    all_members = set(source.namelist()) | set(images)
    for n in pack['notices'][-len(reconstructed):]:
        for ref in re.findall(r'src="(img/[^"<>]+)"', n['body']):
            assert ref in all_members
        assert 'Reconstructed historical summary' in n['body']
    metadata = {'evidence_sha256': sha(args.evidence.read_bytes()), 'image_checks': image_checks,
                'publication_policy': 'Synthetic pages placed at target run start; original publication time unknown.',
                'original_notice_bodies_preserved': True, 'existing_gacha_links_preserved': True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert args.output.resolve() != args.source_pack.resolve()
    assert args.output.name not in ('bunker-notices.zip', 'bunker-notices-recovered.zip')
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        def put(name, data):
            info = zipfile.ZipInfo(name, (2026, 11, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, data)
        for name in source.namelist():
            put(name, json.dumps(pack, ensure_ascii=False, separators=(',', ':')).encode() if name == 'notices.json' else source.read(name))
        for name, data in sorted(images.items()):
            put(name, data)
        put('reconstruction/evidence.json', args.evidence.read_bytes())
        put('reconstruction/validation.json', json.dumps(metadata, indent=2).encode())
    with zipfile.ZipFile(args.output) as out:
        assert out.testzip() is None
        assert len(out.namelist()) == len(set(out.namelist()))
        assert all(out.read(name) == source.read(name) for name in source.namelist() if name != 'notices.json')
    title_review = {r['gacha_id']: r['corrected_identity'] for r in evidence['native_title_review']}
    audit_rows = []
    for g, b in sorted(baseline.items()):
        if g in direct:
            status, reason, nid = 'direct_existing_notice', direct[g]['reason'], direct[g]['notice_id']
        elif g in reconstructed:
            status, reason, nid = 'labelled_reconstruction', reconstructed[g]['date_evidence'], reconstructed[g]['synthetic_notice_id']
        elif g in review:
            status, reason, nid = 'unresolved_date_conflict', review[g]['reason'], 0
        else:
            status, nid = 'unresolved', 0
            reason = ('Two-character weekly format; no matching original notice or safe full rerun template.' if 10000 < g < 10200 else
                      'Same-run event notice not verified.' if b['source'] == 'event_box' else
                      'Run-specific notice or sufficient historical summon rules not verified.')
        display = reconstructed[g]['display_title'] if g in reconstructed else title_review.get(g, b['title'])
        audit_rows.append({'gacha_id': g, 'asset': b['asset'], 'source': b['source'], 'original_title': b['title'],
                           'display_title': display, 'start_pst': date(b['start']), 'status': status,
                           'notice_id': nid, 'notice_title': existing[nid]['title'] if nid else '', 'reason': reason})
    args.report_dir.mkdir(parents=True, exist_ok=True)
    with (args.report_dir/'all-328.csv').open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0]))
        writer.writeheader(); writer.writerows(audit_rows)
    summary = {'scope': evidence['scope'], 'baseline_unlinked': len(baseline), 'direct_links': len(direct),
               'reconstructed_links': len(reconstructed), 'corrected_total': len(links),
               'remaining_unlinked': len(baseline)-len(links), 'review_only_date_conflicts': len(review),
               'date_verified_reconstructions': sum(r['date_evidence'] == 'historical_native_home_banner' for r in reconstructed.values()),
               'date_inferred_reconstructions': sum(r['date_evidence'] != 'historical_native_home_banner' for r in reconstructed.values()),
               'direct_evidence_reasons': dict(Counter(r['reason'] for r in direct.values())),
               'original_notice_count': len(original['notices']), 'candidate_notice_count': len(pack['notices']),
               'original_gacha_map_keys': len(original['gacha']), 'candidate_gacha_map_keys': len(pack['gacha']),
               'original_images': sum(n.startswith('img/') for n in source.namelist()), 'native_images_added': len(images),
               'candidate_path': str(args.output.resolve()), 'candidate_sha256': sha(args.output.read_bytes()),
               'validation': metadata, 'deployment': 'Separate candidate only; defaults, lock, native DB and installed APK unchanged.'}
    (args.report_dir/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (args.report_dir/'evidence.json').write_bytes(args.evidence.read_bytes())
    write_review(args.review_dir, pack, source, images, evidence, audit_rows)
    source.close()
    print(json.dumps({k: v for k, v in summary.items() if k != 'validation'}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pack', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=Path('inputs/summon-notice-repair-evidence.json'))
    parser.add_argument('--native-root', type=Path, default=Path('inputs/native-summon-ui'))
    parser.add_argument('--output', type=Path, default=Path('inputs/bunker-notices-linked-reconstructed.zip'))
    parser.add_argument('--review-dir', type=Path, default=Path('artifacts/summon-notice-repair-review'))
    parser.add_argument('--report-dir', type=Path, default=Path('artifacts/summon-notice-repair-audit'))
    build(parser.parse_args())


if __name__ == '__main__':
    main()
