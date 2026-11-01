"""Validate an isolated parent-built IL2CPP overlay; never compile/rewrite shards."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
HERE=Path(__file__).resolve().parent


def digest(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def definitions(path):
    return {int(value,16)for value in re.findall(rb'^define[^\n]*@sub_([0-9a-f]+)\(',path.read_bytes(),re.M)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--translation',type=Path,required=True)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--shard',default='shard-01066')
    p.add_argument('--overlay',type=Path,required=True)
    p.add_argument('--layout-tool',type=Path,required=True)
    a=p.parse_args();manifest_path=a.translation/'manifest.json';m=json.loads(manifest_path.read_text())
    old_ir=a.translation/(a.shard+'.ll');old_object=a.translation/(a.shard+'.o')
    new_ir=a.overlay/'new.ll';new_object=a.overlay/'new.o'
    old,new=definitions(old_ir),definitions(new_ir);known=set(m['traces'])
    a.overlay.mkdir(parents=True,exist_ok=True)
    entries=a.overlay/'entries.txt';heads=a.overlay/'all-original-trace-heads.txt'
    if entries.read_text()!=''.join(f'{value:#x}\n'for value in sorted(old)):raise RuntimeError('Overlay seed list differs from ALL original definitions')
    if heads.read_text()!=''.join(f'{value:#x}\n'for value in m['traces']):raise RuntimeError('Overlay omitted or changed original trace heads')
    # Verify ownership against actual old COFF symbols, not only IR/manifest.
    process=subprocess.Popen(['llvm-nm-18','--defined-only','--extern-only','--print-file-name','--format=posix',*m['objects']],
                             stdout=subprocess.PIPE,text=True)
    inventory=hashlib.sha256();owners={value:[]for value in old};all_symbols=set()
    for line in process.stdout:
        inventory.update(line.encode())
        match=re.match(r'(.+): sub_([0-9a-f]+) T ',line)
        if not match:continue
        value=int(match.group(2),16);all_symbols.add(value)
        if value in owners:owners[value].append(str(Path(match.group(1)).resolve()))
    if process.wait():raise RuntimeError('Cannot audit original COFF symbol ownership')
    if all_symbols!=known:raise RuntimeError('Actual COFF global trace definitions differ from original manifest')
    expected_owner=str(old_object.resolve())
    if any(paths!=[expected_owner]for paths in owners.values()):raise RuntimeError('A replaced trace has missing/duplicate ownership outside selected old shard')
    text=new_ir.read_text()
    declarations={int(value,16)for value in re.findall(r'^declare[^\n]*@sub_([0-9a-f]+)\(',text,re.M)}
    bodies=re.findall(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}',text,re.M|re.S)
    unsupported=[]
    for match in re.finditer(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}',text,re.M|re.S):
        if re.search(r'call[^\n]*@__remill_(?:error|missing_block)\(',match.group()):
            unsupported.append(int(match.group(1),16))
    available=(known-old)|new
    missing=sorted(declarations-available)
    added,deleted=sorted(new-old),sorted(old-new)
    report={'status':'blocked','replaces':'objects/'+a.shard+'.o','original_manifest_sha256':digest(manifest_path),
            'original_ir_sha256':digest(old_ir),'original_object_sha256':digest(old_object),'original_toolchain':m['toolchain'],
            'original_definitions':sorted(old),'new_definitions':added,'deleted_definitions':deleted,
            'unsupported_traces':unsupported,'old_unsupported_traces':sorted(old&set(m['unsupported_traces'])),
            'direct_targets':sorted(declarations),'new_direct_targets':sorted(declarations-known),'missing_direct_targets':missing,
            'duplicate_outside_definitions':sorted(new&(known-old)),
            'original_coff_symbol_inventory_sha256':inventory.hexdigest(),'original_coff_trace_count':len(all_symbols),
            'seed_sha256':digest(entries),'all_trace_heads_sha256':digest(heads),
            'new_ir_sha256':digest(new_ir),'object':{'path':str(new_object.resolve().relative_to(a.build.resolve())),'sha256':digest(new_object),'size':new_object.stat().st_size},
            'new_toolchain':json.loads((a.overlay/'parent-toolchain.json').read_text())}
    prefix=a.overlay/'state-layout'
    result=subprocess.run([str(a.layout_tool),str(old_ir),str(new_ir),str(prefix)])
    report['state_layout']={'equal':result.returncode==0,
            'old_sha256':digest(Path(str(prefix)+'.old.txt'))if Path(str(prefix)+'.old.txt').is_file()else None,
            'new_sha256':digest(Path(str(prefix)+'.new.txt'))if Path(str(prefix)+'.new.txt').is_file()else None}
    if not(added or deleted or missing or report['duplicate_outside_definitions'] or result.returncode):
        symbols=subprocess.check_output(['llvm-nm-18','--defined-only','--extern-only','--format=just-symbols',str(new_object)],text=True)
        compiled={int(value,16)for value in re.findall(r'^sub_([0-9a-f]+)$',symbols,re.M)}
        if compiled!=new:raise RuntimeError('Fresh COFF definitions differ from fresh IR')
        report['status']='validated'
    (a.overlay/'overlay.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key]for key in ('status','new_definitions','deleted_definitions','unsupported_traces','new_direct_targets','missing_direct_targets','duplicate_outside_definitions','state_layout')},indent=2))
    if report['status']!='validated':raise SystemExit('Overlay blocked: preserve report and close new/deleted definitions/direct targets before linking')


if __name__=='__main__':main()
