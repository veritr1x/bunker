"""Derive the bounded MAIN/no-data activity-filter catalog from AAPT xmltree.

This is not an Android package installer. The consumer supports only explicit
current-package MAIN queries without data, MIME type or component. Unsupported
MAIN filter constructs fail preparation instead of producing an empty catalog.
"""
import json
import re
import subprocess


def _string(raw):
    if not raw.startswith('"'):raise ValueError('MAIN filter requires a literal string: '+raw)
    return json.loads(raw.split(' (Raw:',1)[0])


def _enabled(attributes):
    raw=attributes.get('android:enabled','(type 0x12)0xffffffff')
    match=re.fullmatch(r'\(type 0x12\)(0x[0-9a-f]+)',raw)
    if not match:raise ValueError('Unsupported component enabled encoding')
    return int(match[1],16)!=0


def parse_main_activity_filters(manifest,package):
    roots=[];stack=[]
    for line in manifest.splitlines():
        element=re.match(r'^( *)E: ([^ ]+)(?: |$)',line)
        if element:
            indent=len(element[1]);node={'kind':element[2],'attributes':{},'children':[]}
            while stack and stack[-1][0]>=indent:stack.pop()
            (stack[-1][1]['children'] if stack else roots).append(node);stack.append((indent,node))
        else:
            attribute=re.match(r'^( *)A: ([^=]+)=(.*)$',line)
            if attribute and stack:
                name=attribute[2].split('(')[0]
                if name in stack[-1][1]['attributes']:raise ValueError('Duplicate AAPT attribute')
                stack[-1][1]['attributes'][name]=attribute[3]
    applications=[n for root in roots for n in ([root] if root['kind']=='application' else root['children']) if n['kind']=='application']
    if len(applications)!=1:raise ValueError('Expected exactly one manifest application')
    application=applications[0];output=[]
    for activity in application['children']:
        if activity['kind'] not in ('activity','activity-alias'):continue
        for filter in activity['children']:
            if filter['kind']!='intent-filter':continue
            actions=[_string(n['attributes']['android:name']) for n in filter['children'] if n['kind']=='action']
            if 'android.intent.action.MAIN' not in actions:continue
            if activity['kind']!='activity':raise ValueError('MAIN activity aliases are not implemented')
            if any(n['kind'] not in ('action','category') for n in filter['children']):raise ValueError('MAIN data/unknown filter construct is unsupported')
            name=_string(activity['attributes']['android:name'])
            if name.startswith('.'):name=package+name
            elif '.' not in name:name=package+'.'+name
            categories=sorted({_string(n['attributes']['android:name']) for n in filter['children'] if n['kind']=='category'})
            output.append({'component':name,'enabled':_enabled(application['attributes']) and _enabled(activity['attributes']),'categories':categories})
    return output


def read_main_activity_filters(apk,aapt,package):
    manifest=subprocess.check_output([str(aapt),'dump','xmltree',str(apk),'AndroidManifest.xml'],text=True)
    return parse_main_activity_filters(manifest,package)
