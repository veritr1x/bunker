"""Read typed direct-application metadata from actual AAPT manifest/resources."""
import json
import re
import subprocess


def parse_application_metadata(manifest, resources):
    lines=resources.splitlines();table={}
    for index,line in enumerate(lines):
        match=re.match(r'\s+resource (0x[0-9a-f]+) ([^: ]+:[^: ]+): t=(0x[0-9a-f]+) d=(0x[0-9a-f]+)',line)
        if not match:continue
        address=int(match[1],16)
        if address in table:continue  # AAPT lists the default configuration first.
        kind,bits=int(match[3],16),int(match[4],16)
        value=json.loads(lines[index+1].strip().split(' ',1)[1]) if kind==3 else bits
        table[address]=(kind,value,match[2])

    def resource(raw,seen=()):
        address=int(raw[1:],16)
        if address in seen or len(seen)>16 or address not in table:raise ValueError('Unresolved/cyclic application resource '+raw)
        kind,value,name=table[address]
        if kind==1:return resource('@'+hex(value),(*seen,address))
        if kind==3:return 'string',value
        if kind in (16,17):return 'int',value if value<1<<31 else value-(1<<32)
        if kind==18:return 'boolean',bool(value)
        raise ValueError('Unsupported application resource type '+str(kind))

    def typed(raw):
        if raw.startswith('"'):return 'string',json.loads(raw.split(' (Raw:',1)[0])
        if raw.startswith('@'):return resource(raw)
        match=re.fullmatch(r'\(type (0x[0-9a-f]+)\)(0x[0-9a-f]+)',raw)
        if not match:raise ValueError('Unsupported manifest metadata encoding '+raw)
        kind,value=int(match[1],16),int(match[2],16)
        if kind==18:return 'boolean',bool(value)
        if kind in (16,17):return 'int',value if value<1<<31 else value-(1<<32)
        raise ValueError('Unsupported application metadata type '+str(kind))

    rows=[];current=None;app=False
    for line in manifest.splitlines():
        if line.startswith('    E: application'):app=True
        elif line.startswith('    E: '):app=False
        if line.startswith('      E: '):
            if current:rows.append(current)
            current={} if app and line.startswith('      E: meta-data ') else None
        elif current is not None and line.startswith('        A: '):
            name,value=line.strip()[3:].split('=',1);current[name.split('(')[0]]=value
    if current:rows.append(current)
    output={}
    for row in rows:
        kind,name=typed(row['android:name'])
        if kind!='string' or name in output:raise ValueError('Invalid/duplicate application metadata key')
        if 'android:resource' in row:
            value=int(row['android:resource'][1:],16)
            if value>=1<<31:value-=1<<32
            item={'type':'int','value':value}
        else:
            kind,value=typed(row['android:value']);item={'type':kind,'value':value}
        output[name]=item
    return output


def read_application_metadata(apk,aapt):
    manifest=subprocess.check_output([str(aapt),'dump','xmltree',str(apk),'AndroidManifest.xml'],text=True)
    resources=subprocess.check_output([str(aapt),'dump','--values','resources',str(apk)],text=True)
    return parse_application_metadata(manifest,resources)
