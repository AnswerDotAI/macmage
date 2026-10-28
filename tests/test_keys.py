"Keyboard handlers share the agent's loop; synthetic presses exercise the real Carbon and Quartz boundary."
import asyncio, subprocess, sys, threading, time
from pathlib import Path

from Quartz import (CGEventCreate, CGEventPost, CGEventSetFlags, CGEventSetIntegerValueField, CGEventSetType,
    kCGEventFlagsChanged, kCGHIDEventTap, kCGKeyboardEventKeycode)
from macmage import (char2vk, holdmod, hotkey, leader, mage, modkeys, mods_clear, parse_combo, press, run_loop, snap, specials,
    stop_keys, unholdmod, unhotkey, unleader, unwatch, wait_until, watch)
from macmage.keys import _refs


def test_combo_syntax():
    vk = char2vk()['a']
    assert parse_combo('a') == (vk, 0)
    assert parse_combo('cmd-a') == (vk, 256)
    assert parse_combo('cmd-shift-a') == parse_combo('command+shift+a') == (vk, 256|512)
    assert parse_combo('ctrl-space') == (specials['space'], 4096)
    assert parse_combo(f'cmd-<{vk}>') == (vk, 256)
    assert parse_combo('cmd--') == (char2vk()['-'], 256)


def _modifier(vk, flags):
    ev = CGEventCreate(None)
    CGEventSetType(ev, kCGEventFlagsChanged)
    CGEventSetIntegerValueField(ev, kCGKeyboardEventKeycode, vk)
    CGEventSetFlags(ev, flags)
    CGEventPost(kCGHIDEventTap, ev)


def _story(loop, path):
    time.sleep(0.5)
    got = []
    @mage(keys='ctrl-alt-cmd-;')
    def handler(): got.append('sync')
    press('ctrl-alt-cmd-;')
    assert wait_until(lambda: got == ['sync'], 2)
    time.sleep(0.3)
    assert got == ['sync']

    @mage
    async def replacement():
        await asyncio.sleep(0)
        got.append('async')
    hotkey('ctrl-alt-cmd-;', replacement)
    press('ctrl-alt-cmd-;')
    assert wait_until(lambda: got == ['sync', 'async'], 2)
    unhotkey('ctrl-alt-cmd-;')
    hotkey('ctrl-alt-cmd-;', handler, up=lambda: got.append('up'))
    press('ctrl-alt-cmd-;')
    assert wait_until(lambda: got[-2:] == ['sync', 'up'], 2)
    unhotkey('ctrl-alt-cmd-;')

    held = []
    @mage(keys='ctrl-alt-cmd-6', hold=True)
    async def hold():
        held.append('start')
        await asyncio.sleep(0.3)  # release must not be lost while the press body awaits
        yield
        held.append('stop')
    press('ctrl-alt-cmd-6')
    assert wait_until(lambda: held == ['start', 'stop'], 2)
    unhotkey('ctrl-alt-cmd-6')

    leader('ctrl-alt-cmd-9', {'8': lambda: got.append('leader')})
    press('ctrl-alt-cmd-9')
    assert wait_until(lambda: '8' in _refs, 2)
    press('8')
    assert wait_until(lambda: got[-1] == 'leader', 2)
    assert wait_until(lambda: '8' not in _refs, 2)
    unleader('ctrl-alt-cmd-9')
    leader('ctrl-alt-cmd-9', {'8': lambda: None}, timeout=0.5)
    press('ctrl-alt-cmd-9')
    assert wait_until(lambda: '8' in _refs, 2)
    assert wait_until(lambda: '8' not in _refs, 2)
    unleader('ctrl-alt-cmd-9')

    seen = []
    watcher = watch(lambda kind, vk, flags: seen.append(kind))
    hotkey('ctrl-alt-cmd-0', lambda: got.append('watched'))
    press('ctrl-alt-cmd-0')
    assert wait_until(lambda: got[-1] == 'watched' and 'down' in seen and 'up' in seen, 2)
    unhotkey('ctrl-alt-cmd-0')
    unwatch(watcher)

    edges = []
    vk, mask = modkeys['ropt']
    holdmod('ropt', lambda: edges.append('down'), up=lambda: edges.append('up'))
    _modifier(vk, mask)
    assert wait_until(lambda: edges == ['down'], 2)
    _modifier(vk, 0)
    assert wait_until(lambda: edges == ['down', 'up'], 2)
    assert wait_until(mods_clear, 2)
    unholdmod('ropt')

    photo = asyncio.run_coroutine_threadsafe(snap(path/'photo.jpg'), loop).result(10)
    assert photo.stat().st_size > 10000


def test_keyboard_story(tmp_path):
    r = subprocess.run([sys.executable, __file__, str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout+r.stderr


if __name__ == '__main__':
    errors = []
    def setup():
        loop = asyncio.get_running_loop()
        def worker():
            try: _story(loop, Path(sys.argv[1]))
            except BaseException as e: errors.append(e)
            finally: stop_keys()
        threading.Thread(target=worker, daemon=True).start()
    run_loop(setup)
    if errors: raise errors[0]
