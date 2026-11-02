"""Recover event drop bonuses through original-run native quest relationships.

Uses binary snapshot hashes, chapter periods, quest/bonus foreign keys and
weapon ascension thresholds. Does not borrow bonuses from the template notice.
"""
import hashlib,importlib.util,json,sqlite3,sys,zipfile
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build/notice-audit/python'))
import msgpack
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from native_notice_costume_bonus import TABLES, recover_costume_bonuses

NAMES=['m_event_quest_chapter','m_event_quest_sequence_group','m_event_quest_sequence',
       'm_quest','m_quest_bonus','m_quest_bonus_weapon_group','m_quest_bonus_effect_group',
       'm_quest_bonus_drop_reward','m_quest_bonus_term_group','m_consumable_item']+TABLES


def group(rows):
    out=defaultdict(list)
    for r in rows:out[r[0]].append(r)
    return out


def periods(r,entries=None):
    native=[b['row'][6:8] for b in r.get('native_banner_periods',[])]
    native+= [b[6:8] for b in r.get('history',{}).get('historical_banner_rows',[])]
    chapter=r.get('event',{}).get('chapter')
    if not native and chapter:native=[[chapter['StartDatetime'],chapter['EndDatetime']]]
    pair=r.get('bunker_configuration',{}).get('raw_added_rule',{}).get('pair')
    if not native and pair and entries and pair in entries:
        native=[b['row'][6:8] for b in entries[pair]['record'].get('native_banner_periods',[])]
    if not native:
        b=r.get('baseline',r);start=b['start']
        # A 1ms probe means "active at the recorded launch", not an end date.
        native=[[start,b.get('end',start+1)]]
    # Exclude reconstructed far-future catalog dates.
    return [(a,b) for a,b in native if 1600000000000<a<b<1750000000000]


def recover(tables,windows,weapons,texts,costumes=None):
    gs={n:group(tables.get(n,[])) for n in NAMES}
    quests={r[0]:r for r in tables.get('m_quest',[]) if len(r)>19}
    bonuses={r[0]:r for r in tables.get('m_quest_bonus',[]) if len(r)>=4}
    items={r[0]:r for r in tables.get('m_consumable_item',[]) if len(r)>=8}
    out=[];skipped=[]
    for ch in tables.get('m_event_quest_chapter',[]):
        if len(ch)<10:continue
        overlaps=[(max(a,ch[8]),min(b,ch[9])) for a,b in windows if max(a,ch[8])<min(b,ch[9])]
        if not overlaps:continue
        title=texts.get('quest.event.chapter_title.'+str(ch[3]))
        if not title:continue
        quest_ids={s[2] for g in gs['m_event_quest_sequence_group'][ch[7]] for s in gs['m_event_quest_sequence'][g[2]]}
        bonus_ids={quests[q][19] for q in quest_ids if q in quests}
        weapon_groups={bonuses[b][3] for b in bonus_ids if b in bonuses and bonuses[b][3]}
        found={}
        for wid in weapons:
            for gid in sorted(weapon_groups):
                candidates=[r for r in gs['m_quest_bonus_weapon_group'][gid] if r[1]==wid]
                if not candidates:continue
                for start,end in overlaps:
                    active=[]
                    for r in candidates:
                        terms=gs['m_quest_bonus_term_group'][r[4]] if len(r)>4 and r[4] else []
                        if terms and not any(v[2]<=start and v[3]>=end for v in terms):
                            skipped.append({'event_id':ch[0],'weapon_id':wid,'reason':'bonus term does not cover the whole overlapping period','row':r});continue
                        if len(r)>4 and r[4] and not terms:continue
                        active.append(r)
                    by_currency=defaultdict(dict);proof=defaultdict(list)
                    for asc in range(5):
                        eligible=[r for r in active if r[2]<=asc]
                        if not eligible:continue
                        threshold=max(r[2] for r in eligible)
                        for wr in [r for r in eligible if r[2]==threshold]:
                            for fx in gs['m_quest_bonus_effect_group'][wr[3]]:
                                if fx[2]!=3:continue
                                for drop in gs['m_quest_bonus_drop_reward'][fx[3]]:
                                    if drop[1]!=6 or drop[2] not in items:continue
                                    by_currency[drop[2]][asc]=drop[3]
                                    proof[drop[2]].append({'weapon_group_row':wr,'effect_row':fx,'drop_row':drop})
                    for currency,values in by_currency.items():
                        if set(values)!=set(range(5)):continue
                        item=items[currency]
                        name=texts.get(f'consumable_item.name.{item[6]}{item[7]:03d}')
                        if not name:continue
                        counts=[values[a] for a in range(5)]
                        key=(wid,currency,tuple(counts),start,end)
                        found[key]={'weapon_id':wid,'currency_id':currency,'currency_name':name,
                                    'additional_drops_by_ascension':counts,'start':start,'end':end,
                                    'weapon_group_id':gid,'native_rows':proof[currency]}
        costume_rows=[]
        for start,end in overlaps:costume_rows+=recover_costume_bonuses(tables,bonus_ids,costumes or set(),start,end)
        if found or costume_rows:
            out.append({'event_id':ch[0],'event_name':title,'chapter_row':ch,
                        'quest_ids':sorted(quest_ids),'quest_bonus_ids':sorted(bonus_ids),
                        'weapon_bonuses':list(found.values()),'costume_bonuses':costume_rows})
    return out,skipped


