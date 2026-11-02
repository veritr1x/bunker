"""Find surviving notice bases, promote proven links, and adapt synthetic pages.

Section order and generic Notes come from the base. Native title graphics,
promotional panels and item icons come from each target's own assets. Detailed
summon rules and exchanges use target-specific configuration and run evidence.
"""
import argparse, copy, csv, hashlib, json, re, sys, zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.build/notice-audit/python'))
from bs4 import BeautifulSoup
import build_summon_notice_repair_pack as common
import build_remaining_summon_notices as generated
from rich_notice_content import RichNotices, export_game_previews

ROOT=Path(__file__).resolve().parents[1]
SYNTH=common.SYNTHETIC_BASE
MONTHS={m:i for i,m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split(),1)}
DATE=re.compile(r'([A-Za-z]+)\.?\s+(\d{1,2})\s+(\d{1,2}):(\d{2})')
EXACT={540001:895,580001:1336,583001:1371,588001:1380,608001:1557,612001:1615}
CAMPAIGN={456:903,457:903,554:1382,**{g:1592 for g in [600,601,602,603,604,605,609,610]}}
REVIEWED_BASES={31:1050,180:1050,58:978,194:978,160:962,970001:683,970002:683,9000041:895,9000062:1259}


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def soup(body):return BeautifulSoup(body,'html5lib')
def plain(body):return soup(body).get_text(' ',strip=True)
def norm(value):return re.sub(r'[^a-z0-9]+',' ',value.lower().replace('’',"'")).strip()
def date_pairs(value,year):
    dates=[]
    for mon,day,hour,minute in DATE.findall(value):
        month=MONTHS[mon[:3].lower()]
        y=year+(1 if dates and month<dates[0].month-6 else 0)
        dates.append(datetime(y,month,int(day),int(hour),int(minute),tzinfo=common.PST))
    return [(int(a.timestamp()*1000),int(b.timestamp()*1000)) for a,b in zip(dates[::2],dates[1::2])]


def payment(title,r=None):
    t=norm(title)
    if 'paid' in t:return 'paid'
    if 'free' in t:return 'free'
    if r:
        terms=r.get('native_banner_terms',{})
        if terms.get('payment'):return terms['payment']
        steps=r.get('bunker_configuration',{}).get('steps',[])
        currencies={s['cur'] for s in steps}
        if 'paid' in currencies:return 'paid'
        if 'gems' in currencies:return 'gems'
        if currencies=={'ticket'}:return 'ticket'
        if currencies=={'free'}:return 'free'
    if 'choice weapons' in t or 'ticket summons' in t:return 'ticket'
    return 'gems'


def family(title,r=None):
    t=norm(title)
    if r and r.get('event'):return 'event_variation'
    if 'variation' in t and 'event quest' in t:return 'event_variation'
    if 'weekly' in t or (r and 10000<r['gacha_id']<10200):return 'weekly'
    if (r and (r['asset'].startswith('confirm') or payment(title,r)=='ticket')) or 'ticket summons' in t or 'choice weapons' in t:return 'ticket'
    if any(x in t for x in ['replicant','automata','drakengard','fantasy xiv','phantasmal','tale of resistance','never ending adventure','crossover']):return 'crossover'
    if 'elemental' in t:return 'elemental'
    if 'guaranteed' in t or 'awakening' in t:return 'guaranteed'
    if 'new chapter' in t or 'release countdown' in t:return 'new_chapter'
    if 'festival' in t or 'abyssal costume' in t:return 'festival'
    if 'subjugation' in t:return 'subjugation'
    if 'multi step' in t or (r and r['asset'].startswith('step_up_')):return 'multi_step'
    if 'bonus' in t:return 'bonus'
    if payment(title,r)=='free':return 'free'
    if 'daily showcase' in t:return 'daily'
    return 'premium'


def target_records():
    remaining=load(ROOT/'inputs/remaining-summon-notice-evidence.json')['generated']
    records={r['gacha_id']:{'record':r,'title':r['display_title'],'kind':'native_data'}
             for r in remaining if not r.get('direct_notice_id')}
    for r in load(ROOT/'inputs/summon-notice-repair-evidence.json')['reconstructed']:
        records[r['gacha_id']]={'record':r,'title':r['display_title'],'kind':'verified_rerun'}
    assert len(records)==220
    return records


