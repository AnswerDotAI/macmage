"""What Carbon hotkeys and Quartz keyboard events actually do, checked against the real system.

These run against live macOS APIs rather than fakes, so they double as a record of behaviour
that is hard to discover: a registered hotkey fires from a *synthetic* keystroke, which is what
lets this suite drive itself, and registration needs no permission at all.

Test order matters and is itself a regression test: building the layout map used to poison
Carbon hotkey dispatch for the rest of the process, so `test_parse_combo` deliberately runs
before the hotkey test (see DEV.md).
"""

import threading, time

from Quartz import (CGEventCreate, CGEventPost, CGEventSetFlags, CGEventSetIntegerValueField, CGEventSetType,
    kCGEventFlagsChanged, kCGHIDEventTap, kCGKeyboardEventKeycode)

from macmage import char2vk, holdmod, hotkey, leader, modkeys, parse_combo, press, specials, unholdmod, unhotkey, unleader, unwatch, watch
from macmage.keys import _mods_clear, _refs


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


def test_hotkey_fires_from_synthetic_keystroke():
    "A registered handler runs once per press (and not on release), including when we press it ourselves"
    fired = []
    hotkey('ctrl-alt-cmd-;', lambda: fired.append(1))
    press('ctrl-alt-cmd-;')
    assert _wait(lambda: fired), 'hotkey handler did not run'
    time.sleep(0.3)
    assert len(fired)==1, 'handler ran more than once for a single press'


def _wait(cond):
    for _ in range(40):
        if cond(): return True
        time.sleep(0.05)
    return False


def test_hotkey_replace_and_release():
    "Re-registering a combo replaces its handler; `unhotkey` frees the combo for later re-registration"
    a, b = [], []
    hotkey('ctrl-alt-cmd-8', lambda: a.append(1))
    hotkey('ctrl-alt-cmd-8', lambda: b.append(1))
    press('ctrl-alt-cmd-8')
    assert _wait(lambda: b), 'replacement handler did not run'
    assert not a, 'replaced handler still ran'
    unhotkey('ctrl-alt-cmd-8')
    hotkey('ctrl-alt-cmd-8', lambda: a.append(1))
    press('ctrl-alt-cmd-8')
    assert _wait(lambda: a), 'combo did not work after unhotkey and re-register'
    unhotkey('ctrl-alt-cmd-8')


# The mode's keys are pressed only while the mode holds them, since a hotkey suppresses the
# keystroke and a bare key pressed outside a mode would type into whatever has focus.
def test_leader_captures_the_next_key():
    "The leader binds its keys, the key it captures runs its handler, and the keys are released again"
    got = []
    leader('ctrl-alt-cmd-9', {'8': lambda: got.append('eight')}, timeout=5)
    press('ctrl-alt-cmd-9')
    assert _wait(lambda: '8' in _refs), 'the mode did not bind its keys'
    press('8')
    assert _wait(lambda: got == ['eight']), f'the captured key did not run its handler, got {got}'
    assert _wait(lambda: '8' not in _refs), 'the mode did not release its keys'
    unleader('ctrl-alt-cmd-9')


def test_leader_times_out():
    "A mode nobody answers releases its keys, so the keyboard is never left captured"
    leader('ctrl-alt-cmd-9', {'8': lambda: None}, timeout=0.5)
    press('ctrl-alt-cmd-9')
    assert _wait(lambda: '8' in _refs), 'the mode did not bind its keys'
    assert _wait(lambda: '8' not in _refs), 'the mode did not time out'
    unleader('ctrl-alt-cmd-9')


def test_watch_sees_keystrokes():
    "A listen tap reports key events, including combos our own hotkey claims and suppresses"
    seen, fired = [], []
    w = watch(lambda kind, vk, flags: seen.append((kind, vk)))
    hotkey('ctrl-alt-cmd-0', lambda: fired.append(1))
    press('ctrl-alt-cmd-0')
    assert _wait(lambda: fired), 'hotkey handler did not run alongside the tap'
    vk = parse_combo('ctrl-alt-cmd-0')[0]
    assert _wait(lambda: ('down', vk) in seen), 'tap did not see the keydown'
    assert ('up', vk) in seen, 'tap did not see the keyup'
    unhotkey('ctrl-alt-cmd-0')
    unwatch(w)


def test_hotkey_up_handler():
    "A press and its release dispatch separately, so a handler can run on key-up"
    got = []
    hotkey('ctrl-alt-cmd-7', lambda: got.append('down'), up=lambda: got.append('up'))
    press('ctrl-alt-cmd-7')
    assert _wait(lambda: got==['down','up']), f'expected a down then an up, got {got}'
    unhotkey('ctrl-alt-cmd-7')


def test_hold_generator():
    "A `hold` handler runs up to its `yield` on press and the rest on release, on its own thread so a slow body cannot delay the release"
    got, running = [], threading.Event()
    @hotkey('ctrl-alt-cmd-6', hold=True)
    def rec():
        got.append('start')
        running.set()
        time.sleep(0.3)  # a blocking body is the whole point: recording lasts as long as the key is held
        yield
        got.append('stop')
    press('ctrl-alt-cmd-6')
    assert _wait(lambda: got==['start','stop']), f'expected start then stop, got {got}'
    assert running.is_set()
    unhotkey('ctrl-alt-cmd-6')


def _mod_event(vk, flags):
    "Post a modifier change, the shape of event a real modifier key sends"
    ev = CGEventCreate(None)
    CGEventSetType(ev, kCGEventFlagsChanged)
    CGEventSetIntegerValueField(ev, kCGKeyboardEventKeycode, vk)
    CGEventSetFlags(ev, flags)
    CGEventPost(kCGHIDEventTap, ev)


def test_holdmod_derives_both_edges_of_a_bare_modifier():
    "Carbon cannot register a bare modifier, so `holdmod` reads the tap: a modifier change carries the key's own code, and its device-specific flag bit says which way it went"
    vk, devmask = modkeys['ropt']
    got = []
    holdmod('ropt', lambda: got.append('down'), up=lambda: got.append('up'))
    _mod_event(vk, devmask)
    assert _wait(lambda: got==['down']), f'expected a down, got {got}'
    _mod_event(vk, 0)
    assert _wait(lambda: got==['down','up']), f'expected a down then an up, got {got}'
    unholdmod('ropt')
    assert _wait(_mods_clear), 'the test left a modifier held down'
