"""What Carbon hotkeys and Quartz keyboard events actually do, checked against the real system
under the agent arrangement (the only arrangement): asyncio on cfloop's pump, owning the main
thread of a subprocess, with a worker thread pressing synthetic keys. A registered hotkey fires
from a *synthetic* keystroke, which is what lets this suite drive itself, and registration
needs no permission at all. Punctuation combos per DEV.md: F-keys silently eat synthetic
presses. `parse_combo` needs no engine, so it stays in-process."""

import subprocess, sys

from macmage import char2vk, parse_combo, specials


def test_parse_combo():
    "Combos name keys as typed on the current layout, with an escape hatch for raw key codes"
    vk_a = char2vk()['a']
    assert parse_combo('a') == (vk_a, 0)
    assert parse_combo('cmd-a') == (vk_a, 256)
    assert parse_combo('cmd-shift-a') == (vk_a, 256|512)
    assert parse_combo('command+shift+a') == (vk_a, 256|512)  # '+' and full names also work
    assert parse_combo('ctrl-space') == (specials['space'], 4096)
    assert parse_combo(f'cmd-<{vk_a}>') == (vk_a, 256)
    assert parse_combo('cmd--')[1] == 256  # '-' is a key as well as the separator


SCRIPT = r'''
import asyncio, threading, time
from macmage import holdmod, hotkey, leader, modkeys, parse_combo, press, run_loop, stop_keys, unhotkey, unleader, unwatch, watch
from macmage.keys import _mods_clear, _refs
from Quartz import (CGEventCreate, CGEventPost, CGEventSetFlags, CGEventSetIntegerValueField, CGEventSetType,
    kCGEventFlagsChanged, kCGHIDEventTap, kCGKeyboardEventKeycode)


def _wait(cond, secs=2):
    end = time.time()+secs
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    return False


def _mod_event(vk, flags):
    "Post a modifier change, the shape of event a real modifier key sends"
    ev = CGEventCreate(None)
    CGEventSetType(ev, kCGEventFlagsChanged)
    CGEventSetIntegerValueField(ev, kCGKeyboardEventKeycode, vk)
    CGEventSetFlags(ev, flags)
    CGEventPost(kCGHIDEventTap, ev)


def ok(name, cond): print(f'{name}: {"ok" if cond else "FAIL"}', flush=True)


def checks():
    time.sleep(0.5)

    # A registered handler runs once per press (and not on release)
    fired = []
    hotkey('ctrl-alt-cmd-;', lambda: fired.append(1))
    press('ctrl-alt-cmd-;')
    got_one = _wait(lambda: fired)
    time.sleep(0.3)
    ok('fires_once', got_one and len(fired)==1)

    # Re-registering replaces; unhotkey frees the combo for re-registration
    a, b = [], []
    hotkey('ctrl-alt-cmd-8', lambda: a.append(1))
    hotkey('ctrl-alt-cmd-8', lambda: b.append(1))
    press('ctrl-alt-cmd-8')
    replaced = _wait(lambda: b) and not a
    unhotkey('ctrl-alt-cmd-8')
    hotkey('ctrl-alt-cmd-8', lambda: a.append(1))
    press('ctrl-alt-cmd-8')
    ok('replace_release', replaced and _wait(lambda: a))
    unhotkey('ctrl-alt-cmd-8')

    # A press and its release dispatch separately
    updown = []
    hotkey('ctrl-alt-cmd-7', lambda: updown.append('down'), up=lambda: updown.append('up'))
    press('ctrl-alt-cmd-7')
    ok('up_handler', _wait(lambda: updown==['down','up']))
    unhotkey('ctrl-alt-cmd-7')

    # A `hold` async generator runs to its yield on press as a task and the rest on release;
    # awaiting in the body must not delay the release
    hgot, running = [], threading.Event()
    async def rec():
        hgot.append('start')
        running.set()
        await asyncio.sleep(0.3)  # a slow body is the point: it must not delay the release
        yield
        hgot.append('stop')
    hotkey('ctrl-alt-cmd-6', rec, hold=True)
    press('ctrl-alt-cmd-6')
    ok('hold', _wait(lambda: hgot==['start','stop']) and running.is_set())
    unhotkey('ctrl-alt-cmd-6')

    # The leader binds its keys, the captured key runs its handler, and the keys are released
    lgot = []
    leader('ctrl-alt-cmd-9', {'8': lambda: lgot.append('eight')}, timeout=5)
    press('ctrl-alt-cmd-9')
    bound = _wait(lambda: '8' in _refs)
    press('8')
    ok('leader', bound and _wait(lambda: lgot==['eight']) and _wait(lambda: '8' not in _refs))
    unleader('ctrl-alt-cmd-9')

    # A mode nobody answers releases its keys
    leader('ctrl-alt-cmd-9', {'8': lambda: None}, timeout=0.5)
    press('ctrl-alt-cmd-9')
    ok('leader_timeout', _wait(lambda: '8' in _refs) and _wait(lambda: '8' not in _refs))
    unleader('ctrl-alt-cmd-9')

    # A listen tap reports key events, including combos our own hotkey claims and suppresses
    seen, wfired = [], []
    w = watch(lambda kind, vk, flags: seen.append((kind, vk)))
    hotkey('ctrl-alt-cmd-0', lambda: wfired.append(1))
    press('ctrl-alt-cmd-0')
    vk = parse_combo('ctrl-alt-cmd-0')[0]
    ok('watch', _wait(lambda: wfired) and _wait(lambda: ('down', vk) in seen) and ('up', vk) in seen)
    unhotkey('ctrl-alt-cmd-0')
    unwatch(w)

    # holdmod reads both edges of a bare modifier from the tap
    mvk, devmask = modkeys['ropt']
    mgot = []
    holdmod('ropt', lambda: mgot.append('down'), up=lambda: mgot.append('up'))
    _mod_event(mvk, devmask)
    down_ok = _wait(lambda: mgot==['down'])
    _mod_event(mvk, 0)
    ok('holdmod', down_ok and _wait(lambda: mgot==['down','up']) and _wait(_mods_clear))


def worker():
    try: checks()
    except Exception:
        import traceback
        traceback.print_exc()
    finally: stop_keys()


run_loop(lambda: threading.Thread(target=worker, daemon=True).start())
print('clean exit', flush=True)
'''

MARKERS = ['fires_once', 'replace_release', 'up_handler', 'hold', 'leader', 'leader_timeout', 'watch', 'holdmod']


def test_keys_semantics():
    "Every hotkey, hold, leader, watch, and holdmod behavior, in one agent-arrangement subprocess"
    r = subprocess.run([sys.executable, '-c', SCRIPT], capture_output=True, text=True, timeout=15)
    for m in MARKERS: assert f'{m}: ok' in r.stdout, r.stdout + r.stderr
    assert 'clean exit' in r.stdout, r.stdout + r.stderr