def validate_direct(g,entry,n):
    r=entry['record'];text=plain(n['body'])
    if g in EXACT:
        assert n['publish']==r['baseline']['start']
        assert r['exchange']['lineup']
        assert all(c['costume'] in text for c in r['exchange']['lineup'])
        assert 'paid' in norm(n['title']) and payment(entry['title'],r)=='paid'
        return {'method':'same_run_paid_banner_identity_start_and_full_recorded_exchange_roster',
                'start':r['baseline']['start'],'costumes':[c['costume_id'] for c in r['exchange']['lineup']]}
    assert g in CAMPAIGN
    s=soup(n['body']);year=datetime.fromtimestamp(n['publish']/1000,common.PST).year
    if g==554:
        heading=next(h for h in s.select('h3,h4') if 'Crossover Commemorative 10 Free Summons' in h.get_text(' ',strip=True))
        section=heading.find_parent('section')
        periods=[p for el in section.select('.holding-period') for p in date_pairs(el.get_text(' ',strip=True),year)]
        assert 'one time only' in norm(section.get_text(' ',strip=True))
    else:
        periods=[p for el in s.select('.holding-period') for p in date_pairs(el.get_text(' ',strip=True),year)]
        assert 'free' in norm(text) and 'day' in norm(text)
    matches=[]
    for b in r['native_banner_periods']:
        start,end=b['row'][6:8]
        for a,z in periods:
            if start==a and end//60000==z//60000:matches.append((a,z))
    assert len(set(matches))==1,(g,periods)
    assert r['native_banner_terms']['payment']=='free' and r['native_banner_terms']['draws']==10
    return {'method':'same_campaign_native_art_free_terms_and_exact_schedule_slot',
            'period':list(matches[0]),'native_banner_sha256':r['native_banner']['sha256']}


def choose_base(g,entry,notices):
    r=entry['record'];title=entry['title'];f=family(title,r);pay=payment(title,r)
    if entry['kind']=='verified_rerun':
        return r['reference_notice_id'],'verified_rerun_reference',1000
    if g in REVIEWED_BASES:
        return REVIEWED_BASES[g],'reviewed_format_reference',950
    if 'automata' in norm(title):return (1053 if pay=='paid' else 1052),'same_franchise_format',900
    pools={'weekly':[n for n in notices.values() if 'Weekly Summons Open' in n['title']],
           'event_variation':[n for n in notices.values() if family(n['title'])=='event_variation' and 'On Now' in n['title']],
           'ticket':[notices[i] for i in [683,735,650,1619]],
           'free':[notices[i] for i in [903,960,1592,643]],
           'elemental':[notices[i] for i in [801,962,1142,1300]],
           'daily':[notices[i] for i in [1259,683]]}
    candidates=pools.get(f) or [n for n in notices.values() if 'summon' in norm(n['title'])
        and ('On Now' in n['title'] or n['id'] in [196,1592])
        and not any(x in norm(n['title']) for x in ['issue','coming soon','updated','vol 2 added'])
        and family(n['title']) not in ['event_variation','weekly']]
    target_tokens=set(norm(title).split())-set('summons summon on now paid only free step multi the of and in'.split())
    chars=[c.get('costume','') for c in r.get('exchange',{}).get('lineup',r.get('costumes',[]))]
    def score(n):
        nt=set(norm(n['title']).split());nf=family(n['title']);np=payment(n['title'])
        lexical=sum(8 if t in {'abstract','lacrima','abyssal','bloodless','fractured','yuletide','summer','swimwear','mama','anniversary','subjugation','monthly','black','friday'} else 3 for t in target_tokens&nt)
        value=lexical+(40 if f==nf else 0)+(22 if pay==np else -22)
        value+=7 if ('multi step' in norm(title))==('multi step' in norm(n['title'])) else -7
        value+=min(12,sum(2 for c in chars if c and norm(c) in n['_norm']))
        if f=='event_variation':value+=sum(8 for t in target_tokens&nt if t in {'senior','officer','daemon','blossom','resentful','witch','armed','aberration','dynast'})
        return value
    candidates.sort(key=lambda n:(-score(n),abs(n['publish']-r.get('start',r.get('baseline',{}).get('start',0))),n['id']))
    selected=candidates[0]
    strength='same_family_format' if family(selected['title'])==f else 'structural_analogue'
    return selected['id'],strength,score(selected)


