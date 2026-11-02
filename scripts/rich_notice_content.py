"""Notice presentation from native promotion art and target-specific summon facts.

Never uses the template's character art, bonus quantities, rates or event effects.
"""
import hashlib,html,io,json,re,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.build/notice-audit/python'))
from bs4 import BeautifulSoup
from PIL import Image

BASE=Path('C:/GitRepos/bunker-backup-before-replace/inputs')
STAR='img/c_c0591a6ed6321ab9.webp'
GEM='img/c_0a0f76549d1cbb9f.webp'
def esc(s):return html.escape(str(s),quote=True)
def soup(s):return BeautifulSoup(s,'html5lib')
def body(s):return ''.join(str(e) for e in s.body.contents)


class RichNotices:
    def __init__(self,source_members,entries):
        self.source_members=set(source_members);self.entries=entries
        self.images={};self.evidence=[];self.bundle_cache={};self.image_cache={}
        self.prior_sources={}
        import zipfile
        previous=ROOT/'inputs/bunker-notices-template-based.zip'
        if previous.exists():
            with zipfile.ZipFile(previous) as old:
                if 'templates/rich-assets.json' in old.namelist():
                    for p in json.loads(old.read('templates/rich-assets.json')):
                        key=p.get('composite_key') or p.get('source_bundle') or p.get('source_png')
                        self.prior_sources[key]=p
        self.asset_root=BASE/'android-dump/revisions/0/assetbundle'
        self.master={}
        for name,key in [('Costume','CostumeId'),('Weapon','WeaponId'),('ConsumableItem','ConsumableItemId'),('Material','MaterialId'),('Character','CharacterId')]:
            self.master[name]={r[key]:r for r in json.loads((BASE/'master'/f'EntityM{name}Table.json').read_text(encoding='utf-8'))}
        self.assets={}
        for folder in ['asset-images','item-images']:
            for r in json.loads((ROOT/'inputs'/folder/'manifest.json').read_text(encoding='utf-8'))['images']:
                self.assets[(r['family'],r['asset'],r['variant'])]=(ROOT/'inputs'/folder/r['file'],r)
        self.rules=json.loads((ROOT/'.build/notice-audit/rerun-reconstruction/source-main/overlays/server/internal/masterdata/summon_rules.json').read_text())
        bonus_file=ROOT/'inputs/summon-notice-event-bonuses.json'
        self.event_bonus_evidence=json.loads(bonus_file.read_text(encoding='utf-8')) if bonus_file.exists() else {'entries':[]}
        self.event_bonuses={r['gacha_id']:r for r in self.event_bonus_evidence['entries']}
        self.costume_bonus_facts={}
        import sqlite3
        with sqlite3.connect('file:'+(BASE/'archive.db').as_posix()+'?mode=ro',uri=True) as db:
            self.texts=dict(db.execute("SELECT key,value FROM text WHERE key LIKE 'costume.name.%' OR key LIKE 'character.name.%' OR key LIKE 'weapon.name.%' OR key LIKE 'consumable_item.%' OR key LIKE 'material.%'"))
        from notice_fidelity import NoticeFidelity
        self.fidelity=NoticeFidelity(self)
        from native_notice_icons import NativeNoticeIcons
        self.notice_icons=NativeNoticeIcons(self)

    def reuse_image(self,key,source_hash):
        p=self.prior_sources.get(key)
        if not p or source_hash not in [p.get('source_bundle_sha256'),p.get('source_png_sha256'),p.get('source_composition_sha256')]:return None
        path=ROOT/'artifacts/notice-template-review'/p['member']
        if not path.exists():return None
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=Path(p['member']).stem:return None
        im=Image.open(io.BytesIO(raw)).convert('RGBA')
        assert hashlib.sha256(im.tobytes()).hexdigest()==p['rgba_sha256']
        if p['member'] not in self.source_members:self.images[p['member']]=raw
        self.evidence.append(p)
        return p['member']

    def add_image(self,im,source):
        im=im.convert('RGBA');buf=io.BytesIO();im.save(buf,format='WEBP',lossless=True,exact=True)
        encoded=buf.getvalue();assert Image.open(io.BytesIO(encoded)).convert('RGBA').tobytes()==im.tobytes()
        key=hashlib.sha256(encoded).hexdigest();member=f'img/{key}.webp'
        if member not in self.source_members:self.images[member]=encoded
        self.evidence.append({**source,'member':member,'width':im.width,'height':im.height,
                              'rgba_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'lossless_roundtrip_verified':True})
        return member

    def bundle_image(self,relative):
        if relative in self.bundle_cache:return self.bundle_cache[relative]
        path=self.asset_root/relative
        if not path.is_file():self.bundle_cache[relative]=None;return None
        raw=path.read_bytes();cached=self.reuse_image(relative,hashlib.sha256(raw).hexdigest())
        if cached:self.bundle_cache[relative]=cached;return cached
        import UnityPy
        from export_asset_images import unmask
        env=UnityPy.load(unmask(raw,relative))
        sprites=[o for o in env.objects if o.type.name=='Sprite']
        objects=sprites or [o for o in env.objects if o.type.name=='Texture2D']
        if not objects:self.bundle_cache[relative]=None;return None
        choices=[(o,o.read().image) for o in objects];obj,im=max(choices,key=lambda p:p[1].width*p[1].height)
        member=self.add_image(im,{'source_bundle':relative,'source_bundle_sha256':hashlib.sha256(raw).hexdigest(),'object_id':obj.path_id})
        self.bundle_cache[relative]=member;return member

    def icon(self,family,asset):
        k=(family,asset)
        if k in self.image_cache:return self.image_cache[k]
        found=next((self.assets[(family,asset,v)] for v in ['standard','icon','gacha','large'] if (family,asset,v) in self.assets),None)
        if not found:self.image_cache[k]=None;return None
        path,record=found;raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256']
        cached=self.reuse_image(str(path),record['sha256'])
        if cached:self.image_cache[k]=cached;return cached
        member=self.add_image(Image.open(io.BytesIO(raw)),{'source_png':str(path),'source_png_sha256':record['sha256'],'asset':asset})
        self.image_cache[k]=member;return member

    def weapon(self,w):
        r=self.master['Weapon'].get(w)
        if not r:return None,'',0
        asset=f"wp{r['WeaponType']:03d}{r['AssetVariationId']:03d}"
        return self.notice_icons.icon('weapons',w),self.texts.get(f'weapon.name.{asset}.1',''),r['RarityType']//10

    def costume_icon(self,c):
        return self.notice_icons.icon('costumes',c)

    def costume(self,c):
        r=self.master['Costume'].get(c)
        if not r or r['CharacterId'] not in self.master['Character']:return None
        asset=f"ch{r['ActorSkeletonId']:03d}{r['AssetVariationId']:03d}";ch=self.master['Character'][r['CharacterId']]
        return {'costume_id':c,'asset':asset,'costume':self.texts.get('costume.name.'+asset,''),
                'character':self.texts.get('character.name.'+str(ch['NameCharacterTextId']),''),
                'rarity':r['RarityType']//10}

    def item_icon(self,ident,material=False):
        kind='Material' if material else 'ConsumableItem';r=self.master[kind].get(ident)
        if not r:return None
        prefix='material' if material else 'consumable'
        return self.icon('materials' if material else 'consumables',f"{prefix}{r['AssetCategoryId']}{r['AssetVariationId']:03d}")

    def stars(self,count):
        if STAR in self.source_members:return ''.join(f'<img class="star" src="{STAR}" alt="★">' for _ in range(count))
        return '★'*count

    def img(self,member,cls='weapon_icon',width='6%',alt=''):
        return f'<img class="{cls}" src="{member}" width="{width}" alt="{esc(alt)}"> ' if member else ''

    def exchange(self,r):
        if r.get('exchange'):return r['exchange']
        return {'shard_id':r['medal']['ConsumableItemId'],'shard_name':r['shard_name'],
                'lineup':[{**c,'price':r['history']['historical_exchange_prices'][0]} for c in r['costumes']],
                'conversion':r['medal']['AutoConvertDatetime'],'other_exchange_weapons':[]}

    def featured(self,r):
        rule=self.rules['rules'].get(str(r['gacha_id']),{})
        pair=r.get('bunker_configuration',{}).get('raw_added_rule',{}).get('pair')
        if not rule.get('featured') and pair:rule=self.rules['rules'].get(str(pair),{})
        featured=rule.get('featured',{});allowed={c['costume_id'] for c in self.exchange(r)['lineup']} if r.get('exchange') or r.get('medal') else set()
        ids=[c for c in featured.get('c',[]) if not allowed or c in allowed]
        return ids,featured.get('w',[])

    @staticmethod
    def guarantee(s):
        code=s.get('guar','').lower()
        if not code or code=='none':return ''
        count=s.get('guaranteed_count',1);quantity='one' if count==1 else str(count)
        element=code.split(':',1)[1].title()+' ' if ':' in code else ''
        character='character ' if code.startswith('r4c') or code.startswith('set') else ''
        rarity='★★★ or higher' if code.startswith('r3') else '★★★★'
        if s.get('guarantee_slot'):return f'The {s["guarantee_slot"]}th summon guarantees a {rarity} {element}{character}weapon.'
        return f'At least {quantity} {rarity} {element}{character}weapon'+(' is' if count==1 else 's are')+' guaranteed.'

    def phase_details(self,r):
        steps=r.get('bunker_configuration',{}).get('steps',[])
        if not steps or r.get('configuration_conflicts'):return '',[]
        x=self.exchange(r) if r.get('exchange') or r.get('medal') else None
        shard_icon=self.item_icon(x['shard_id']) if x else None
        rows=[];notes=[];facts=[]
        for i,s in enumerate(steps,1):
            cur={'paid':'paid gems','gems':'gems','free':'Free','ticket':s.get('ticket_name','Summon ticket')}[s['cur']]
            price='Free' if s['cur']=='free' else f"{s.get('price',0):,} {esc(cur)}"
            if s['cur'] in ['paid','gems'] and GEM in self.source_members:price=self.img(GEM,'gem_icon','16px')+price
            elif s['cur']=='ticket':price=self.img(self.item_icon(s.get('ticket',1002)),'gem_icon','16px')+price
            other=[]
            if x:other.append(self.img(shard_icon,'gem_icon','16px')+esc(x['shard_name'])+f" ×{s['draws']}")
            guarantee=self.guarantee(s)
            if guarantee:other.append('<span class="text-red">'+guarantee+'</span>')
            if s.get('feat4'):other.append('★★★★ character weapons are selected from the featured characters.')
            if s.get('rate'):other.append(f'<span class="text-red">★★★★ appearance-rate multiplier ×{s["rate"]:g}</span>')
            if s.get('bonus_display'):
                for bonus in s['bonus_display']:
                    other.append(self.img(self.fidelity.named_item(bonus['name']),'gem_icon','16px')+esc(bonus['name'])+f' ×{bonus["quantity"]}')
            elif s.get('items'):
                for item in s['items']:
                    icon,name,_=self.fidelity.item(item['id'],item['t']==5) if item['t'] in [5,6] else (None,'','')
                    if item['t']==2:icon,name,_=self.weapon(item['id'])
                    if item['t'] in [11,12]:name='Paid Gems' if item['t']==11 else 'Gems'
                    if name:other.append(self.img(icon,'gem_icon','16px')+esc(name)+f' ×{item["n"]}')
            else:other.extend(esc(b) for b in s.get('bonus',[]))
            if s.get('limit'):
                note=f"Can be used {s['limit']} time{'s' if s['limit']!=1 else ''}"+(' per day.' if s.get('daily') else ' per cycle.' if s.get('step') else '.')
                other.append(note)
            if s.get('set'):
                names=[self.costume(c) for c in s['set']];names=[f"{c['character']} ({c['costume']})" for c in names if c]
                if names:other.append('Guaranteed character pool: '+esc(', '.join(names)))
            label=f"Step {s['step']}: " if s.get('step') else ''
            rows.append(f'<tr><td>{label}{s["draws"]}x summon</td><td>{price}</td><td>'+('<br>'.join(other) or '—')+'</td></tr>')
            facts.append({k:s[k] for k in ['draws','cur','price','guar','limit','daily','feat4','rate','bonus','set','items','ticket','ticket_name','guaranteed_count','bonus_display','guarantee_slot'] if k in s})
        out='<div class="information_table"><table style="width:100%"><thead><tr><th>Type</th><th>'+('Required Tickets' if r.get('event') else 'Required Gems / Tickets')+'</th><th>Other</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
        currencies={s['cur'] for s in steps}
        if currencies=={'paid'}:notes.append('This summons can only be used with paid gems.')
        elif currencies=={'paid','free'}:notes.append('Paid steps require paid gems. Steps marked Free do not consume gems.')
        for s in steps:
            if self.guarantee(s) and self.guarantee(s) not in notes:notes.append(self.guarantee(s))
        out+='<p>'+'<br>'.join(esc(n) for n in notes)+'</p>'
        return out,facts

    def event_bonus_section(self,g):
        record=self.event_bonuses.get(g,{})
        if not record.get('events'):return '',[]
        import build_summon_notice_repair_pack as common
        sections=[];facts=[];costume_facts=[]
        for event in record['events']:
            content='<h4>'+esc(event['event_name'])+'</h4>'
            content+='<div class="holding-period">'+esc(common.date(event['chapter_row'][8]))+' – '+esc(common.date(event['chapter_row'][9]))+'</div>'
            costume_rows=[]
            for bonus in event.get('costume_bonuses',[]):
                c=self.costume(bonus['costume_id'])
                if not c:continue
                for stat,values in bonus['stat_percent_by_ascension'].items():
                    costume_rows.append('<tr><td>'+self.img(self.costume_icon(c['costume_id']),width='32px',alt=c['costume'])+esc(f"{c['character']} ({c['costume']})")+'</td><td>'+esc(stat)+'</td>'+''.join('<td>+'+str(v)+'%</td>' for v in values)+'</tr>')
                    costume_facts.append({'event_id':event['event_id'],'costume_id':c['costume_id'],'stat':stat,'percent_by_ascension':values})
            if costume_rows:
                content+='<p>The costumes below receive quest bonuses during this event.</p><div class="information_table"><table><thead><tr><th rowspan="2">Costume</th><th rowspan="2">Bonus</th><th colspan="5">Ascension Count</th></tr><tr><th>None</th><th>1</th><th>2</th><th>3</th><th>4</th></tr></thead><tbody>'+''.join(costume_rows)+'</tbody></table></div>'
            rows=[]
            for bonus in event['weapon_bonuses']:
                icon,name,_=self.weapon(bonus['weapon_id'])
                if not name:continue
                item=self.item_icon(bonus['currency_id'])
                rows.append('<tr><td>'+self.img(icon,width='32px',alt=name)+esc(name)+'</td><td>'+self.img(item,'gem_icon','16px')+esc(bonus['currency_name'])+'</td>'+''.join('<td>+'+str(n)+'</td>' for n in bonus['additional_drops_by_ascension'])+'</tr>')
                facts.append({'event_id':event['event_id'],'weapon_id':bonus['weapon_id'],'currency_id':bonus['currency_id'],
                              'additional_drops_by_ascension':bonus['additional_drops_by_ascension']})
            if not rows and not costume_rows:continue
            if rows:content+='<p>Equipping the weapons below increases the number of event items dropped in these quests. The bonus depends on the weapon’s ascension count.</p><div class="information_table"><table><thead><tr><th rowspan="2">Weapon</th><th rowspan="2">Event Item</th><th colspan="5">Ascension Count</th></tr><tr><th>None</th><th>1</th><th>2</th><th>3</th><th>4</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
            sections.append(content)
        self.costume_bonus_facts[g]=costume_facts
        return ('<section><h3>Event Quest Bonuses</h3>'+''.join(sections)+'</section>' if sections else ''),facts

    def enhance(self,n,entry,base,mapping):
        entry=self.fidelity.prepare(entry,mapping)
        r=entry['record'];doc=soup(n['body']);asset=r['asset'];g=r['gacha_id']
        original_text=doc.get_text(' ',strip=True);original_images=len(doc.select('img'))
        logo=self.bundle_image(f'ui/gacha/en/{asset}/title_logo.assetbundle')
        appeal_files=sorted((self.asset_root/f'ui/gacha/en/{asset}/appeal').glob('*.assetbundle'))
        appeals=[self.bundle_image(p.relative_to(self.asset_root).as_posix()) for p in appeal_files]
        appeals=[p for p in appeals if p]
        header=doc.find('section')
        if header is None or header.find('h3'):
            header=doc.new_tag('section');doc.body.insert(0,header)
        if logo:
            new=soup(f'<section><div class="info-largeimage"><img src="{logo}" alt="{esc(entry["title"])}"></div></section>').find('section')
            if header and not header.find('h3'):header.replace_with(new)
            else:doc.body.insert(0,new)
            header=new
        else:
            header.insert(0,soup(self.fidelity.title_panel(entry['title'])).find('div'))
            mapping['fidelity']['reconstructed_text_title_panel']=True
        header['class']=['notice-intro']
        x=self.exchange(r) if r.get('exchange') or r.get('medal') else None
        steps=r.get('bunker_configuration',{}).get('steps',[])
        featured_ids,featured_weapons=self.featured(r)
        featured_weapons=list(dict.fromkeys(featured_weapons+r.get('_native_featured_weapons',[])))
        intro=[f'The <span class="text-red">{esc(entry["title"])}</span> is available.']
        if len(steps)==1 and not r.get('configuration_conflicts'):
            s=steps[0]
            if s['cur']=='paid':intro.append(f'This is a {s["draws"]}x summon that uses paid gems.')
            if s['cur']=='free':intro.append(f'Perform a <span class="text-red">free {s["draws"]}x summon</span> without spending gems or tickets.')
            if s['cur']=='ticket':intro.append('Use '+esc(s.get('ticket_name','a summon ticket'))+' to summon.')
            if s.get('limit'):intro.append('It can be used <span class="text-red">'+('once' if s['limit']==1 else str(s['limit'])+' times')+(' per day' if s.get('daily') else '')+'</span>.')
            if self.guarantee(s):intro.append('<span class="text-red">'+self.guarantee(s)+'</span>')
            if s.get('feat4') and len(featured_ids)==1:
                c=self.costume(featured_ids[0]);intro.append('Whenever a ★★★★ character weapon appears, <span class="text-red">'+esc(f"{c['character']} ({c['costume']})")+'</span> is guaranteed.')
        if x:intro.append('The <span class="text-red">'+esc(x['shard_name'])+' Exchange</span> is also available.')
        header.append(soup('<p>'+'<br>'.join(intro)+'</p>').find('p'))
        # Use the original-style period band instead of a spreadsheet for dates.
        for h in list(doc.select('h3')):
            if h.get_text(' ',strip=True) in ['Banner Period','Banner Periods','Duration','Estimated Period','Event Period','Start Date']:
                section=h.find_parent('section');tbl=section.find('table')
                if tbl:
                    bands=[]
                    for tr in tbl.select('tbody tr'):
                        cells=tr.find_all('td')
                        if len(cells)>=2:bands.append('<div class="holding-period">'+esc(cells[0].get_text(' ',strip=True))+' – '+esc(cells[1].get_text(' ',strip=True))+'</div>')
                    wrapper=doc.new_tag('div')
                    wrapper.extend(list(soup(''.join(bands)).body.contents))
                    tbl.replace_with(wrapper)
                elif h.get_text(' ',strip=True)=='Start Date':
                    pair=r.get('bunker_configuration',{}).get('raw_added_rule',{}).get('pair')
                    paired=self.entries.get(pair,{}).get('record',{})
                    periods=paired.get('native_banner_periods',[])
                    if periods:
                        import build_summon_notice_repair_pack as common
                        section.clear();section.append(soup('<h3>Estimated Period</h3>').find('h3'))
                        for b in periods:section.append(soup('<div class="holding-period">'+esc(common.date(b['row'][6]))+' – '+esc(common.date(b['row'][7]))+'</div>').find('div'))
                        mapping['rich_paired_period_source']=pair
        # Native cards and names replace the exchange-only character spreadsheet.
        chars=(x or {}).get('lineup',[])
        illustrated=[]
        if not chars:
            set_ids=list(dict.fromkeys(c for s in steps for c in s.get('set',[])))
            ids=featured_ids or set_ids
            if not ids and r.get('_native_featured_weapons'):
                ids=[c for c,w in self.fidelity.pairs.items() if w in r['_native_featured_weapons']]
                featured_ids=ids
            if not ids:
                illustrated=r.get('_native_illustrated_costumes') or r.get('bunker_configuration',{}).get('raw_added_rule',{}).get('cards',[])
                ids=illustrated
            chars=[c for ident in ids if (c:=self.fidelity.card(ident))]
        chosen=[c for c in chars if c['costume_id'] in featured_ids] if featured_ids else chars
        char_html=''
        for c in chosen:
            member=self.costume_icon(c['costume_id']);w=c.get('weapon_id');weapon_icon,weapon_name,_=self.weapon(w) if w else (None,'',0)
            rarity=self.master['Costume'][c['costume_id']]['RarityType']//10
            char_html+='<p>'+self.stars(rarity)+'</p><p>'+self.img(member,alt=c['costume'])+esc(f"{c['character']} ({c['costume']})")
            if w:char_html+='<br>Note: You can get this character by acquiring the <span class="text-red">'+esc(c.get('weapon') or weapon_name)+'</span> weapon.'
            char_html+='</p><br>'
        weapons=list(dict.fromkeys([c['weapon_id'] for c in chosen if c.get('weapon_id')]+featured_weapons))
        weapon_html=''
        for w in weapons:
            icon,name,rarity=self.weapon(w)
            if name:weapon_html+='<p>'+self.stars(rarity)+'</p><p>'+self.img(icon,alt=name)+esc(name)+'</p><br>'
        promo=''.join(f'<div class="info-largeimage"><img src="{p}" alt="Original summon promotional panel"></div>' for p in appeals)
        if asset.startswith('step_up_'):
            overview=[p for p in appeal_files if p.stem=='step_up']
            if overview:
                cover=self.bundle_cache.get(overview[0].relative_to(self.asset_root).as_posix())
                panels=[p for p in appeals if p!=cover]
                promo=f'<div class="info-largeimage"><img src="{cover}" alt="Summon step overview"></div>'
                if panels:promo+='<details><summary>View individual step panels</summary>'+''.join(f'<div class="info-largeimage"><img src="{p}" alt="Summon step panel"></div>' for p in panels)+'</details>'
        if char_html or promo or weapon_html:
            heading='Featured Characters &amp; Weapons' if (featured_ids or featured_weapons) and not r.get('_native_promotions',{}).get('no_featured_rates') else 'Summons Information'
            content='<section><h3>'+heading+'</h3>'+promo
            cards=''
            if char_html:cards+='<h4>'+('Characters' if featured_ids or any(s.get('set') for s in steps) else 'Characters Shown on the Banner' if illustrated else 'Exchange Characters')+'</h4>'+char_html
            if weapon_html:cards+='<h4>Weapons</h4>'+weapon_html
            if x and not featured_ids and not illustrated and len(chosen)>6:
                content+='<details><summary>View exchange characters and weapons</summary>'+cards+'</details>'
            else:content+=cards
            content+='</section>'
            old=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='Exchange Lineup'),None)
            new=soup(content).find('section')
            if old:old.replace_with(new)
            else:
                detail=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True) in ['Summons Details','Notes']),None)
                if detail:detail.insert_before(new)
                else:doc.body.append(new)
        details,facts=self.phase_details(r)
        if details:
            new=soup('<section><h3>Summons Details</h3>'+details+'</section>').find('section')
            old=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='Summons Details'),None)
            if old:old.replace_with(new)
            else:doc.body.append(new)
        if x:
            icon=self.item_icon(x['shard_id']);name=x['shard_name']
            existing=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='About Shards / Exchange'),None)
            convert=next((p.get_text(' ',strip=True) for p in existing.select('p') if p.get_text(' ',strip=True).startswith('Shard conversion:')),'') if existing else ''
            exchange='<section><h3>About '+esc(name)+'</h3><p>'+self.img(icon,'coin_icon','32px',name)+'You will earn <span class="text-red">'+esc(name)+'</span> by using this summons.<br>Use these shards at the exchange of the same name to obtain characters and weapons.</p>'
            if steps and not r.get('configuration_conflicts'):exchange+='<p>Each summon gives one shard. A 10x summon gives 10 shards.</p>'
            rows=[]
            for c in chars:
                w=c.get('weapon_id');wi,wn,_=self.weapon(w) if w else (None,'',0)
                rows.append('<tr><td>'+self.img(wi,alt=c.get('weapon',''))+esc(c.get('weapon') or wn)+(' ('+esc(c['costume'])+')' if c.get('costume') else '')+'</td><td>'+self.img(icon,'gem_icon','16px')+str(c.get('price',''))+' shards</td></tr>')
            for w in x.get('other_exchange_weapons',[]):
                wi,wn,_=self.weapon(w['weapon_id']);rows.append('<tr><td>'+self.img(wi,alt=wn)+esc(w['weapon'])+'</td><td>'+str(w['price'])+' shards</td></tr>')
            if rows:exchange+='<div class="information_table"><table style="width:100%"><thead><tr><th>Exchange Character / Weapon</th><th>Required Shards</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
            if convert:exchange+='<p>'+esc(convert)+'</p>'
            exchange+='<p>Shards can only be used at the exchange of the same name.</p></section>'
            new=soup(exchange).find('section')
            if existing:existing.replace_with(new)
            else:doc.body.append(new)
        # Put native reward icons into the event box tables too.
        if r.get('event'):
            section=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='Event Summons'),None)
            if section:
                prizes=[p for level in r['event']['main_prizes'] for p in level]
                rows=section.select('tbody tr')
                if len(rows)==len(prizes):
                    for tr,p in zip(rows,prizes):
                        cells=tr.find_all('td')
                        if len(cells)>=2:
                            icon=self.weapon(p['id'])[0] if p['type']==2 else self.item_icon(p['id'],True) if p['type']==5 else None
                            if icon:cells[1].insert(0,soup(self.img(icon,alt=p['name'])).find('img'))
        bonus_content,bonus_facts=self.event_bonus_section(g)
        if bonus_content:
            new=soup(bonus_content).find('section')
            anchor=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='Notes'),None)
            if anchor:anchor.insert_before(new)
            else:doc.body.append(new)
        # Match the source's list treatment for ordinary player notes.
        notes=next((h.find_parent('section') for h in doc.select('h3') if h.get_text(' ',strip=True)=='Notes'),None)
        if notes:
            ps=notes.find_all('p',recursive=False)
            if ps:
                ul=doc.new_tag('ul');wrap=doc.new_tag('div',attrs={'class':'attention_content'})
                for p in ps:
                    li=doc.new_tag('li');li.extend(list(p.contents));ul.append(li);p.decompose()
                wrap.append(ul);notes.append(wrap)
        doc=self.fidelity.finish(doc,entry,mapping)
        n={**n,'title':entry['title'],'body':body(doc)}
        mapping['rich_content']={'title_graphic':logo,'promotion_panels':appeals,'character_cards':len(chosen),
            'weapon_cards':len(weapons),'configured_phase_facts':facts,'text_chars_before':len(original_text),
            'native_event_bonus_rows':bonus_facts,
            'native_event_costume_bonus_rows':self.costume_bonus_facts.get(g,[]),
            'text_chars_after':len(BeautifulSoup(n['body'],'html5lib').get_text(' ',strip=True)),
            'images_before':original_images,'images_after':len(BeautifulSoup(n['body'],'html5lib').select('img')),
            'source_bonus_or_rate_facts_copied':False}
        mapping['player_visible_headings']=[h.get_text(' ',strip=True) for h in soup(n['body']).select('h3')]
        return n


