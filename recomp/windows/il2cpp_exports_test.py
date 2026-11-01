"""Read-only original-ELF export proof and deliberately rejected inputs."""
import argparse
import json
from pathlib import Path
import tempfile
from il2cpp_prepare import unity_requests,digest,UNITY_SHA256

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--unity-library',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True)
    p.add_argument('--translation',type=Path,required=True)
    a=p.parse_args();m=json.loads((a.translation/'manifest.json').read_text());checks=0
    def check(value,why):
        nonlocal checks
        if not value:raise AssertionError(why)
        checks+=1
    def reject(unity,manifest,why):
        try:unity_requests(unity,a.library,manifest)
        except RuntimeError:check(True,why)
        else:raise AssertionError(why)
    result=unity_requests(a.unity_library,a.library,m)
    check(result['unity_sha256']==UNITY_SHA256 and result['request_count']==222,'actual Unity source and count')
    check(len({r['name']for r in result['requests']})==222,'distinct names')
    check(not any(r['entry']in m['unsupported_traces']for r in result['requests']),'supported export entries')
    check(result['requests'][0]['name']=='il2cpp_init'and result['requests'][1]['name']=='il2cpp_init_utf16','real resolver order')
    check(result['dlsym_relocation']['type']==1026 and result['dlsym_relocation']['undefined'],'actual undefined dlsym ownership')
    check(all(r['slot']==0x12bbfd0+i*8 for i,r in enumerate(result['requests'])),'real contiguous Unity result table')
    first=result['requests'][0]
    invalid=dict(m);invalid['exports']=dict(m['exports']);invalid['exports'][first['name']]+=4
    reject(a.unity_library,invalid,'mismatched original export address rejected')
    invalid=dict(m);invalid['exports']=dict(m['exports']);invalid['exports'].pop(first['name'])
    reject(a.unity_library,invalid,'missing manifest export rejected')
    invalid=dict(m);invalid['traces']=[v for v in m['traces']if v!=first['entry']]
    reject(a.unity_library,invalid,'untranslated export rejected')
    invalid=dict(m);invalid['unsupported_traces']=list(m['unsupported_traces'])+[first['entry']]
    reject(a.unity_library,invalid,'unsupported export entry rejected')
    invalid=dict(m,sha256='0'*64);reject(a.unity_library,invalid,'foreign IL2CPP source rejected')
    with tempfile.TemporaryDirectory()as directory:
        modified=Path(directory)/'changed-unity.so';raw=bytearray(a.unity_library.read_bytes());raw[-1]^=1;modified.write_bytes(raw)
        reject(modified,m,'changed Unity source rejected')
    print(f'Actual Unity/IL2CPP export proof: {checks} checks pass; 222 original API names/addresses; no guest execution.')

if __name__=='__main__':main()