def source_role(title):
    t=norm(title)
    if t=='duration':return 'duration'
    if t=='notes':return 'notes'
    if any(x in t for x in ['duplicate','rates up','resonant','quest bonus','mama medal','event missions','changes','memoir']):return None
    if 'how to play event' in t:return 'howto'
    if 'summons details' in t:return 'details'
    if any(x in t for x in ['character','weapons']) and 'guaranteed' not in t:return 'characters'
    if 'shard' in t or ('medal' in t and 'summon' in t):return 'exchange'
    if 'summons' in t and any(x in t for x in ['mage','phantom','daemon','dynast','blossom','officer','aberration','witch','amalgam','oculus']):return 'eventbox'
    return None


def groups(body):
    root=soup(body).find('section');out={};key=None
    for el in list(root.contents):
        if getattr(el,'name',None)=='h3':key=el.get_text(' ',strip=True);out[key]=[]
        elif key:out[key].append(str(el))
    return {k:''.join(v) for k,v in out.items()}


def target_blocks(n):
    gs=groups(n['body']);out={};notes=[];provenance=[]
    for title,content in gs.items():
        if title in ['Generated data summary','Reconstructed historical summary']:continue
        content_soup=soup(content)
        for details in list(content_soup.select('details')):
            if 'sources' in details.get_text(' ',strip=True).lower():
                provenance.append(str(details));details.extract()
        content=''.join(str(e) for e in content_soup.body.contents)
        if title in ['Historical availability','Native event quest period','Recorded home-banner display','Catalog date reference','Historical availability unknown','Historical dates remain unresolved']:out['duration']=content
        elif title in ['Native shard exchange data','Verified shard exchange lineup']:
            x=soup(content);tbl=x.find('table')
            if tbl:
                out['characters']='<p>The following character-weapon pairs are recorded in this run’s exchange data. This is not a verified featured-rate list.</p>'+str(tbl)+'<p>Names use the available native English text.</p>'
                tbl.extract()
            out['exchange']=''.join(str(e) for e in x.body.contents)
        elif title=='Event summons':out['howto']=content
        elif title=='Bunker’s reconstructed box rewards':out['eventbox']=content
        elif title in ['Bunker summon options','Terms visible on the native banner','Payment configuration needs review']:
            out['details']=out.get('details','')+'<h4>'+common.esc(title)+'</h4>'+content
        elif title in ['Details not established','Details not recovered']:notes.append(content)
    out['notes']=''.join(notes);out['provenance']=''.join(provenance)
    if 'details' not in out:out['details']='<p>Original summon prices, step guarantees and bonus rewards have not been established for this run. See the in-game Summons Details for implemented rules.</p>'
    return out


