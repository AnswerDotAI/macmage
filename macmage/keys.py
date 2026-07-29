"Global hotkeys through Carbon, and synthetic typing through Quartz"

from fastcore.utils import *
from fastcore.xdg import xdg_cache_home
import asyncio, atexit, cfloop, inspect, json, objc, re, struct, subprocess, sys, threading, time, traceback
from Quartz import (CFMachPortCreateRunLoopSource, CFRunLoopAddSource, CFRunLoopGetCurrent, CFRunLoopRun, CFRunLoopStop,
    CGEnableEventStateCombining, CGEventCreateKeyboardEvent, CGEventGetFlags, CGEventGetIntegerValueField, CGEventKeyboardSetUnicodeString,
    CGEventMaskBit, CGEventPost, CGEventSetFlags, CGEventSourceFlagsState, CGEventTapCreate, CGEventTapEnable, kCFRunLoopCommonModes,
    kCGEventFlagMaskAlternate, kCGEventFlagMaskCommand, kCGEventFlagMaskControl, kCGEventFlagMaskShift,
    kCGEventFlagsChanged, kCGEventKeyDown, kCGEventKeyUp, kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput,
    kCGEventSourceStateHIDSystemState, kCGEventTapOptionListenOnly, kCGHIDEventTap, kCGHeadInsertEventTap, kCGKeyboardEventKeycode, kCGSessionEventTap)

from ._hitoolbox import (EventTypeSpec, GetEventDispatcherTarget, GetEventKind, GetEventParameter, InstallEventHandler,
    RegisterEventHotKey, UnregisterEventHotKey, kEventClassKeyboard,
    kEventHotKeyPressed, kEventHotKeyReleased, kEventParamDirectObject, typeEventHotKeyID)
from .imp import need, aneed
from .util import wait_until

__all__ = ['mods', 'specials', 'char2vk', 'parse_combo', 'hotkey', 'unhotkey', 'leader', 'unleader', 'watch', 'unwatch', 'modkeys', 'holdmod', 'unholdmod', 'press', 'stop_keys', 'run_loop', 'type_text']

mods = dict(cmd=256, command=256, shift=512, opt=2048, option=2048, alt=2048, ctrl=4096, control=4096)

specials = dict(space=49, escape=53, esc=53, tab=48, enter=36, ret=36, delete=51, backspace=51, forwarddelete=117,
    home=115, end=119, pageup=116, pagedown=121, left=123, right=124, down=125, up=126,
    f1=122, f2=120, f3=99, f4=118, f5=96, f6=97, f7=98, f8=100, f9=101, f10=109, f11=103, f12=111)

_ADHOC_ERR = -9878 # eventHotKeyExistsErr
_SIG = struct.unpack('@I', b'IMPK')[0]
_cgflags = {256: kCGEventFlagMaskCommand, 512: kCGEventFlagMaskShift,
    2048: kCGEventFlagMaskAlternate, 4096: kCGEventFlagMaskControl}


def _mods_clear():
    "Whether no modifier key is physically held right now"
    return not CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState) & sum(_cgflags.values())


CGEnableEventStateCombining(False)  # else a posted event inherits whatever modifiers are physically held, so typing while the triggering hotkey is still down sends the wrong keys

_layout_src = r'''import json
from Quartz import CGEventCreateKeyboardEvent, CGEventKeyboardGetUnicodeString
res = {}
for vk in range(128):
    ev = CGEventCreateKeyboardEvent(None, vk, True)
    if ev is None: continue
    n, chars = CGEventKeyboardGetUnicodeString(ev, 8, None, None)
    if n==1 and chars.isprintable(): res.setdefault(chars.lower(), vk)
print(json.dumps(res))'''


_layout_cache = xdg_cache_home()/'macmage'/'layout.json'


def _query_layout():
    # Runs in a child process: in-process CGEvent keyboard translation silently breaks Carbon hotkey dispatch (see DEV.md)
    r = subprocess.run([sys.executable, '-c', _layout_src], capture_output=True, text=True, check=True)
    res = json.loads(r.stdout)
    return res if 'a' in res and len(res)>40 else None  # partial maps can keep letters yet drop punctuation (see DEV.md)


