"""Recover advertised summon terms from native promotional panels.

OCR is an index, not an authority for ambiguous numerals. Price/loop/guarantee
corrections below were checked visually against the native panel/overview.
"""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

NAMES=['Piece: Zenith\'s Brilliance','Piece: Black Pearl','Advanced Handbook','Black Pearl',
       'Small Slab Fragment','Medium Slab Fragment','Large Slab Fragment',
       'Small Cursed-God Antler Bit','Medium Cursed-God Antler Bit','Large Cursed-God Antler Bit',
       'Skip Ticket','Small BP Recovery','Insignia of Skill','Insignia of Quality',
       'Topaz','Tanzanite','XL Weapon Enhancement','XL Character Enhancement']

def bonuses(text):
    out=[];used=[]
    for name in NAMES:
        pattern=re.escape(name).replace(r'\ ',r'\s*').replace(':',r'[:.]?').replace("'",r"['’]?")
        if name=='Advanced Handbook':pattern=r'Ad[vce]+anced?\s*Handbook|Advanced\s*Handbook'
        for m in re.finditer('(?:'+pattern+r')\s*[xX×]\s*([0-9OIlo,]+)',text,re.I):
            if any(a<=m.start()<b for a,b in used):continue
            number=m[1].translate(str.maketrans({'O':'0','I':'1','l':'1','o':'0'})).replace(',','')
            if not number.isdigit() or not 0<int(number)<=10000:continue
            row={'name':name,'quantity':int(number)}
            if row not in out:out.append(row)
            used.append(m.span())
    return out

