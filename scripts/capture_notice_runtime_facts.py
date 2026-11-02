"""Read implemented summon configuration without drawing or changing a save.

GetGacha loads the requested catalog rows; unlike GetGachaList it does not
auto-convert medals. Rates remain in the game's live Details page, since Pod
Program settings can change them. This is runtime evidence, not historical odds.
"""
import concurrent.futures,hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.build/notice-audit/python'),str(ROOT/'scripts')]
import grpc
from google.protobuf import descriptor_pb2,descriptor_pool,message_factory,json_format
import google.protobuf.timestamp_pb2
from rich_notice_content import soup
import build_notice_templates as templates


def messages():
    fd=descriptor_pb2.FileDescriptorProto(name='notice_fidelity_probe.proto',package='noticefidelity',syntax='proto3')
    fd.dependency.append('google/protobuf/timestamp.proto')
    I,S,M=5,9,11
    def msg(name,fields):
        m=fd.message_type.add(name=name)
        for number,name,kind,target,repeated in fields:
            f=m.field.add(number=number,name=name,type=kind,label=3 if repeated else 1)
            if target:f.type_name=target
        return m
    msg('Bonus',[(1,'type',I,'',False),(2,'id',I,'',False),(3,'count',I,'',False)])
    msg('Fixed',[(1,'rarity',I,'',False),(2,'count',I,'',False)])
    msg('Phase',[(1,'id',I,'',False),(3,'limit',I,'',False),(5,'priceType',I,'',False),(6,'priceId',I,'',False),(7,'price',I,'',False),(9,'draws',I,'',False),(11,'bonuses',M,'.noticefidelity.Bonus',True),(12,'fixed',M,'.noticefidelity.Fixed',False)])
    msg('Gacha',[(1,'id',I,'',False),(4,'mode',I,'',False),(5,'resetType',I,'',False),(6,'resetPeriod',I,'',False),(10,'phases',M,'.noticefidelity.Phase',True),(13,'start',M,'.google.protobuf.Timestamp',False),(14,'end',M,'.google.protobuf.Timestamp',False),(22,'medal',I,'',False)])
    msg('Request',[(1,'ids',I,'',True)])
    entry=msg('Entry',[(1,'key',I,'',False),(2,'value',M,'.noticefidelity.Gacha',False)]);entry.options.map_entry=True
    msg('Response',[(1,'gacha',M,'.noticefidelity.Entry',True)])
    pool=descriptor_pool.Default();pool.Add(fd)
    return tuple(message_factory.GetMessageClass(pool.FindMessageTypeByName('noticefidelity.'+n)) for n in ['Request','Response'])


def main():
    mapping=json.loads((ROOT/'inputs/summon-notice-template-map.json').read_text(encoding='utf-8'))['matches']
    ids=[m['gacha_id'] for m in mapping if m['action']=='adapt_template']
    folder=ROOT/'artifacts/notice-fidelity-audit/runtime-details';folder.mkdir(parents=True,exist_ok=True)
    Request,Response=messages()
    with grpc.insecure_channel('127.0.0.1:18003',options=[('grpc.max_receive_message_length',32*1024*1024)]) as ch:
        response=ch.unary_unary('/apb.api.gacha.GachaService/GetGacha',request_serializer=lambda r:r.SerializeToString(),response_deserializer=Response.FromString)(Request(ids=ids),timeout=20)
    runtime=json_format.MessageToDict(response).get('gacha',{})
    def fetch(g):
        url=f'http://127.0.0.1:18080/web/en/gacha-details?gachaId={g}'
        raw=urllib.request.urlopen(url,timeout=8).read();(folder/f'{g}.html').write_bytes(raw)
        doc=soup(raw.decode('utf-8'));h=next((h for h in doc.select('h2') if h.get_text(strip=True)=='COST'),None)
        rows=[]
        if h:
            for tr in h.find_next('table').select('tr'):
                cells=tr.find_all('td');label=cells[0].get_text(' ',strip=True);price=cells[1].get_text(' ',strip=True)
                draw=re.search(r'(\d+) summons?',label);step=re.search(r'Step (\d+)',label);limit=re.search(r'Up to (\d+) times',label)
                fixed=re.search(r'(\d+) guaranteed ★(\d+) or higher',label)
                rows.append({'draws':int(draw[1]),'step':int(step[1]) if step else 0,'price_text':price,
                             'limit':int(limit[1]) if limit else 0,'fixed_count':int(fixed[1]) if fixed else 0,'fixed_rarity':int(fixed[2])*10 if fixed else 0})
        return str(g),{'endpoint':url,'html_sha256':hashlib.sha256(raw).hexdigest(),'rpc':runtime.get(str(g)), 'cost_rows':rows}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:rows=dict(pool.map(fetch,ids))
    data={'version':1,'source':'Running Bunker 1.7.0: read-only GetGacha and gacha-details. Not original historical rules. No rates copied because Pod Programs can change them.',
          'observed_utc':datetime.now(timezone.utc).isoformat(),'entries':rows}
    output=ROOT/'inputs/summon-notice-runtime-facts.json';output.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'requested':len(ids),'structured_rows':len(runtime),'pages_with_costs':sum(bool(r['cost_rows']) for r in rows.values())}))


if __name__=='__main__':main()