@functools.cache
def char2vk():
    "Map each character to its key code on the current keyboard layout, so combos name keys as typed"
    res = wait_until(_query_layout, 2.4, 0.3)
    if res:
        _layout_cache.parent.mkdir(parents=True, exist_ok=True)
        _layout_cache.write_text(json.dumps(res))
        return res
    if _layout_cache.exists(): return json.loads(_layout_cache.read_text())
    raise RuntimeError('Keyboard layout query keeps returning a partial map; can happen transiently just after login')


_modre = re.compile('(' + '|'.join(mods) + r')[-+]', re.I)


def parse_combo(
    combo:str # e.g. `'cmd-alt-`'`, `'ctrl-shift-space'`, or `'cmd-<50>'` to give a key code directly
):
    "Parse `combo` into its `(key code, modifier mask)` pair"
    mask, rest = 0, combo
    while (m := _modre.match(rest)):
        mask |= mods[m[1].lower()]
        rest = rest[m.end():]
    if not rest: raise ValueError(f'No key in combo {combo!r}')
    if vk := re.fullmatch(r'<(\d+)>', rest): return int(vk[1]), mask
    if rest.lower() in specials: return specials[rest.lower()], mask
    vk = char2vk().get(rest.lower())
    if vk is None: raise ValueError(f'{rest!r} is not a key on the current keyboard layout')
    return vk, mask


_handlers, _refs, _lock = {}, {}, threading.Lock()
_next_id, _started, _tap_started, _handler_ref, _cb = 0, False, False, None, None
_loop, _stop = None, None


def _handle(callref, event, void):
    "Carbon handler: look up this combination's press or release function and dispatch it"
    try:
        res, atype, asize, param = GetEventParameter(event, kEventParamDirectObject, typeEventHotKeyID, None, 8, None, None)
        _sig, hkid = struct.unpack('@II', param)
        down, up = _handlers.get(hkid, (None, None))
        if (fn := down if GetEventKind(event)==kEventHotKeyPressed else up): _dispatch(fn)
    except Exception: traceback.print_exc()
    return 0


async def _alogged(fn, *args):
    try: await fn(*args)
    except Exception: traceback.print_exc()


def _dispatch(fn, *args):
    "Run a handler on the agent's loop: async ones as tasks, sync ones inline (so they should stay quick)"
    if inspect.iscoroutinefunction(fn): (_loop or asyncio.get_running_loop()).create_task(_alogged(fn, *args))
    else:
        try: fn(*args)
        except Exception: traceback.print_exc()


def stop_keys():
    "Shut down the keyboard engine, releasing every hotkey and ending the loop and tap. Runs at exit; call it yourself before `os.exec*`, which skips atexit (see DEV.md)"
    for combo in list(_refs): unhotkey(combo)
    _quit_loop()
    if _tap: CGEventTapEnable(_tap, False)
    if _tap_rl: CFRunLoopStop(_tap_rl)
    if _tap_thread: _tap_thread.join(1)


def _quit_loop():
    "Signal the agent loop to end, from any thread"
    if _loop is not None: _loop.call_soon_threadsafe(_stop.set)


def _start():
    "Install the Carbon handler, once per process; hotkeys dispatch on the agent loop, so one must be running"
    global _started, _handler_ref, _cb
    if _started: return
    if _loop is None: raise RuntimeError('hotkeys need the agent loop running: wrap your program in run_loop(...) (see README)')
    @objc.callbackFor(InstallEventHandler)
    def _cb(callref, event, void): return _handle(callref, event, void)
    specs = [EventTypeSpec(eventClass=kEventClassKeyboard, eventKind=o) for o in (kEventHotKeyPressed, kEventHotKeyReleased)]
    res, _handler_ref = InstallEventHandler(GetEventDispatcherTarget(), _cb, 2, specs, None, None)
    if res: raise RuntimeError(f'InstallEventHandler failed: {res}')
    atexit.register(stop_keys)
    _started = True


def run_loop(
    setup:callable=None # Runs once the loop is up, so its registrations dispatch there
):
    "Run the agent arrangement until `stop_keys`: a stock asyncio loop on cfloop's Carbon-pumping selector owns the calling thread, so hotkeys dispatch there, async handlers run as tasks, and main-queue delegates drain during every idle wait (see DEV.md)"
    cfloop.run(_agent(setup))


async def _agent(setup):
    global _loop, _stop
    _loop, _stop = asyncio.get_running_loop(), asyncio.Event()
    try:
        if setup: setup()
        await _stop.wait()
    finally: _loop = None


