#!/usr/bin/env python3
"""Bring the reconstructed notices' summon prices in line with the summon rules.

The notice pack's reconstructed notices (ids from 1500000000; the recovered
originals are never touched) show a "Summons Details" table written when the
pack was built. When a summon's prices are corrected later in
overlays/server/internal/masterdata/summon_rules.json, its table goes stale.
This rewrites the rows and the notes under them of every reconstructed notice
whose table no longer matches its summon's rule steps, in the pack's own
format (rich_notice_content), and writes a new pack. A row's "Other" cell is
kept when its step and draws are unchanged (its bonus items and icons), with
the use limit brought up to date.

    python3 scripts/sync_notice_prices.py --source-pack inputs/bunker-notices.zip --output inputs/bunker-notices-synced.zip
"""
import argparse
import html
import json
import os
import re
import zipfile
from pathlib import Path

# As rich_notice_content (GEM, esc, RichNotices.guarantee), which builds need
# not install (it needs Pillow and Beautiful Soup); test_sync_notice_prices
# checks they agree.
GEM = 'img/c_0a0f76549d1cbb9f.webp'


def esc(s):
    return html.escape(str(s), quote=True)


def guarantee(s):
    code = s.get('guar', '').lower()
    if not code or code == 'none':
        return ''
    count = s.get('guaranteed_count', 1)
    quantity = 'one' if count == 1 else str(count)
    element = code.split(':', 1)[1].title() + ' ' if ':' in code else ''
    character = 'character ' if code.startswith('r4c') or code.startswith('set') else ''
    rarity = '★★★ or higher' if code.startswith('r3') else '★★★★'
    if s.get('guarantee_slot'):
        return f'The {s["guarantee_slot"]}th summon guarantees a {rarity} {element}{character}weapon.'
    return f'At least {quantity} {rarity} {element}{character}weapon' + (' is' if count == 1 else 's are') + ' guaranteed.'

SYNTHETIC_BASE = 1500000000
ROW = re.compile(r'<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>', re.S)
LIMIT = re.compile(r'(?:<br/?>)?\s*(?:Can be used|Up to) \d+ times?(?: per day| per cycle)?\.')


def rule_steps(rules):
    steps = {int(g): r['steps'] for g, r in rules['rules'].items() if r.get('steps')}
    for n in rules['new']:
        if n.get('steps'):
            steps.setdefault(n['id'], n['steps'])
    return steps


def details(body):
    """The Summons Details table and the notes paragraph after it: (start, end) in body, or None."""
    head = body.find('<h3>Summons Details</h3>')
    if head < 0:
        return None
    start = body.find('<div class="information_table">', head)
    end = body.find('</table></div>', start)
    if start < 0 or end < 0:
        return None
    end += len('</table></div>')
    if body.startswith('<p>', end):
        end = body.index('</p>', end) + len('</p>')
    return start, end


def parse(table):
    rows = []
    for label, price, other in ROW.findall(table):
        m = re.match(r'(?:Step (\d+): )?(\d+)x summon', re.sub('<[^>]+>', '', label))
        text = re.sub('<[^>]+>', '', price).strip()
        if text == 'Free':
            cur, amount = 'free', 0
        else:
            p = re.match(r'([\d,]+) (paid gems|gems)', text)
            cur, amount = ({'paid gems': 'paid', 'gems': 'gems'}[p[2]], int(p[1].replace(',', ''))) if p else ('ticket', None)
        limit = re.search(r'(?:Can be used|Up to) (\d+) time', other)
        rows.append({'step': int(m[1] or 0) if m else None, 'draws': int(m[2]) if m else None, 'cur': cur, 'price': amount,
                     'limit': int(limit[1]) if limit else 0, 'daily': 'per day' in other or 'Once a day' in other, 'other': other})
    return rows


def key(s):
    """What a row says: a ticket row names no count, and a multi-step's step is
    once per cycle unless its rule says otherwise."""
    limit = s.get('limit', 0) or (1 if s.get('step') else 0)
    price = None if s['cur'] == 'ticket' else 0 if s['cur'] == 'free' else s.get('price', 0)
    return (s.get('step', 0), s['draws'], s['cur'], price, limit, bool(s.get('daily')))