def main():
    observations=json.loads((ROOT/'.build/notice-audit/panel-ocr/results.json').read_text(encoding='utf-8'))
    assets={}
    for row in observations:
        asset=row['source_bundle'].split('/')[3];part=Path(row['source_bundle']).stem
        a=assets.setdefault(asset,{'sources':[],'steps':{},'features':[]})
        a['sources'].append({'bundle':row['source_bundle'],'member':row['member'],'ocr_lines':row['lines']})
        text=' '.join(row['lines']);step=int(part) if part.isdigit() and asset.startswith('step_up_') else 0
        if part=='step_up':continue
        s=a['steps'].setdefault(str(step),{})
        found=bonuses(text)
        if found:s['bonus_display']=found
        if re.search(r'appearance\s*rate\s*(?:doubled|double|x\s*2)',text,re.I):s['rate']=2
        elif re.search(r'appearance\s*rate\s*x\s*1\s*\.\s*5',text,re.I):s['rate']=1.5
        if 'no characters or weapons will have featured rates' in text.lower():a['no_featured_rates']=True
        if re.search(r'more\s*ascen[st]ion\s*material',text,re.I):a['features'].append('Summoning a duplicate ★★★★ character can grant additional ascension materials.')
    def a(name):return assets[name]
    def s(name,step=0):return a(name)['steps'].setdefault(str(step),{})
    def reward(name,count):return {'name':name,'quantity':count}
    # These paid costume panels were visually checked; OCR often separated
    # "Get Piece:" from the following Zenith's Brilliance name.
    for number in [68,108,110,122,130,133,135,149,152,158,164,167,169,172,174,177,179,182,187,191,193,404]:
        s('limited_'+str(number))['bonus_display']=[reward("Piece: Zenith's Brilliance",2)]
    s('limited_177')['rate']=1.5
    # Visually verified numerical price fields. Generic runtime prices were
    # contradictory to these original panels and must not override them.
    for name in ['limited_43','limited_52','limited_60']:s(name).update(draws=10,cur='paid',price=1500,only_advertised_option=True)
    for name in ['limited_49','limited_9004','limited_9015','limited_9025','limited_9026','limited_9027','limited_9028']:
        s(name).update(draws=10,cur='gems',price=2000,limit=5,only_advertised_option=True,bonus_display=[reward('Advanced Handbook',2)])
    a('limited_49')['display_title']='NieR Day Bonus Summons'
    a('limited_49')['title_basis']='Native title graphic says NieR Day Bonus Summons; the final catalog title asserts an unsupported four-star guarantee.'
    s('limited_84').update(limit=10,bonus_display=[reward('Advanced Handbook',2)])
    for name in ['limited_9014','limited_9018']:
        s(name).update(draws=10,cur='gems',price=2000,limit=20,only_advertised_option=True,bonus_display=[reward('Piece: Black Pearl',1)])
    s('limited_66')['guar']='r4c';a('limited_66')['no_featured_rates']=True
    s('limited_59')['rate']=2;a('limited_59')['shared_exchange_from']=58
    a('limited_59')['shared_exchange_basis']='Own panel explicitly names Shard (Half-Year Anniversary); target 58 has the same native start and the original-run exchange of that exact name.'
    s('limited_139').update(draws=10,cur='free',price=0,only_advertised_option=True)
    # These two rewards belong to the 50-medal exchange, not the free draw.
    s('limited_139').pop('bonus_display',None)
    a('limited_139')['features']+=['No new characters or weapons appear in this summons.','Fio, Akeha and Levania appear as ★★★★ characters, with their limited-time costumes included.','Trade 50 Mama’s Exciting Festival Medals for Piece: Zenith’s Brilliance ×5 or Piece: Black Pearl ×5.']
    a('limited_139')['no_featured_rates']=True
    s('limited_186').update(rate=2,bonus_display=[reward('Small Slab Fragment',300),reward('Medium Slab Fragment',200),reward('Large Slab Fragment',20),reward('Small Cursed-God Antler Bit',300),reward('Medium Cursed-God Antler Bit',200),reward('Large Cursed-God Antler Bit',20)])
    a('limited_186')['no_featured_rates']=True
    # The 194 panel lists examples rather than promising a complete bonus pool.
    s('limited_194')['rate']=2;s('limited_194').pop('bonus_display',None)
    a('limited_194')['features'].append('Summon bonuses include items such as Advanced Handbook ×2, Large Slab Fragment ×20 and Large Cursed-God Antler Bit ×20.')
    s('limited_405').update(rate=1.5,bonus_display=[reward('Piece: Black Pearl',2)])
    a('limited_405')['features']+=['When a ★★★★ appears, a previously available Abyssal costume is guaranteed.','Rion (Abyssal Exile) does not appear in this summons.']
    a('limited_405')['illustrated_costume_names']=['Abyssal Gunman','Abyssal Girl','Abyssal Monster']
    # The fifth Daily Showcase's weapon names are explicit in its own panel.
    weapons={'limited_9019':['Iron Abandonment','Tormented Eviscerator'],'limited_9020':['Three-Wing Sword','Sword of the Titan'],
             'limited_9021':['Faulty Greatsword','Core-expelling Blade'],'limited_9022':["Winter’s Warmth",'Seabone Blade'],
             'limited_9023':['Trusting Trigger','Mechanical Heart']}
    for name,values in weapons.items():a(name)['featured_weapon_names']=values;a(name)['features'].append('Whenever a ★★★★ weapon appears, one of the featured weapons is guaranteed.')
    # Complete loop counts and overview rewards were verified visually; some
    # summaries carry rewards absent from the individual-step OCR.
    loops={'507001':3,'509001':0,'510001':0,'512001':1,'514001':4,'515001':1,'516001':3,'517001':0,'519001':1,'522001':1,'524001':3,'525001':1,'530001':3,'503001':5,'505001':6,'900001':2,'900002':5,'511001':1}
    for number,count in loops.items():a('step_up_'+number)['loop_limit']=count
    extra={
      '507001':{1:[('Skip Ticket',100)],5:[('Skip Ticket',30)]},
      '509001':{5:[('Insignia of Quality',1)]},'510001':{5:[('Insignia of Quality',1)]},
      '514001':{1:[('Skip Ticket',100),('Small BP Recovery',50)],2:[('Insignia of Skill',1),('Insignia of Quality',2)]},
      '516001':{1:[('Skip Ticket',100)],5:[('Skip Ticket',30)]},'517001':{3:[('Skip Ticket',100)]},
      '519001':{1:[('Topaz',50),('Tanzanite',50),('XL Weapon Enhancement',1000)],2:[('XL Weapon Enhancement',1000)],3:[('Skip Ticket',100),('XL Weapon Enhancement',1000)]},
      '522001':{1:[('Skip Ticket',100),('XL Weapon Enhancement',1000)]},
      '524001':{2:[('Skip Ticket',100)],5:[('Skip Ticket',30)]},
      '525001':{1:[('Skip Ticket',100),('XL Weapon Enhancement',1000)],2:[('Insignia of Quality',1),('Insignia of Skill',1),('XL Weapon Enhancement',1000)]},
      '530001':{1:[('Skip Ticket',50)],2:[('Skip Ticket',50)]},
      '503001':{5:[('Large Slab Fragment',10)]},'505001':{5:[('Insignia of Quality',1)]},
      '900001':{4:[('Skip Ticket',50),('Small Cursed-God Antler Bit',350),('Medium Cursed-God Antler Bit',150)],5:[('Small Cursed-God Antler Bit',400),('Medium Cursed-God Antler Bit',150)]},
      '900002':{5:[('Skip Ticket',30)]}}
    for number,steps in extra.items():
        for step,items in steps.items():
            target=s('step_up_'+number,step).setdefault('bonus_display',[])
            for name,count in items:
                if reward(name,count) not in target:target.append(reward(name,count))
    # Guarantee text here is explicit in the inspected overview's slot label.
    for number,last,first in [('514001',4,1),('519001',3,1),('522001',3,1),('525001',4,1)]:
        s('step_up_'+number,first)['guar']='r4w';s('step_up_'+number,last)['guar']='r4c'
    for number in ['512001','515001']:s('step_up_'+number,5)['guar']='r4c'
    for number in ['501001','900002']:s('step_up_'+number,4)['guar']='r4c'
    s('step_up_503001',1)['bonus_display']=[reward('XL Character Enhancement',3500)]
    s('step_up_503001',2)['bonus_display']=[reward('XL Weapon Enhancement',1000)]
    s('step_up_503001',5)['rate']=1.5
    for number in ['509001','505001']:
        s('step_up_'+number,1)['bonus_display']=[reward('Assorted Weapon-Skill Enhancement Materials',20)]
    s('step_up_517001',1)['bonus_display']=[reward('Weapon-skill enhancement materials for each weapon type',20)]
    s('step_up_900001',5).update(guar='r4w',guarantee_slot=10)
    for number,steps in [('519001',[1,3]),('522001',[1,3])]:
        for step in steps:s('step_up_'+number,step)['guarantee_slot']=10
    a('step_up_512001')['features'].append('Whenever a ★★★★ appears, 2B, A2 or 9S is guaranteed.')
    a('step_up_515001')['features'].append('Whenever a ★★★★ appears, Kainé, The World-Ender or Emil is guaranteed.')
    for step,element in enumerate(['fire','wind','dark','water','light'],1):
        s('step_up_511001',step).update(rate=2,guar='r4w:'+element,limit=1,bonus_display=[reward("Piece: Zenith's Brilliance",1),reward('Medium Cursed-God Antler Bit',100),reward('Small Cursed-God Antler Bit',250)])
    a('step_up_511001')['no_featured_rates']=True
    # OCR ambiguities in the price fields were checked against native images.
    s('step_up_516001',1).update(price=1500,cur='gems',draws=10)
    for step in [2,4]:s('step_up_510001',step).update(price=1500,cur='gems',draws=10)
    s('step_up_524001',1).update(price=0,cur='free',draws=10)
    for key,value in assets.items():
        # Keep only supported mechanical facts; panel artwork itself remains
        # untouched and all OCR observations remain available for re-review.
        value['features']=list(dict.fromkeys(value['features']))
        value['steps']={k:v for k,v in value['steps'].items() if v}
    result={'version':1,'method':'Native promotional panel OCR used as an index; mechanical lines reviewed, ambiguous prices and step overviews checked visually. Historical advertised terms override generic runtime defaults. Artwork is unchanged.',
            'panels_checked':len(observations),'assets':assets}
    out=ROOT/'inputs/summon-notice-native-promotion-terms.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Native panels:',len(observations),'assets with mechanical terms:',sum(bool(a['steps'] or a['features']) for a in assets.values()))

if __name__=='__main__':main()