def _hold_pair(fn):
    "Split async generator `fn` into press and release handlers: it runs as a task, pausing at `yield` until the key comes up"
    waiting = []
    def _press():
        ev = asyncio.Event()
        waiting.append(ev)
        async def _run():
            try:
                agen = fn()
                await anext(agen)
                await ev.wait()
                await anext(agen, None)
            except Exception: traceback.print_exc()
        _loop.create_task(_run())
    def _release():
        if waiting: waiting.pop(0).set()
    return _press, _release


def _pair(fn, up, hold):
    "The (press, release) pair for a handler, splitting a `hold` async generator into one"
    if not hold: return fn, up
    if up: raise ValueError('A `hold` handler resumes on release, so it cannot also take `up`')
    if not inspect.isasyncgenfunction(fn):
        raise ValueError(f'A `hold` handler needs `async def` with a `yield`: {fn.__name__} is not an async generator function')
    return _hold_pair(fn)


def hotkey(
    combo:str, # Key combination, e.g. `'cmd-alt-`'`
    fn:callable=None, # Handler to run on press; omit to use as a decorator
    up:callable=None, # Handler to run on release; omit to ignore releases
    hold:bool=False # Take `fn` as a generator: the body before `yield` runs on press and the rest on release
):
    "Run `fn` whenever `combo` is pressed, anywhere. Needs no permissions, and suppresses the keystroke"
    if fn is None: return partial(hotkey, combo, up=up, hold=hold)
    down, up = _pair(fn, up, hold)
    vk, mask = parse_combo(combo)
    if combo in _refs: unhotkey(combo)
    global _next_id
    with _lock:
        _next_id += 1
        hkid = _next_id
        res, ref = RegisterEventHotKey(vk, mask, (_SIG, hkid), GetEventDispatcherTarget(), 0, None)
        if res:
            hint = ' (another application already claims it)' if res==_ADHOC_ERR else ''
            raise RuntimeError(f'Could not register {combo!r}: error {res}{hint}')
        _handlers[hkid], _refs[combo] = (down, up), (hkid, ref)
    _start()
    return fn


def unhotkey(
    combo:str # A combination previously passed to `hotkey`
):
    "Release `combo`, so the keystroke reaches applications again"
    with _lock:
        hkid, ref = _refs.pop(combo)
        UnregisterEventHotKey(ref)
        del _handlers[hkid]


_modes = {}


def leader(
    combo:str, # Combination that enters the mode
    keymap:dict, # Single keys, named as `parse_combo` names them, to the handlers they run
    timeout:float=3 # Seconds to wait for a key before leaving the mode
):
    "Bind `combo` to capture the next keystroke: it runs that key's handler from `keymap`, then releases the keys again"
    def _enter():
        if combo in _modes: return
        bound = []
        def _exit():
            if _modes.pop(combo, None) is None: return  # a key and the timer can both ask
            timer.cancel()
            for k in bound: unhotkey(k)
        timer = _loop.call_later(timeout, _exit)  # `_enter` dispatches on the loop, so this is loop-thread code
        _modes[combo] = _exit
        try:
            for k, fn in list(keymap.items()) + [('escape', lambda: None)]:
                hotkey(k, lambda fn=fn: (_exit(), fn()))
                bound.append(k)
        except Exception:
            _exit()
            raise
    return hotkey(combo, _enter)


def unleader(
    combo:str # A combination previously passed to `leader`
):
    "Release `combo` and leave its mode if it is active"
    if (exit := _modes.get(combo)): exit()
    unhotkey(combo)

_kinds = {kCGEventKeyDown: 'down', kCGEventKeyUp: 'up', kCGEventFlagsChanged: 'flags'}
_watchers, _tap, _tap_rl, _tap_thread = [], None, None, None


def _tap_cb(proxy, etype, event, refcon):
    if etype in (kCGEventTapDisabledByTimeout, kCGEventTapDisabledByUserInput): CGEventTapEnable(_tap, True)
    elif (kind := _kinds.get(etype)):
        vk, flags = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode), CGEventGetFlags(event)
        # threadsafe scheduling keeps this callback fast: a slow tap callback gets the tap disabled
        for f in _watchers: _loop.call_soon_threadsafe(_dispatch, f, kind, vk, flags)
    return event


