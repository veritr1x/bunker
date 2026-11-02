"""Consistent, useful notice sections with per-field evidence kept externally."""
import copy,html,json,re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]

def esc(s):return html.escape(str(s),quote=True)
def soup(s):return BeautifulSoup(s,'html5lib')


class NoticeFidelity:
    def __init__(self,library):
        self.lib=library
        path=ROOT/'inputs/summon-notice-runtime-facts.json'
        self.runtime=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'entries':{}}
        path=ROOT/'inputs/summon-notice-native-promotion-terms.json'
        self.promotions=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'assets':{}}
        pair=Path('C:/GitRepos/bunker-backup-before-replace/upstream/lunar-tear/server/internal/masterdata/costume_weapon_pairings.go')
        self.pairs={int(c):int(w) for c,w in re.findall(r'^\s*(\d+):\s*(\d+)',pair.read_text(),re.M)}
        self.named_icons={}

    def item(self,ident,material=False):
        record=self.lib.master['Material' if material else 'ConsumableItem'].get(ident)
        if not record:return None,'',''
        asset=f"{record['AssetCategoryId']}{record['AssetVariationId']:03d}"
        prefix='material' if material else 'consumable_item'
        return self.lib.item_icon(ident,material),self.lib.texts.get(f'{prefix}.name.{asset}',''),self.lib.texts.get(f'{prefix}.description.{asset}','')

    def prepare(self,entry,mapping):
        entry=copy.deepcopy(entry);r=entry['record'];g=r['gacha_id']
        cfg=r.setdefault('bunker_configuration',{'steps':[]})
        evidence=mapping.setdefault('fidelity',{})
        evidence['phase_source']='existing_target_configuration' if cfg.get('steps') else 'not_recovered'
        runtime=self.runtime['entries'].get(str(g),{})
        if not cfg.get('steps') and not r.get('configuration_conflicts') and runtime.get('cost_rows'):
            phases=[];rpc=runtime.get('rpc') or {};wire=rpc.get('phases',[])
            # Step-up RPC responses contain only the current step. The Details
            # endpoint exposes all steps, so use its complete table in that case.
            if len(wire)!=len(runtime['cost_rows']):wire=[]
            for i,row in enumerate(runtime['cost_rows']):
                p=wire[i] if wire else {};text=row['price_text']
                if p:
                    cur={1:'ticket',2:'gems',3:'paid'}.get(p.get('priceType'))
                    if p.get('price',0)==0:cur='free'
                    price=p.get('price',0)
                else:
                    cur='free' if text=='Free' else 'paid' if text.endswith('paid gems') else 'gems' if text.endswith(' gems') else 'ticket' if 'Summon Ticket' in text else None
                    price=int(re.match(r'\d+',text)[0]) if cur!='free' else 0
                assert cur,(g,text)
                step={'cur':cur,'price':price,'draws':p.get('draws',row['draws'])}
                if row['step']:step['step']=row['step']
                limit=p.get('limit',row['limit'])
                if 0<limit<999:step['limit']=limit
                if rpc.get('resetType')==2:step['daily']=True
                minimum=p.get('fixed',{}).get('rarity',row['fixed_rarity']);count=p.get('fixed',{}).get('count',row['fixed_count'])
                if minimum and count:step.update(guar=f'r{minimum//10}w',guaranteed_count=count)
                if cur=='ticket':
                    # The HTTP-only premium counterpart (159) uses the native
                    # buildPremiumBasicPricePhases ticket 1002; RPC retains ids.
                    tid=p.get('priceId',1002);step.update(ticket=tid,ticket_name=self.item(tid)[1] or 'Summon Ticket')
                if p.get('bonuses'):step['items']=[{'t':b['type'],'id':b['id'],'n':b['count']} for b in p['bonuses']]
                phases.append(step)
            cfg['steps']=phases;evidence['phase_source']='current_runtime_catalog'
            evidence['runtime_endpoint']=runtime['endpoint'];evidence['runtime_html_sha256']=runtime['html_sha256']
        if r.get('configuration_conflicts'):evidence['phase_source']='withheld_payment_conflict'
        advertised=copy.deepcopy(self.promotions['assets'].get(r['asset'],{}))
        if advertised:
            evidence['native_promotion_sources']=[p['bundle'] for p in advertised['sources']]
            r['_native_promotions']=advertised
            if advertised.get('display_title'):
                evidence['previous_catalog_title']=entry['title'];evidence['title_correction_basis']=advertised['title_basis']
                entry['title']=advertised['display_title'];mapping['target_title']=entry['title']
                mapping['target_family']='bonus'
            if advertised.get('shared_exchange_from') and not r.get('exchange'):
                parent=self.lib.entries[advertised['shared_exchange_from']]['record']
                assert r['baseline']['start']==parent['baseline']['start']
                r['exchange']=copy.deepcopy(parent['exchange']);r['exchange']['association']='native_panel_explicit_shared_currency'
                evidence['shared_exchange_basis']=advertised['shared_exchange_basis']
                parent_bonus=self.lib.event_bonuses.get(advertised['shared_exchange_from'])
                windows=[b['row'][6:8] for b in r.get('native_banner_periods',[])]
                if parent_bonus and windows:
                    derived=copy.deepcopy(parent_bonus);derived['gacha_id']=g;derived['windows']=windows
                    derived['events']=[e for e in derived['events'] if any(max(a,e['chapter_row'][8])<min(b,e['chapter_row'][9]) for a,b in windows)]
                    derived['derivation']='Same native run start, explicitly shared panel currency and identical original-run exchange roster; only overlapping event chapters retained.'
                    for e in derived['events']:
                        for bonus in e.get('weapon_bonuses',[])+e.get('costume_bonuses',[]):
                            bonus['start']=max(bonus['start'],min(a for a,b in windows));bonus['end']=min(bonus['end'],max(b for a,b in windows))
                    self.lib.event_bonuses[g]=derived
                    self.lib.event_bonus_evidence['entries']=[derived if e['gacha_id']==g else e for e in self.lib.event_bonus_evidence['entries']]
            base_source=evidence['phase_source']
            ordinary=advertised.get('steps',{}).get('0',{})
            if ordinary.get('only_advertised_option') and not r.get('configuration_conflicts'):
                old=next((s for s in cfg.get('steps',[]) if s['draws']==ordinary.get('draws',10)),{})
                cfg['steps']=[{**old,'draws':ordinary.get('draws',10),'cur':ordinary['cur'],'price':ordinary['price']}]
                evidence['phase_source']='native_promotion_panel'
            for step in cfg.get('steps',[]):
                fact=advertised.get('steps',{}).get(str(step.get('step',0)),{})
                if not fact:continue
                if (base_source=='current_runtime_catalog' or cfg.get('source')=='banner row; usual prices') and step.get('guar','').startswith('r4') and 'guar' not in fact:
                    step['guar']='r3w' if step['draws']>=10 else ''
                for key in ['rate','guar','guarantee_slot']:
                    if key in fact:step[key]=fact[key]
                if step.get('step') or step['draws']>=10:
                    for key in ['price','cur','limit','bonus_display']:
                        if key in fact:step[key]=copy.deepcopy(fact[key])
                    if 'price' in fact:evidence['phase_source']='native_promotion_panel'
            r['_native_featured_weapons']=[]
            r['_native_illustrated_costumes']=[]
            for name in advertised.get('illustrated_costume_names',[]):
                matches=[ident for ident in self.lib.master['Costume'] if (self.lib.costume(ident) or {}).get('costume')==name]
                assert len(matches)==1,(g,name,'illustrated costume identity ambiguous')
                r['_native_illustrated_costumes']+=matches
            for name in advertised.get('featured_weapon_names',[]):
                key=name.replace('’',"'")
                matches=[wid for wid,w in self.lib.master['Weapon'].items()
                         if self.lib.texts.get(f"weapon.name.wp{w['WeaponType']:03d}{w['AssetVariationId']:03d}.1",'').replace('’',"'")==key]
                assert matches,(g,name,'native panel weapon cannot be resolved')
                paired=[w for w in matches if w in self.pairs.values()]
                r['_native_featured_weapons'].append(min(paired or matches))
        r['_phase_source']=evidence['phase_source']
        return entry

    def named_item(self,name):
        if name in self.named_icons:return self.named_icons[name]
        for material,kind in [(True,'Material'),(False,'ConsumableItem')]:
            for ident in self.lib.master[kind]:
                r=self.lib.master[kind][ident];asset=f"{r['AssetCategoryId']}{r['AssetVariationId']:03d}"
                prefix='material' if material else 'consumable_item'
                if self.lib.texts.get(f'{prefix}.name.{asset}')==name:
                    self.named_icons[name]=self.item(ident,material)[0];return self.named_icons[name]
        self.named_icons[name]=None
        return None

    def card(self,ident):
        c=self.lib.costume(ident)
        if c and ident in self.pairs:
            c['weapon_id']=self.pairs[ident];c['weapon']=self.lib.weapon(c['weapon_id'])[1]
        return c

    def title_panel(self,title):
        return '<div class="notice-title-panel"><p>SUMMONS</p><h2>'+esc(title)+'</h2></div>'

    def finish(self,doc,entry,mapping):
        r=entry['record'];g=r['gacha_id'];steps=r.get('bunker_configuration',{}).get('steps',[])
        evidence=mapping['fidelity']
        def find(heading):return next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)==heading),None)
        def add(content,before=None):
            new=soup(content).find('section')
            anchor=before or find('Notes')
            if anchor:anchor.insert_before(new)
            else:doc.body.append(new)
            return new
        advertised=r.get('_native_promotions',{});features=list(advertised.get('features',[]))
        if advertised.get('no_featured_rates'):features.append('Individual characters and weapons do not have featured appearance rates in this summons.')
        if advertised.get('loop_limit') is not None:
            limit=advertised['loop_limit'];features.append('The full step sequence can be performed '+('any number of times.' if limit==0 else 'once.' if limit==1 else f'up to {limit} times.'))
        if r['asset'].startswith('limited_100') and (r.get('exchange') or r.get('costumes')):
            chars=list(dict.fromkeys(c['character'] for c in r.get('exchange',{}).get('lineup',r.get('costumes',[]))))
            if chars:features.append('When a ★★★★ character weapon appears, one of these characters is guaranteed: '+', '.join(chars)+'.')
        # Publish known native terms even when an unrelated payment conflict
        # prevents printing the cost table (405).
        if r.get('configuration_conflicts'):
            native=advertised.get('steps',{}).get('0',{})
            if native.get('rate'):features.append('★★★★ appearance-rate multiplier ×'+str(native['rate'])+'.')
            for b in native.get('bonus_display',[]):features.append(b['name']+' ×'+str(b['quantity'])+' as a summon bonus.')
        if features:
            add('<section><h3>Summon Features</h3><ul>'+''.join('<li>'+esc(f)+'</li>' for f in features)+'</ul></section>',find('Summons Details'))
            evidence['native_promotion_features']=features
        # A configured original-run window was previously discarded, even for
        # the New Year free summons whose two opportunities have separate ends.
        date_section=find('Start Date')
        added=r.get('bunker_configuration',{}).get('raw_added_rule',{})
        start,end=added.get('start',0),added.get('end',0)
        if date_section and 1600000000000<start<end<1750000000000:
            import build_summon_notice_repair_pack as common
            date_section.clear();date_section.extend(list(soup('<h3>Estimated Period</h3><div class="holding-period">'+esc(common.date(start))+' – '+esc(common.date(end))+'</div>').body.contents))
            evidence['period_source']='target_added_rule_original_run_window'
        # Explain each summon family using that target's actual usable options.
        usable=steps and not r.get('configuration_conflicts')
        if usable and {s['cur'] for s in steps}=={'free'}:
            s=steps[0];count=s['draws'];limit=s.get('limit');daily=s.get('daily')
            text=f'This summons lets you perform {count} summons without spending gems or summon tickets.'
            if limit:text+=' It is available '+('once' if limit==1 else str(limit)+' times')+(' per day.' if daily else ' during this opportunity.')
            text+=' Open Summons, select '+entry['title']+f', then choose the {count}x summon option.'
            add('<section><h3>How to Use the Free Summons</h3><p>'+esc(text)+'</p></section>',find('Summons Details'))
        ticket_ids=list(dict.fromkeys(s.get('ticket',1002) for s in steps if s['cur']=='ticket')) if usable else []
        if ticket_ids:
            content='<section><h3>About Summon Tickets</h3>'
            for ident in ticket_ids:
                icon,name,description=self.item(ident)
                content+='<h4>'+esc(name or 'Summon Ticket')+'</h4><p>'+self.lib.img(icon,'coin_icon','32px',name)+esc(description or 'Use this ticket from the matching summons on the Summons screen.')+'</p>'
                matching=[s for s in steps if s.get('ticket',1002)==ident and s['cur']=='ticket']
                content+='<p>'+esc(' / '.join(f"{s['price']} ticket"+('s' if s['price']!=1 else '')+f" for {s['draws']} summon"+('s' if s['draws']!=1 else '') for s in matching))+'.</p>'
            content+='</section>';add(content,find('Summons Details'));evidence['ticket_descriptions']=ticket_ids
        # Full configured event box rewards were present in the data but omitted
        # from the earlier main-prize-only summary. These are Bunker's stocks.
        if r.get('event'):
            event=r['event'];content='<section><h3>Event Summons Rewards</h3><p>Collect all target prizes in a level to advance to the next level. The final level can be replenished.</p><details><summary>View all rewards by level</summary>'
            count=0
            for level,box in enumerate(event['configuration']['levels'],1):
                rows=[]
                for item in box['items']:
                    kind=item['t'];ident=item['id'];icon=None;name=''
                    if kind in [5,6]:icon,name,_=self.item(ident,kind==5)
                    elif kind==2:icon,name,_=self.lib.weapon(ident)
                    elif kind==12:name='Gems'
                    elif kind==11:name='Paid Gems'
                    assert name,(g,kind,ident,'unknown reward name')
                    rows.append('<tr><td>'+self.lib.img(icon,width='24px',alt=name)+esc(name)+(' <strong>(Target)</strong>' if item.get('target') else '')+'</td><td>'+str(item['n'])+'</td><td>'+str(item['stock'])+'</td></tr>');count+=1
                content+='<h4>Level '+str(level)+'</h4><div class="information_table"><table><thead><tr><th>Reward</th><th>Quantity</th><th>Stock</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
            content+='</details></section>';add(content);evidence['full_box_reward_rows']=count
        # Always finish with the same useful notes and a working path to live
        # rates. Do not freeze configurable Pod Program rates into a notice.
        notes=find('Notes')
        if notes is None:notes=add('<section><h3>Notes</h3></section>')
        text=notes.get_text(' ',strip=True)
        useful=['Illustrations shown in notices, etc. may differ from those in-game.',
                'You cannot have more than one character with the same name in the same deck.',
                'For more information about rates, please check the Rates button on the summons page.']
        existing=[li.get_text(' ',strip=True) for li in notes.select('li')]+[p.get_text(' ',strip=True) for p in notes.select('p')]
        for n in useful:
            if n not in existing:existing.append(n)
        notes.clear();notes.extend(list(soup('<h3>Notes</h3><div class="attention_content"><ul>'+''.join('<li>'+esc(n)+'</li>' for n in existing if n)+'</ul></div>').body.contents))
        notes.append(soup(f'<a class="other-link-btn" href="/web/en/gacha-details?gachaId={g}">Summon Details and Rates</a>').find('a'))
        notes.extract();doc.body.append(notes)
        # Keep the practical reading order consistent, even when the chosen
        # base's announcement covered an exchange before its summon details.
        def rank(section):
            if 'notice-intro' in section.get('class',[]):return 0
            h=section.find('h3');title=h.get_text(' ',strip=True) if h else ''
            if title in ['Duration','Banner Period','Banner Periods','Estimated Period','Event Period','Start Date']:return 10
            if title in ['Featured Characters & Weapons','Summons Information','Exchange Lineup']:return 20
            if title=='How to Play Event Quests':return 25
            if title=='Summon Features':return 30
            if title in ['How to Use the Free Summons','About Summon Tickets']:return 35
            if title=='Summons Details':return 40
            if title=='Event Summons':return 45
            if title=='Event Summons Rewards':return 50
            if title.startswith('About '):return 60
            if title=='Event Quest Bonuses':return 70
            if title=='Notes':return 90
            return 55
        sections=doc.body.find_all('section',recursive=False)
        for section in sorted(sections,key=rank):section.extract();doc.body.append(section)
        evidence['live_rates_link']=True
        evidence['complete_historical_rates_claimed']=False
        return doc
