"""Audit every reconstructed page against applicable source facts and UI rules."""
import argparse,collections,hashlib,json,re,sys,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build/notice-audit/python'))
from bs4 import BeautifulSoup


def audit(pack,mappings,members,before=None,promotions=None):
    by={n['id']:n for n in pack['notices']};rows=[]
    for m in mappings:
        if m['action']!='adapt_template':continue
        n=by[m['target_notice_id']];d=BeautifulSoup(n['body'],'html5lib');text=d.get_text(' ',strip=True)
        errors=[];rich=m['rich_content'];f=m.get('fidelity',{})
        heads=[h.get_text(' ',strip=True) for h in d.select('h3')]
        if not d.select_one('section.notice-intro'):errors.append('Missing opening presentation section')
        if not heads or heads[-1]!='Notes':errors.append('Notes must finish the page')
        if len(d.select('.attention_content li'))<3:errors.append('Missing useful Notes')
        if not d.select_one(f'a[href="/web/en/gacha-details?gachaId={m["gacha_id"]}"]'):errors.append('Missing correct live Details / Rates link')
        if n['title']!=m['target_title']:errors.append('Title differs from target identity')
        if m['target_title'] not in text:errors.append('Target name missing from opening')
        if not rich['configured_phase_facts'] and f.get('phase_source')!='withheld_payment_conflict':errors.append('No usable draw options')
        if f.get('phase_source')=='withheld_payment_conflict' and rich['configured_phase_facts']:errors.append('Disputed phase pricing published')
        for image in d.select('img'):
            if image.get('src') not in members:errors.append('Missing image: '+str(image.get('src')))
        if d.select('script,iframe,style'):errors.append('Unexpected executable or embedded content')
        for phrase in ['Details not established','Page sources and limitations','This table does not establish','This is not a verified summon end time','These dates come from native home-banner records','Exchange options recorded in original-run snapshot']:
            if phrase in text:errors.append('Research boilerplate: '+phrase)
        if re.search(r'\b(?:2099|2100)\b',text):errors.append('Far-future placeholder shown to player')
        if re.search(r'\b(?:Costume|Weapon|Material|Item) \d{4,}\b',text):errors.append('Unresolved native item name')
        if not d.select_one('.info-largeimage img,.notice-title-panel'):errors.append('No native or reconstructed title presentation')
        sources=f.get('native_promotion_sources',[])
        advertised=(promotions or {}).get('assets',{}).get(sources[0].split('/')[3],{}) if sources else {}
        if f.get('phase_source')!='withheld_payment_conflict':
            for key,fact in advertised.get('steps',{}).items():
                matching=[s for s in rich['configured_phase_facts'] if s.get('step',0)==int(key)]
                for step in matching:
                    if step.get('step') or step['draws']>=10:
                        if 'price' in fact and (step['price']!=fact['price'] or step['cur']!=fact['cur']):errors.append('Price contradicts native promotional panel')
                        if 'bonus_display' in fact and step.get('bonus_display')!=fact['bonus_display']:errors.append('Bonus contradicts native promotional panel')
                    if 'rate' in fact and step.get('rate')!=fact['rate']:errors.append('Rate multiplier omitted from native terms')
        old=BeautifulSoup(before.get(n['id'],{}).get('body',''),'html5lib') if before else None
        rows.append({'gacha_id':m['gacha_id'],'notice_id':n['id'],'title':m['target_title'],
                     'family':m['target_family'],'base_notice_id':m['base_notice_id'],
                     'status':'reviewed_payment_conflict' if f.get('phase_source')=='withheld_payment_conflict' and not errors else 'needs_fix' if errors else 'pass',
                     'errors':errors,'phase_source':f.get('phase_source'),'draw_options':len(rich['configured_phase_facts']),
                     'native_title':bool(rich['title_graphic']),'native_promotion_panels':len(rich['promotion_panels']),
                     'text_chars':len(text),'text_chars_before':len(old.get_text(' ',strip=True)) if old else None,
                     'images':len(d.select('img')),'images_before':len(old.select('img')) if old else None,
                     'event_weapon_bonus_rows':len(rich['native_event_bonus_rows']),
                     'event_costume_stat_rows':len(rich.get('native_event_costume_bonus_rows',[])),
                     'full_box_reward_rows':f.get('full_box_reward_rows',0),'ticket_descriptions':f.get('ticket_descriptions',[])})
    return {'audited_pages':len(rows),'status_counts':dict(collections.Counter(r['status'] for r in rows)),
            'phase_sources':dict(collections.Counter(r['phase_source'] for r in rows)),
            'reviewed_exception_ids':[r['gacha_id'] for r in rows if r['status']=='reviewed_payment_conflict'],
            'unresolved_original_material':['Exact historical per-item rates and complete original pools','Native title / banner art for 70, 85, 160; text title panels used','Original promotional panels absent for 23 entries','Original historical phase terms where the displayed source is current runtime configuration','Any stat, cooldown, duplicate or awakening effects whose original-run relations are not established'],
            'rows':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pack',type=Path,default=ROOT/'inputs/bunker-notices-template-based.zip');args=p.parse_args()
    folder=ROOT/'artifacts/notice-fidelity-audit';folder.mkdir(exist_ok=True)
    before_path=folder/'before-notices.json';before={n['id']:n for n in json.loads(before_path.read_text(encoding='utf-8'))['notices']} if before_path.exists() else None
    with zipfile.ZipFile(args.pack) as z:
        pack=json.loads(z.read('notices.json'));mapping=json.loads(z.read('templates/base-map.json'))['matches']
        promotions=json.loads(z.read('templates/native-promotion-terms.json'))
        report=audit(pack,mapping,set(z.namelist()),before,promotions)
    report['pack_sha256']=hashlib.sha256(args.pack.read_bytes()).hexdigest()
    (folder/'fidelity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    import build_summon_notice_repair_pack as common
    content='<h1>Reconstructed notice fidelity audit</h1><p>'+str(report['audited_pages'])+' reconstructed pages. '+common.esc(str(report['status_counts']))+'</p><p>Current implemented draw options are used where historical phase rules were absent. Original rate tables are not invented; every page links to its live Details / Rates page. One payment conflict remains withheld.</p><p><a href="all-notices.html">Browse all notices</a></p><input id="filter" placeholder="Search summon, family, status or source"><table><thead><tr><th>Summon</th><th>Notice</th><th>Status</th><th>Price source</th><th>Text before → after</th><th>Images before → after</th><th>Issues</th></tr></thead><tbody>'
    for r in report['rows']:
        cells=[str(r['gacha_id']),f'<a href="notices/{r["notice_id"]}.html">{common.esc(r["title"])}</a>',r['status'],str(r['phase_source']),str(r['text_chars_before'])+' → '+str(r['text_chars']),str(r['images_before'])+' → '+str(r['images']),common.esc('; '.join(r['errors']))]
        content+='<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>'
    content+='</tbody></table><script>document.querySelector("#filter").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))})</script>'
    (ROOT/'artifacts/notice-template-review/fidelity.html').write_text(common.page('Notice fidelity audit',content,''),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['rows','unresolved_original_material']},indent=2))
    for row in report['rows']:
        if row['errors']:print(row['gacha_id'],row['errors'])
    if any(r['errors'] for r in report['rows']):raise SystemExit(1)


if __name__=='__main__':main()