def _tap_loop(ready):
    global _tap, _tap_rl
    mask = sum(CGEventMaskBit(o) for o in _kinds)
    _tap = CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly, mask, _tap_cb, None)
    _tap_rl = CFRunLoopGetCurrent()
    if _tap: CFRunLoopAddSource(_tap_rl, CFMachPortCreateRunLoopSource(None, _tap, 0), kCFRunLoopCommonModes)
    ready.set()
    if _tap: CFRunLoopRun()


def _start_tap():
    global _tap_started, _tap_thread
    if _tap_started: return
    if _loop is None: raise RuntimeError('watchers need the agent loop running: wrap your program in run_loop(...) (see README)')
    need('accessibility')
    ready = threading.Event()
    _tap_thread = threading.Thread(target=_tap_loop, args=(ready,), daemon=True)
    _tap_thread.start()
    ready.wait(5)
    if _tap is None: raise RuntimeError('Could not create event tap: is Accessibility granted?')
    _tap_started = True


def watch(
    fn:callable # Called as `fn(kind, vk, flags)` for every key event: kind is 'down', 'up', or 'flags'
):
    "Report every key event system-wide to `fn`, without consuming it; needs Accessibility"
    _start_tap()
    _watchers.append(fn)
    return fn


def unwatch(
    fn:callable # A function previously passed to `watch`
):
    "Stop reporting key events to `fn`"
    _watchers.remove(fn)


# Modifier key codes with their device-specific flag bits (IOKit's NX_DEVICE*KEYMASK), which say
# which side moved: the shared masks in `mods` cannot tell left from right, or say who let go.
modkeys = dict(lctrl=(59,0x1), rctrl=(62,0x2000), lshift=(56,0x2), rshift=(60,0x4),
    lcmd=(55,0x8), rcmd=(54,0x10), lopt=(58,0x20), ropt=(61,0x40), fn=(63,0x800000))
modkeys.update(lalt=modkeys['lopt'], ralt=modkeys['ropt'])

_modwatchers = {}


def holdmod(
    name:str, # A single modifier key, e.g. `'ropt'`; see `modkeys`
    fn:callable=None, # Handler to run when it goes down; omit to use as a decorator
    up:callable=None, # Handler to run when it comes up; omit to ignore that edge
    hold:bool=False # Take `fn` as a generator: the body before `yield` runs on the way down and the rest on the way up
):
    "Run `fn` when a bare modifier key like right Option is pressed. Unlike `hotkey` this reads the tap, so it needs Accessibility and cannot suppress the key"
    if fn is None: return partial(holdmod, name, up=up, hold=hold)
    if name not in modkeys: raise ValueError(f'{name!r} is not a modifier key: try one of {", ".join(modkeys)}')
    vk, devmask = modkeys[name]
    down, up = _pair(fn, up, hold)
    if name in _modwatchers: unholdmod(name)
    def _w(kind, evk, flags):
        if kind=='flags' and evk==vk and (f := down if flags & devmask else up): f()
    _modwatchers[name] = _w
    watch(_w)
    return fn


def unholdmod(
    name:str # A modifier previously passed to `holdmod`
):
    "Stop reporting `name`, so nothing runs when it is pressed"
    unwatch(_modwatchers.pop(name))


def press(
    combo:str # Key combination to send, e.g. `'cmd-c'`
):
    "Send `combo` to the focused application as a synthetic keystroke; needs Accessibility"
    need('accessibility')
    vk, mask = parse_combo(combo)
    flags = sum(v for k,v in _cgflags.items() if mask & k)
    def _post(down):
        ev = CGEventCreateKeyboardEvent(None, vk, down)
        CGEventSetFlags(ev, flags)
        CGEventPost(kCGHIDEventTap, ev)
        time.sleep(0.001)
    try: _post(True)
    finally: _post(False)


async def type_text(
    s:str # Text to type
):
    "Type `s` into the focused application, one synthetic keystroke per chunk; needs Accessibility"
    await aneed('accessibility')
    end = time.monotonic()+1  # applications read live modifier state when interpreting a unicode event, so text typed while the triggering hotkey is still held arrives mangled or not at all
    while not _mods_clear() and time.monotonic() < end: await asyncio.sleep(0.01)
    for i in range(0, len(s), 16):
        chunk = s[i:i+16]
        for down in (True, False):
            ev = CGEventCreateKeyboardEvent(None, 0, down)
            CGEventKeyboardSetUnicodeString(ev, len(chunk), chunk)
            CGEventPost(kCGHIDEventTap, ev)
            await asyncio.sleep(0.001)
