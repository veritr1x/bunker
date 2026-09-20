#!/usr/bin/env python3
"""Integration test on copies of private game inputs; requires a save with user 1.

Install the Android Python requirements plus httpx in a host Python 3.11 venv.
No input save, master or resource bundle is modified. The Go bridge is built
under server/tmp and the isolated database and catalogs are removed afterwards.
"""
from pathlib import Path
import argparse
import sys, shutil, subprocess, os, json, sqlite3, tempfile, contextlib

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--save', type=Path, required=True)
parser.add_argument('--assets', type=Path, required=True, help='Prepared assets directory')
parser.add_argument('--master', type=Path, required=True, help='Active patched master')
parser.add_argument('--original-master', type=Path, required=True)
args = parser.parse_args()
for name in ('save', 'assets', 'master', 'original_master'):
    setattr(args, name, getattr(args, name).resolve(strict=True))
sys.path.insert(0, str(root/'android/app/src/main/python'))
(root/'server/tmp').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='lunar-tools-') as work, tempfile.TemporaryDirectory(prefix='editor-test-', dir=root/'server/tmp') as bridge:
    fixture=Path(work)
    bridge=Path(bridge)
    (bridge/'main.go').write_text('package main\nimport("fmt";"io";"os";"lunar-tear/server/mobile")\nfunc main(){raw,_:=io.ReadAll(os.Stdin);fmt.Print(mobile.Edit(os.Args[1],os.Args[2],string(raw)))}\n')
    probe=fixture/'edit-probe'
    subprocess.run(['go','build','-o',str(probe),str(bridge/'main.go')],cwd=root/'server',check=True)
    data=fixture/'saves'; data.mkdir()
    # SQLite backup also copies committed WAL content from the supplied save.
    with contextlib.closing(sqlite3.connect(f'file:{args.save}?mode=ro', uri=True)) as source:
        with contextlib.closing(sqlite3.connect(data/'game.db')) as target:
            source.backup(target)
    server=fixture/'server'; assets=server/'assets'
    (assets/'release').mkdir(parents=True)
    shutil.copyfile(args.master, assets/'release/20240404193219.bin.e')
    (assets/'revisions').symlink_to(args.assets/'revisions', target_is_directory=True)
    import android_runtime
    native=lambda d,a,r:subprocess.check_output([str(probe),d,a],input=r.encode()).decode()
    config=android_runtime.configure(data,server,fixture/'tools',native,print)
    android_runtime.prepare_data()
    from android_patcher import folder
    shutil.copyfile(args.original_master, folder()/'origin.bin.e')
    from fastapi.testclient import TestClient
    client=TestClient(android_runtime.create_app('test-token','http://127.0.0.1:8888'),base_url='http://127.0.0.1:8888')
    assert client.get('/').status_code==403
    client.cookies.set('lunar_tools','test-token')
    for path in ['/','/patcher','/backups','/users','/items','/costumes','/weapons','/upgrades','/memoirs']:
        response=client.get(path)
        print(path,response.status_code,len(response.content),response.url,flush=True)
        if response.status_code!=200:print(response.text[:2000])
        assert response.status_code==200
        assert '?error=' not in str(response.url),response.url
    assert client.post('/backups/create',headers={'Origin':'http://evil.example'}).status_code==403
    from web.services import backup_service
    def gems():
        with sqlite3.connect(data/'game.db') as db:
            return db.execute('SELECT free_gem FROM user_gem WHERE user_id=1').fetchone()[0]
    initial_gems = gems()
    before=backup_service.create_backup()
    response=client.post('/users/1/edit/items/grant',json={'possession_type':12,'possession_id':0,'count':1})
    print('Grant',response.status_code,response.text,flush=True)
    assert response.json()['ok']
    assert gems() == initial_gems + 1
    assert len(backup_service.list_backups())>=2
    backup_service.restore_backup(before.filename)
    assert gems() == initial_gems
    print('Backup and restore passed',flush=True)
    from web.services import costume_service,weapon_service,memoir_service,userdata_service

    def post(path, payload=None):
        response=client.post(path,json=payload or {})
        print('EDIT',path,response.status_code,response.text[:300],flush=True)
        assert response.status_code==200 and response.json()['ok'],response.text
        return response.json()

    costume=next(c for c in costume_service.get_catalog() if c.rarity==40 and c.id not in userdata_service.get_owned_costume_ids(1))
    post('/users/1/edit/costumes/grant_batch',{'costume_ids':[costume.id]})
    weapon=next(w for w in weapon_service.get_catalog() if w.id not in userdata_service.get_owned_weapon_ids(1))
    post('/users/1/edit/weapons/grant_batch',{'weapon_ids':[weapon.id]})
    for operation in ['grant_missing_companions','grant_missing_thoughts','exalt_all','fill_mythic_slabs','upgrade_all_companions','upgrade_all_weapons','upgrade_all_costumes','fill_karma_slots','skip_dark_memory_cutscenes']:
        post('/users/1/upgrades/'+operation)
    post('/users/1/memoirs/grant_set',{'set_id':1,'memoirs':[{'group_id':i,'primary_key':'crit_rate','subs':[{'slot':1,'sub_key':'atk_flat','value':600}]} for i in (1,2,3)]})
    post('/users/1/memoirs/upgrade_all')
    with sqlite3.connect(data/'game.db') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        uuid=db.execute('SELECT user_parts_uuid FROM user_parts WHERE user_id=1 ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    post('/users/1/memoirs/fix_slots',{'user_parts_uuid':uuid,'subs':[{'slot':1,'sub_key':'atk_pct','value':125}]})
    backup_service.restore_backup(before.filename)
    print('All editor categories and restore passed',flush=True)

    # Real engine boundary check: a rejected batch must not partially add gems.
    cap_backup = backup_service.create_backup()
    def engine(payload):
        return json.loads(native(str(data), str(server), json.dumps({'user_id':1, **payload})))
    assert engine({'action':'grant_possession','possession_type':12,'possession_id':0,'count':2_000_000_000-initial_gems})['ok']
    assert gems() == 2_000_000_000
    assert not engine({'action':'grant_possession','possession_type':11,'possession_id':0,'count':200_000_000})['ok']
    response = engine({'action':'grant_batch','grants':[
        {'possession_type':11,'possession_id':0,'count':1},
        {'possession_type':12,'possession_id':0,'count':100_000_000},
        {'possession_type':12,'possession_id':99,'count':100_000_000}]})
    assert not response['ok'] and 'inventory limit' in response['error'], response
    assert gems() == 2_000_000_000
    with sqlite3.connect(data/'game.db') as check, sqlite3.connect(config.BACKUP_DIR/cap_backup.filename) as prior:
        assert check.execute('SELECT paid_gem FROM user_gem WHERE user_id=1').fetchone() == prior.execute('SELECT paid_gem FROM user_gem WHERE user_id=1').fetchone()
    backup_service.restore_backup(cap_backup.filename)
    assert gems() == initial_gems
    print('Oversized batch rejected without partial grants', flush=True)
    response=client.post('/patcher/apply',data={'preset':'Clear'})
    print('PATCH',response.status_code,response.url,flush=True)
    assert response.status_code==200 and '?error=' not in str(response.url),str(response.url)
    from android_patcher import master_history
    response=client.post('/patcher/restore',data={'filename':master_history()[0].name})
    assert response.status_code==200 and '?error=' not in str(response.url),str(response.url)
    assert (assets/'release/20240404193219.bin.e').read_bytes()==args.master.read_bytes()
    print('Preset application and master rollback passed',flush=True)

    config.BACKUP_RETENTION = 3
    oldest = backup_service.create_backup()
    post('/users/1/edit/items/grant', {'possession_type':12,'possession_id':0,'count':7})
    backup_service.create_backup()
    assert oldest.filename in [item.filename for item in backup_service.list_backups()]
    response = client.post('/backups/restore', data={'filename':oldest.filename,'confirm':'RESTORE'})
    assert '?error=' not in str(response.url), response.url
    assert gems() == initial_gems
    assert len(backup_service.list_backups()) == 3
    assert not (config.DATA_DIR/'restore-selected.db').exists()
    print('Oldest retained backup restores safely', flush=True)

    from android_patcher import activate
    from unittest.mock import patch
    master_path = config.find_master_data_bin()
    prior_master = master_path.read_bytes()
    candidate = fixture/'candidate.bin.e'
    candidate.write_bytes(prior_master)
    with patch.object(android_runtime, 'prepare_data', side_effect=[RuntimeError('injected catalog failure'), None]) as rebuild:
        try:
            activate(candidate, 'must not activate')
            raise AssertionError('Activation unexpectedly succeeded')
        except RuntimeError as error:
            assert str(error) == 'injected catalog failure'
        assert rebuild.call_count == 2
    assert master_path.read_bytes() == prior_master
    print('Failed activation restores the prior master and rebuilds its catalog', flush=True)