def export_game_previews(folder,pack):
    """Use the shared server CSS for both originals and reconstructions."""
    source=ROOT/'overlays/server/internal/service/bunker_notices.go'
    css=re.search(r'const noticeCSS = `([\s\S]*?)`',source.read_text(encoding='utf-8')).group(1)
    (folder/'notice-game.css').write_text(css,encoding='utf-8')
    for n in pack['notices']:
        content=re.sub(r'(["\'])img/',r'\1../img/',n['body'])
        content=re.sub(r'(["\'])\?informationId=(\d+)(["\'])',r'\1\2.html\3',content)
        content=content.replace('href="/web/en/gacha-details?', 'href="http://127.0.0.1:18080/web/en/gacha-details?')
        page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(n['title'])+'</title><link rel="stylesheet" href="../notice-game.css"><main class="detail"><header><a class="back" href="../all-notices.html" aria-label="All Notices"></a><div class="head-text"><h1>'+esc(n['title'])+'</h1></div></header><article>'+content+'</article></main></html>'
        (folder/'notices'/f'{n["id"]}.html').write_text(page,encoding='utf-8')
    comparison='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Notice presentation comparison</title><style>
    *{box-sizing:border-box}body{margin:0;padding:20px;background:#111;color:#e6dfcf;font:14px/1.5 system-ui}h1{font-size:20px;margin:0 0 8px}p{max-width:900px} .pages{display:grid;grid-template-columns:1fr 1fr;gap:20px}h2{font-size:15px}iframe{width:100%;height:1500px;border:1px solid #736b68}a{color:#d29797}
    </style><h1>Original and corrected reconstruction</h1><p>Both pages use the game's notice CSS at the same width. Fractured Prisoner uses its own native title, promotion artwork, characters, weapons and summon configuration. The original's later event bonuses are specific to Fractured Songstress.</p><div class="pages"><section><h2>Original: Paid Only Fractured Songstress · 1013</h2><a href="notices/1013.html">Open full original</a><iframe src="notices/1013.html"></iframe></section><section><h2>Corrected: Paid-Only Fractured Prisoner · 1500000039</h2><a href="notices/1500000039.html">Open full reconstruction</a><iframe src="notices/1500000039.html"></iframe></section></div></html>'''
    (folder/'comparison.html').write_text(comparison,encoding='utf-8')
    import build_summon_notice_repair_pack as common
    summons={}
    for g,nid in pack['gacha'].items():summons.setdefault(nid,[]).append(g)
    rows=[]
    for n in sorted(pack['notices'],key=lambda n:(-n.get('publish',0),-n['id'])):
        kind='reconstructed' if n['id']>=common.SYNTHETIC_BASE else 'original'
        rows.append(f'<tr data-kind="{kind}"><td>{n["id"]}</td><td><a href="notices/{n["id"]}.html">{esc(n["title"])}</a></td><td>{kind.title()}</td><td>'+esc(', '.join(summons.get(n['id'],[])) or '—')+'</td></tr>')
    content='<h1>All Notices</h1><p><a href="index.html">Summon notice bases</a> · <a href="comparison.html">Original / reconstruction comparison</a></p><p id="count" aria-live="polite">'+str(len(rows))+' notices</p><label for="filter">Search title, notice ID or summon ID</label><br><input id="filter" type="search" placeholder="Search notices…"><label for="kind"> Show </label><select id="kind"><option value="">All notices</option><option value="original">Original notices</option><option value="reconstructed">Reconstructed notices</option></select><table><thead><tr><th>Notice ID</th><th>Title</th><th>Page</th><th>Summon IDs</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table><script>const rows=[...document.querySelectorAll("tbody tr")];function filter(){const q=document.querySelector("#filter").value.trim().toLowerCase(),kind=document.querySelector("#kind").value;let shown=0;for(const r of rows){r.hidden=!(r.textContent.toLowerCase().includes(q)&&(!kind||r.dataset.kind===kind));if(!r.hidden)shown++}document.querySelector("#count").textContent=shown+" of "+rows.length+" notices"}document.querySelector("#filter").addEventListener("input",filter);document.querySelector("#kind").addEventListener("change",filter);</script>'
    (folder/'all-notices.html').write_text(common.page('All Notices',content,''),encoding='utf-8')
