#!/usr/bin/env python3
"""Original calendar on copies of private game inputs: switch on, next update,
speed, jump preview, a loop ending and switching off.

Install the Android Python requirements plus httpx in a host Python 3.11 venv.
No input is modified; everything runs in a temporary folder.
"""
from pathlib import Path
import argparse, contextlib, json, re, shutil, sqlite3, sys, tempfile

if __name__ != '__main__':  # unittest discovery imports it: it needs private inputs
    import unittest
    raise unittest.SkipTest('integration script: run it directly with --save, --assets and --original-master')
root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--save', type=Path, required=True)
parser.add_argument('--assets', type=Path, required=True, help='Assets directory with revisions/')
parser.add_argument('--original-master', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(root / 'android/app/src/main/python'))

with tempfile.TemporaryDirectory(prefix='calendar-') as work:
    work = Path(work)
    data = work / 'saves'
    data.mkdir()
    with contextlib.closing(sqlite3.connect(f'file:{args.save}?mode=ro', uri=True)) as source, contextlib.closing(sqlite3.connect(data / 'game.db')) as target:
        source.backup(target)
    server = work / 'server'
    (server / 'assets/release').mkdir(parents=True)
    shutil.copyfile(args.original_master, server / 'assets/release/20240404193219.bin.e')
    (server / 'assets/revisions').symlink_to(args.assets.resolve() / 'revisions', target_is_directory=True)
    import android_runtime
    android_runtime.configure(data, server, work / 'tools', lambda *a: '{}', print)
    android_runtime.prepare_data()
    from android_patcher import folder
    shutil.copyfile(args.original_master, folder() / 'origin.bin.e')
    import android_calendar as cal
    from fastapi.testclient import TestClient
    client = TestClient(android_runtime.create_app('t', 'http://127.0.0.1:8888'), base_url='http://127.0.0.1:8888')
    client.cookies.set('lunar_tools', 't')

    def page(path, data=None):
        response = client.post(path, data=data) if data is not None else client.get(path)
        assert response.status_code == 200, (path, response.status_code, response.text[:500])
        assert 'ERROR' not in response.text, re.findall(r'ERROR ::[^<]*', response.text)
        return response

    assert 'Start calendar' in page('/patcher').text
    page('/patcher/calendar/on', {})
    state = json.loads((data / 'calendar.json').read_text())
    assert state['loop'] == 1 and (server / 'assets/release' / state['next']).exists(), state
    print('Calendar on, loop 1 week', cal.week_of(state, cal.game_now(state)))

    target = int(re.search(r'name="target" value="(\d+)"', page('/patcher/calendar/next').text).group(1))
    page('/patcher/calendar/jump', {'target': str(target)})
    state = cal.read_state()
    assert state['jumpMillis'] % cal.DAY == 0 and cal.game_now(state) >= target, state
    print('Next update: moved', state['jumpMillis'] // cal.DAY, 'days')

    page('/patcher/calendar/speed', {'speed': '7'})
    state = cal.read_state()
    assert state['speed'] == 7 and cal.auto_weeks(state, state['speedSince'] + 7 * cal.DAY + 1) == 6, state
    page('/patcher/calendar/jump?at=%d' % (cal.game_now(state) + 20 * cal.WEEK))
    print('Speed 7x and the jump preview passed')

    # Past the end of the loop the page starts loop 2 and builds loop 3 ahead.
    state['jumpMillis'] += 150 * cal.WEEK
    cal.write_state(state)
    assert 'Loop 2 started' in page('/patcher').text
    state = cal.read_state()
    assert state['loop'] == 2 and state['nextLoop'] == 3 and cal.week_of(state, cal.game_now(state)) < cal.LOOP_WEEKS, state
    print('Loop end starts loop 2')

    page('/patcher/calendar/off', {})
    assert not (data / 'calendar.json').exists() and 'Start calendar' in page('/patcher').text
    print('Calendar off passed')