def player_body(body,entry,mapping):
    """Keep playable facts in notices; retain research commentary in the audit."""
    doc=soup(body);removed=[]
    def discard(el):
        removed.append(str(el));el.decompose()
    for el in list(doc.select('.reconstruction-note')):discard(el)
    for el in list(doc.select('details')):
        heading=el.find('summary',recursive=False)
        if heading and any(w in norm(heading.get_text(' ',strip=True)) for w in ['source','limitation']):
            discard(el)
    # Disputed costs remain withheld; their implementation discussion belongs
    # in the external audit rather than the notice's player-facing content.
    for h in list(doc.select('h4')):
        if h.get_text(' ',strip=True)=='Payment configuration needs review':
            node=h.next_sibling
            while node and getattr(node,'name',None) not in ['h3','h4']:
                following=node.next_sibling
                if getattr(node,'name',None):discard(node)
                else:node.extract()
                node=following
            discard(h)
    research_prefixes=(
        'the following character weapon pairs are recorded',
        'names use the available native english text',
        'original individual rates', 'original summon prices',
        'the original gem costs', 'exchange options recorded in original run snapshot',
        'these options come from the final native master',
        'the expected currency record was not found',
        'an exchange can be shared by several banners or volumes',
        'these dates come from native home banner records',
        'these prices and draw counts describe bunker',
        'this is the start used by the reconstructed catalog',
        'bunker associates this banner with a shared or paired exchange',
        'availability is inferred from the native exchange opening',
        'availability is verified by the original run',
        'this is the quest period',
        'the following main prizes describe bunker',
        'usable historical run dates have not been recovered',
        'native snapshots record different display ends',
        'the final master contains a different exchange roster',
        'the original banner artwork has not been recovered',
        'the january weekly schedule and native exchange data disagree',
        'related january schedule',
    )
    for p in list(doc.select('p')):
        text=p.get_text(' ',strip=True);key=norm(text)
        if key.startswith(research_prefixes) or text==entry['title']:
            discard(p)
        elif key.startswith('native shard conversion'):
            clean=re.sub(r'^Native shard conversion(?: time)?:','Shard conversion:',text)
            clean=clean.split(' This is not a verified summon end time.')[0]
            p.clear();p.append(clean)
        elif 'These are verified exchange options;' in text:
            p.clear();p.append(text.split(' These are verified exchange options;')[0])
    for li in list(doc.select('li')):
        text=norm(li.get_text(' ',strip=True))
        if text.startswith(('this run s exchange cost is','the later reference includes an additional costume')):
            discard(li)
    for summary in doc.select('summary'):
        if summary.get_text(' ',strip=True)=='Other recorded weapon exchange entries':
            summary.string='Other Exchange Weapons'
    for h in doc.select('h4'):
        rename={'Bunker summon options':'Summon Options','Terms visible on the native banner':'Summon Terms'}
        if h.get_text(' ',strip=True) in rename:h.string=rename[h.get_text(' ',strip=True)]
    for th in doc.select('th'):
        rename={'Banner text':'Details','Advertised terms':'Value','Configured stock':'Stock','Per prize':'Quantity'}
        if th.get_text(' ',strip=True) in rename:th.string=rename[th.get_text(' ',strip=True)]
    for table in list(doc.select('table')):
        headers=table.select('thead th')
        native_id_cols=[i for i,h in enumerate(headers) if h.get_text(' ',strip=True)=='Native item ID']
        for i in reversed(native_id_cols):
            headers[i].decompose()
            for tr in table.select('tbody tr'):
                cells=tr.find_all('td',recursive=False)
                if len(cells)>i:cells[i].decompose()
    for h in doc.select('h3'):
        if h.get_text(' ',strip=True)=='Characters & Weapons':h.string='Exchange Lineup'
        elif h.get_text(' ',strip=True)=='Duration':
            r=entry['record']
            if entry['kind']=='verified_rerun' and r['date_evidence'].startswith('inferred_'):
                h.string='Estimated Period'
            elif r.get('event'):h.string='Event Period'
            elif r.get('native_banner_periods'):
                h.string='Banner Periods' if len(r['native_banner_periods'])>1 else 'Banner Period'
            elif entry['kind']!='verified_rerun':h.string='Start Date'
    for tag in list(doc.select('ul,section')):
        if tag.name=='ul' and not tag.find('li'):tag.decompose()
    for section in list(doc.select('section')):
        content=[el for el in section.contents if getattr(el,'name',None) not in ['h3','h4']]
        if not any((getattr(el,'name',None)=='img' or (getattr(el,'get_text',None) and el.get_text(' ',strip=True))) for el in content):
            section.decompose()
    mapping['player_ui_removed_html']=removed
    mapping['player_visible_headings']=[h.get_text(' ',strip=True) for h in doc.select('h3')]
    cleaned=''.join(str(el) for el in doc.body.contents)
    assert not any(t in plain(cleaned) for t in ['Details not established','Page sources and limitations',
        'This table does not establish','This is not a verified summon end time',
        'Exchange options recorded in original-run snapshot','These dates come from native home-banner records'])
    return cleaned