def limit_note(s):
    n = s.get('limit') or (1 if s.get('step') else 0)
    if not n:
        return ''
    return f"Can be used {n} time{'s' if n != 1 else ''}" + (' per day.' if s.get('daily') else ' per cycle.' if s.get('step') else '.')


def other_cell(s, old):
    if old is not None:
        cell = LIMIT.sub('', old['other'])
        note = limit_note(s)
        return cell + ('<br/>' if cell and note else '') + note if note else (cell or '—')
    parts = []
    g = guarantee(s)
    if g:
        parts.append('<span class="text-red">' + g + '</span>')
    if s.get('feat4'):
        parts.append('★★★★ character weapons are selected from the featured characters.')
    if s.get('rate'):
        parts.append(f'<span class="text-red">★★★★ appearance-rate multiplier ×{s["rate"]:g}</span>')
    parts += [esc(re.sub(r' x(\d)', r' ×\1', b)) for b in s.get('bonus', [])]
    if limit_note(s):
        parts.append(limit_note(s))
    return '<br/>'.join(parts) or '—'


def render(steps, old_rows):
    by_step = {(r['step'], r['draws']): r for r in old_rows}
    rows = []
    for s in steps:
        if s['cur'] == 'free':
            price = 'Free'
        elif s['cur'] in ('paid', 'gems'):
            price = f'<img alt="" class="gem_icon" src="{GEM}" width="16px"/> {s.get("price", 0):,} ' + ('paid gems' if s['cur'] == 'paid' else 'gems')
        else:
            price = esc(s.get('ticket_name', 'Summon ticket'))
        label = f"Step {s['step']}: " if s.get('step') else ''
        old = by_step.get((s.get('step', 0), s['draws']))
        rows.append(f'<tr><td>{label}{s["draws"]}x summon</td><td>{price}</td><td>{other_cell(s, old)}</td></tr>')
    notes = []
    currencies = {s['cur'] for s in steps}
    if currencies == {'paid'}:
        notes.append('This summons can only be used with paid gems.')
    elif currencies == {'paid', 'free'}:
        notes.append('Paid steps require paid gems. Steps marked Free do not consume gems.')
    for s in steps:
        g = guarantee(s)
        if g and g not in notes:
            notes.append(g)
    return ('<div class="information_table"><table style="width:100%"><thead><tr><th>Type</th><th>Required Gems / Tickets</th>'
            '<th>Other</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>' + '<p>' + '<br/>'.join(esc(n) for n in notes) + '</p>')


def sync(pack, rules):
    """Rewrites pack (the parsed notices.json) in place; returns [(gacha, notice id)] changed."""
    steps = rule_steps(rules)
    by_id = {n['id']: n for n in pack['notices']}
    changed = []
    for g, nid in sorted(((int(g), n) for g, n in pack['gacha'].items()), key=lambda x: x[0]):
        if nid < SYNTHETIC_BASE or g not in steps or nid not in by_id:
            continue
        body = by_id[nid]['body']
        span = details(body)
        if not span:
            continue
        old = parse(body[span[0]:span[1]])
        if [key(dict(r, step=r['step'] or 0)) for r in old] == [key(s) for s in steps[g]]:
            continue
        by_id[nid]['body'] = body[:span[0]] + render(steps[g], old) + body[span[1]:]
        changed.append((g, nid))
    return changed


RULES = Path(__file__).resolve().parents[1] / 'overlays/server/internal/masterdata/summon_rules.json'


def write(source, output, rules=RULES):
    """Writes source's pack to output with its notices synced; returns [(gacha, notice id)] changed."""
    output = Path(output)
    partial = output.with_name(output.name + '.partial')
    try:
        with zipfile.ZipFile(source) as src:
            pack = json.loads(src.read('notices.json'))
            changed = sync(pack, json.loads(Path(rules).read_text()))
            with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as out:
                for info in src.infolist():
                    data = json.dumps(pack, ensure_ascii=False).encode() if info.filename == 'notices.json' else src.read(info.filename)
                    out.writestr(info, data)
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return changed


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source-pack', type=Path, required=True)
    p.add_argument('--rules', type=Path, default=RULES)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    changed = write(a.source_pack, a.output, a.rules)
    for g, nid in changed:
        print(f'summon {g}: notice {nid}')
    print(f'{len(changed)} notices brought in line with the summon rules -> {a.output}')


if __name__ == '__main__':
    main()