def main():
    import build_notice_templates as templates
    spec=importlib.util.spec_from_file_location('notice_decoder',ROOT/'.build/notice-audit/master-decoder/dump_masterdata.py')
    dec=importlib.util.module_from_spec(spec);spec.loader.exec_module(dec)
    entries=templates.target_records()
    mappings=json.loads((ROOT/'inputs/summon-notice-template-map.json').read_text(encoding='utf-8'))['matches']
    needed={m['gacha_id'] for m in mappings if m['action']=='adapt_template'}
    archives=[zipfile.ZipFile(p) for p in (ROOT/'inputs/shared-drive-recovery/archives').glob('GL-*.zip')]
    members={Path(i.filename).name:(z,i.filename) for z in archives for i in z.infolist() if i.filename.endswith('.bin.e')}
    with sqlite3.connect('file:C:/GitRepos/bunker-backup-before-replace/inputs/archive.db?mode=ro',uri=True) as db:texts=dict(db.execute('select key,value from text'))
    cached={};results=[]
    for g in sorted(needed):
        r=entries[g]['record'];windows=periods(r,entries)
        src=r.get('exchange',{}).get('source') or r.get('history',{}).get('source')
        weapons={c['weapon_id'] for c in r.get('exchange',{}).get('lineup',r.get('costumes',[])) if c.get('weapon_id')}
        weapons|={c['weapon_id'] for c in r.get('exchange',{}).get('other_exchange_weapons',[])}
        weapons|={p['id'] for level in r.get('event',{}).get('main_prizes',[]) for p in level if p['type']==2}
        costumes={c['costume_id'] for c in r.get('exchange',{}).get('lineup',r.get('costumes',[]))}
        row={'gacha_id':g,'windows':windows,'checked_weapon_ids':sorted(weapons),'checked_costume_ids':sorted(costumes),'events':[]}
        if not windows or not weapons:
            row['status']='no_historical_period_or_known_weapon_ids';results.append(row);continue
        if not src:
            choices=[n for n in members if any(a<=int(datetime.strptime(n[:14],'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).timestamp()*1000)<=b for a,b in windows)]
            if not choices:
                row['status']='no_original_run_snapshot';results.append(row);continue
            name=min(choices);z,member=members[name];raw=z.read(member)
            src={'source_file':name,'archive':str(z.filename),'archive_member':member,'sha256':hashlib.sha256(raw).hexdigest()}
        name=src['source_file']
        if name not in cached:
            z,member=members[name];raw=z.read(member);assert hashlib.sha256(raw).hexdigest()==src['sha256']
            plain=unpad(AES.new(bytes.fromhex(dec.DEFAULT_KEY),AES.MODE_CBC,bytes.fromhex(dec.DEFAULT_IV)).decrypt(raw),16)
            try:toc=msgpack.unpackb(plain,raw=False,strict_map_key=False);blob=b''
            except msgpack.ExtraData as ex:toc,blob=ex.unpacked,ex.extra
            cached[name]={n:dec.decompress_table(blob,*toc[n]) for n in NAMES if n in toc}
            print('Decoded',name,flush=True)
        row['source']={k:src[k] for k in ['source_file','sha256','archive','archive_member']}
        row['events'],row['unresolved_terms']=recover(cached[name],windows,weapons,texts,costumes)
        row['status']='original_run_native_bonus_rows' if row['events'] else 'no_matching_drop_bonus_recovered'
        results.append(row)
    for z in archives:z.close()
    result={'version':1,'method':'Native chapter period → sequence group → sequence → quest → quest bonus → weapon group → effect → drop reward. Ascension thresholds 0–4; exact snapshot hashes. No template bonuses copied.',
            'counts':dict(Counter(r['status'] for r in results)),'snapshots_decoded':len(cached),'entries':results}
    output=ROOT/'inputs/summon-notice-event-bonuses.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['counts'],indent=2))


if __name__=='__main__':main()