def adapt(n,entry,base,mapping):
    blocks=target_blocks(n)
    # Re-render ticket labels from corrected native evidence, rather than
    # retaining the previous generator's incorrect 3001 default item lookup.
    steps=entry['record'].get('bunker_configuration',{}).get('steps',[])
    if steps and blocks.get('details'):
        details=soup(blocks['details'])
        option_heading=next((h for h in details.select('h4') if h.get_text(' ',strip=True)=='Bunker summon options'),None)
        if option_heading:
            rows=option_heading.find_next('table').select('tbody tr')
            assert len(rows)==len(steps)
            for row,step in zip(rows,steps):
                if step['cur']=='ticket':
                    cell=row.find_all('td')[2];correct=step.get('ticket_name','Premium Summon Ticket')
                    previous=cell.get_text(' ',strip=True)
                    if previous!=correct:
                        mapping.setdefault('target_data_corrections',[]).append({'field':'ticket payment label','previous':previous,'corrected':correct,
                            'evidence':'Native English item lookup; latest Bunker ConsumableIdPremiumTicket = 1002.'})
                        cell.clear();cell.append(correct)
            blocks['details']=''.join(str(e) for e in details.body.contents)
    heads=soup(base['body']).select('h3')
    order=[];dropped=[];heading_by_role={}
    for h in heads:
        title=h.get_text(' ',strip=True);role=source_role(title)
        if role and role not in order:
            order.append(role);heading_by_role[role]=h
        elif not role:dropped.append(title)
    order=[r for r in order if r!='notes']
    for role in ['duration','characters','howto','eventbox','details','exchange']:
        if role in blocks and role not in order:order.append(role)
    order.append('notes')
    reused=[]
    for s in soup(base['body']).stripped_strings:
        t=norm(s)
        if len(s)<320 and any(t.startswith(p) for p in ['for more information about rates please','you cannot have more than one character with the same name','illustrations shown in notices']):
            if s not in reused:reused.append(s)
    blocks['notes']+= ''.join('<p>'+common.esc(t)+'</p>' for t in reused)
    labels={'duration':'Duration','characters':'Characters & Weapons','details':'Summons Details','exchange':'About Shards / Exchange',
            'howto':'How to Play Event Quests','eventbox':'Event Summons','notes':'Notes'}
    disclosure=f'<section><p class="reconstruction-note"><b>Reconstructed notice.</b> Adapted from <a href="?informationId={base["id"]}">{common.esc(base["title"])}</a>. Original announcement text for this run has not been recovered. Dates and content below come from this entry’s own evidence.</p>'
    if n.get('thumb'):disclosure+=f'<img src="img/{n["thumb"]}.webp" alt="Original native banner for this summon" width="234">'
    elif not entry['record'].get('native_banner'):disclosure+='<p>The original banner artwork has not been recovered for this entry.</p>'
    disclosure+='<p>'+common.esc(entry['title'])+'</p></section>'
    rendered=[]
    for role in order:
        if not blocks.get(role):continue
        original=heading_by_role.get(role)
        attrs=''
        if original and original.get('class'):attrs=' class="'+common.esc(' '.join(original['class']))+'"'
        rendered.append(f'<section><h3{attrs}>{labels[role]}</h3>{blocks[role]}</section>')
    provenance='<details><summary>Reconstruction sources</summary>'+blocks['provenance']+'<p>Base notice '+str(base['id'])+': section order and generic Notes text only. Its dates, featured roster, artwork, stats, odds, guarantees and rewards were not copied.</p></details>'
    updated={**n,'title':entry['title'],
             'body':player_body(disclosure+''.join(rendered)+provenance,entry,mapping)}
    mapping['source_headings']=[h.get_text(' ',strip=True) for h in heads]
    mapping['adapted_section_order']=[r for r in order if blocks.get(r)]
    mapping['excluded_source_headings']=dropped
    mapping['generic_notes_reused']=reused
    return updated


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-pack',type=Path,default=ROOT/'inputs/bunker-notices-complete-generated.zip')
    p.add_argument('--audit-only',action='store_true')
    args=p.parse_args()
    z=zipfile.ZipFile(args.source_pack);pack=json.loads(z.read('notices.json'))
    originals={n['id']:{**n,'_text':plain(n['body'])} for n in pack['notices'] if n['id']<SYNTH}
    for n in originals.values():n['_norm']=norm(n['_text'])
    entries=target_records();mapping=[]
    for g,e in sorted(entries.items()):
        direct=EXACT.get(g) or CAMPAIGN.get(g)
        if direct:
            base_id=direct;strength='verified_same_run_notice';score=1000
            proof=validate_direct(g,e,originals[base_id])
        else:base_id,strength,score=choose_base(g,e,originals);proof={}
        base=originals[base_id]
        mapping.append({'gacha_id':g,'target_notice_id':SYNTH+g,'target_title':e['title'],
            'action':'direct_existing_notice' if direct else 'adapt_template',
            'base_notice_id':base_id,'base_title':base['title'],'base_body_sha256':common.sha(base['body'].encode()),
            'target_family':family(e['title'],e['record']),'base_family':family(base['title']),
            'target_payment':payment(e['title'],e['record']),'base_payment':payment(base['title']),
            'basis':strength,'similarity_score':score,'direct_evidence':proof})
        if g in CAMPAIGN:
            mapping[-1]['base_payment']='free (matched campaign section)'
    audit=ROOT/'artifacts/notice-template-audit';audit.mkdir(parents=True,exist_ok=True)
    mapfile=ROOT/'inputs/summon-notice-template-map.json'
    def save_mapping():
        mapfile.write_text(json.dumps({'version':1,'source_pack_sha256':common.sha(args.source_pack.read_bytes()),
            'target_evidence_sha256':common.sha((ROOT/'inputs/remaining-summon-notice-evidence.json').read_bytes()),'matches':mapping},ensure_ascii=False,indent=2),encoding='utf-8')
        keys=['gacha_id','target_title','action','base_notice_id','base_title','target_family','base_family','target_payment','base_payment','basis']
        with (audit/'base-notices.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(mapping)
    save_mapping()
    print('Matched:',len(mapping),'actions:',dict(Counter(r['action'] for r in mapping)),
          'basis:',dict(Counter(r['basis'] for r in mapping)),'unique bases:',len({r['base_notice_id'] for r in mapping}),flush=True)
    if args.audit_only:return
    rich=RichNotices(z.namelist(),entries)
    updated=copy.deepcopy(pack);byid={n['id']:n for n in updated['notices']};removed=set()
    for m in mapping:
        g=m['gacha_id'];nid=m['target_notice_id']
        assert updated['gacha'][str(g)]==nid and nid in byid
        if m['action']=='direct_existing_notice':
            updated['gacha'][str(g)]=m['base_notice_id'];removed.add(nid)
        else:
            base=originals[m['base_notice_id']]
            byid[nid]=rich.enhance(adapt(byid[nid],entries[g],base,m),entries[g],base,m)
    updated['notices']=[byid[n['id']] for n in updated['notices'] if n['id'] not in removed]
    original_byid={n['id']:n for n in pack['notices']}
    assert all(n==original_byid[n['id']] for n in updated['notices'] if n['id']<SYNTH)
    ids={n['id'] for n in updated['notices']}
    assert all(v in ids for v in updated['gacha'].values())
    assert len(ids)==len(updated['notices'])
    save_mapping()
    output=ROOT/'inputs/bunker-notices-template-based.zip'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as out:
        for name in z.namelist():
            info=zipfile.ZipInfo(name,(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            out.writestr(info,json.dumps(updated,ensure_ascii=False,separators=(',',':')).encode() if name=='notices.json' else z.read(name))
        out.writestr('templates/base-map.json',mapfile.read_bytes())
        out.writestr('templates/target-evidence.json',(ROOT/'inputs/remaining-summon-notice-evidence.json').read_bytes())
        for name,data in sorted(rich.images.items()):out.writestr(name,data)
        out.writestr('templates/rich-assets.json',json.dumps(rich.evidence,ensure_ascii=False,indent=2).encode())
        out.writestr('templates/event-bonus-evidence.json',json.dumps(rich.event_bonus_evidence,ensure_ascii=False,indent=2).encode())
        out.writestr('templates/runtime-facts.json',json.dumps(rich.fidelity.runtime,ensure_ascii=False,indent=2).encode())
        out.writestr('templates/native-promotion-terms.json',json.dumps(rich.fidelity.promotions,ensure_ascii=False,indent=2).encode())
    with zipfile.ZipFile(output) as out:
        assert out.testzip() is None
        assert all(out.read(n)==z.read(n) for n in z.namelist() if n!='notices.json')
    rows=list(csv.DictReader((ROOT/'artifacts/generated-summon-notice-audit/all-328.csv').open(encoding='utf-8-sig')))
    for row in rows:
        g=int(row['gacha_id'])
        m=next((m for m in mapping if m['gacha_id']==g),None)
        if not m:continue
        direct=m['action']=='direct_existing_notice';nid=m['base_notice_id'] if direct else m['target_notice_id']
        row.update(notice_id=nid,notice_title=byid[nid]['title'],status='direct_existing_notice' if direct else 'adapted_from_surviving_notice',
                   reason=f"Base {m['base_notice_id']}: {m['basis']}")
    with (audit/'all-328.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Reuse the exporter, then provide this candidate's own overview and base links.
    folder=ROOT/'artifacts/notice-template-review'
    generated.review(folder,updated,z,rich.images,rows)
    export_game_previews(folder,updated)
    table_rows=[(str(m['gacha_id']),common.esc(m['target_title']),m['action'],
                 f'<a href="notices/{updated["gacha"][str(m["gacha_id"])]}.html">Open notice</a>',
                 f'<a href="notices/{m["base_notice_id"]}.html">{m["base_notice_id"]}: {common.esc(m["base_title"])}</a>',m['basis']) for m in mapping]
    content='<h1>Notice bases and adaptations</h1><p class="count">125 surviving-notice links · 203 notices adapted from surviving originals</p><p>Each adapted page uses its base’s section structure and this target’s own run data. Seventeen earlier generated entries now link to surviving notices. All 328 entries from the original missing-link cohort remain covered.</p><input id="filter" aria-label="Filter matches" placeholder="Filter by summon, family or base…"><table><thead><tr><th>Summon</th><th>Target</th><th>Action</th><th>Page</th><th>Original base</th><th>Match</th></tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in table_rows)+'</tbody></table><script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'
    content=content.replace('</h1>','</h1><p><a href="all-notices.html">Browse all '+str(len(updated['notices']))+' notices</a></p>',1)
    (folder/'index.html').write_text(common.page('Notice bases and adaptations',content,''),encoding='utf-8')
    summary={'audited_synthetic_entries':len(mapping),'new_direct_links':len(removed),'adapted_pages':sum(m['action']=='adapt_template' for m in mapping),
             'unique_original_bases':len({m['base_notice_id'] for m in mapping}),'basis_counts':dict(Counter(m['basis'] for m in mapping)),
             'notices':len(updated['notices']),'gacha_keys':len(updated['gacha']),
             'all_original_328_have_pages':all(updated['gacha'].get(str(r['gacha_id'])) in ids for r in load(ROOT/'inputs/summon-notice-repair-evidence.json')['baseline']),
             'sha256':common.sha(output.read_bytes()),'bytes':output.stat().st_size,'original_951_records_and_all_assets_preserved':True,
             'original_dynamic_facts_copied':False,'deployment':'Separate candidate only; installed APK, default packs and previous candidates unchanged.'}
    summary['player_ui_cleanup_applied']=True
    enriched=[m['rich_content'] for m in mapping if 'rich_content' in m]
    summary['native_title_graphics']=sum(bool(m['title_graphic']) for m in enriched)
    summary['pages_with_native_promotion_panels']=sum(bool(m['promotion_panels']) for m in enriched)
    summary['native_promotion_panels']=sum(len(m['promotion_panels']) for m in enriched)
    summary['new_native_image_members']=len(rich.images)
    summary['pages_with_detailed_phase_facts']=sum(bool(m['configured_phase_facts']) for m in enriched)
    summary['pages_with_native_event_bonuses']=sum(bool(m['native_event_bonus_rows'] or m['native_event_costume_bonus_rows']) for m in enriched)
    summary['native_event_bonus_rows']=sum(len(m['native_event_bonus_rows']) for m in enriched)
    summary['pages_with_native_costume_bonuses']=sum(bool(m['native_event_costume_bonus_rows']) for m in enriched)
    summary['native_event_costume_bonus_rows']=sum(len(m['native_event_costume_bonus_rows']) for m in enriched)
    summary['phase_fact_sources']=dict(Counter(m['fidelity']['phase_source'] for m in mapping if 'fidelity' in m))
    summary['pages_with_reconstructed_text_titles']=sum(bool(m.get('fidelity',{}).get('reconstructed_text_title_panel')) for m in mapping)
    summary['native_promotion_panels_reviewed']=rich.fidelity.promotions.get('panels_checked',0)
    summary['pages_with_native_promotion_terms']=sum(bool(m.get('fidelity',{}).get('native_promotion_sources')) for m in mapping)
    summary['rich_image_provenance_records']=len(rich.evidence)
    framed={p['member'] for p in rich.evidence if p.get('composite_key')}
    summary['framed_native_thumbnail_members']=len(framed)
    summary['pages_with_framed_native_thumbnails']=sum(any(member in n['body'] for member in framed) for n in updated['notices'] if n['id']>=SYNTH)
    summary['player_ui_audit_blocks_removed']=sum(len(m.get('player_ui_removed_html',[])) for m in mapping)
    (audit/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
