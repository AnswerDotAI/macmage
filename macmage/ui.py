"Showing things to the user: wisps through Imp, because only a bundled app may, and sounds locally"

import asyncio, json
from contextlib import asynccontextmanager, suppress

from AppKit import NSSound

from .imp import ImpError, aimp as _imp, _argv

__all__ = ['notify', 'alert', 'pick', 'show', 'web', 'badge', 'keywisp', 'tone']


def _frame(frame): return dict(frame=frame) if frame else {}


def tone(
    name:str='Glass' # A system sound name, from /System/Library/Sounds
):
    "Play a short system sound; unknown names play nothing"
    if (s := NSSound.soundNamed_(name)): s.play()


async def web(
    target:str, # A URL, or a path to a local file to display
    title:str='macmage', # The panel title
    frame:str=None, # An Imp --frame spec: tr|tl|br|bl, 400x300, or 400x300@tr
):
    "Show a page or file in a web wisp until it is dismissed"
    await _imp(web=(title, str(target)), **_frame(frame))


async def notify(
    title:str, # The bold first line
    body:str='' # The rest of the notification
):
    "Post a notification, returning whether it went out. Needs Imp's `notifications` permission"
    return (await _imp(notify=(title, body))).returncode == 0


async def alert(
    title:str, # The bold first line
    body:str='', # The rest of the message
    *buttons:str # Button titles, left to right; one `OK` button when none are given
):
    "Show a message box, returning the index of the button pressed once dismissed"
    return (await _imp(alert=(title, body, *buttons))).returncode


def _pick_keys(items):
    "Labels and key chars from `_` markers: `('_edit',)` -> `['edit'], 'e'`; the unmarked get spare digits, then letters"
    labels, keys, used = [], [], set()
    for o in items:
        i = str(o).find('_')
        k = str(o)[i+1].lower() if 0 <= i < len(str(o))-1 else None
        labels.append(str(o)[:i] + str(o)[i+1:] if k else str(o))
        keys.append(k if k and k not in used else None)
        used.update(keys[-1] or ())
    spares = (d for d in '0123456789abcdefghijklmnopqrstuvwxyz' if d not in used)
    keys = [k or next(spares, None) for k in keys]
    if None in keys: raise ValueError('more than 36 items need `_` keys; only digits and letters exist')
    return labels, ''.join(keys)


async def pick(
    title:str, # The panel title
    items:list, # The choices; an item's first `_` claims the next character as its key, the rest get digits, then letters
    frame:str=None, # An Imp --frame spec
):
    "Show a key-driven menu, returning the chosen index, or None when dismissed"
    labels, keys = _pick_keys(items)
    r = await _imp(pick=(title, '--keys', keys, *labels), **_frame(frame))
    return int(r.stdout) if r.returncode == 0 else None


async def show(
    title:str, # The panel title
    text:str, # What to display, monospaced and selectable
    frame:str=None, # An Imp --frame spec
):
    "Show text in a scrollable panel until it is dismissed"
    await _imp(show=title, input=text, **_frame(frame))


class Badge:
    "A live wisp on a leash, from `badge`: `set` replaces its text; `dismissed` reports the close button"
    def __init__(self, p): self.p, self.dismissed = p, False
    async def set(self,
        text:str # The badge's new text, replacing what it shows now
    ):
        if self.dismissed: return
        try:
            self.p.stdin.write(f'{text}\n'.encode())
            await self.p.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): await _wisp_done(self)


async def _wisp_done(w):
    "Record a person's dismissal, and expose every other abnormal Imp exit"
    await w.p.wait()
    w.dismissed = w.p.returncode == 2
    if w.p.returncode not in (0, 2): raise ImpError(f'Imp {type(w).__name__} exited with status {w.p.returncode}')


@asynccontextmanager
async def badge(
    text:str='', # The initial text
    title:str='macmage', # The panel title
    frame:str='tr', # Where the badge sits (an Imp --frame spec)
):
    "A floating lamp that never takes focus, alive for the block: yields a `Badge` whose `set` updates it"
    p = await asyncio.create_subprocess_exec(*_argv(show=title, live=True, frame=frame), stdin=asyncio.subprocess.PIPE)
    b = Badge(p)
    try:
        if text: await b.set(text)
        yield b
    except BaseException:
        with suppress(BrokenPipeError, ConnectionResetError): p.stdin.close()
        await p.wait()
        raise
    else:
        with suppress(BrokenPipeError, ConnectionResetError): p.stdin.close()
        await _wisp_done(b)


class KeyWisp:
    "A keyboard-taking live page: `eval`/`call` drive it, `messages` yields values it posts back"
    def __init__(self, p): self.p, self.dismissed = p, False
    async def _ready(self):
        "Wait until the page is loaded and its functions are safe to call"
        line = await self.p.stdout.readline()
        if not line:
            await self.p.wait()
            raise ImpError(f'Imp exited before the key wisp was ready (status {self.p.returncode}); update Imp')
        try: event = json.loads(line)
        except json.JSONDecodeError as e: raise ImpError('Imp does not support the key wisp protocol; update Imp') from e
        if event != {'kind': 'ready'}: raise ImpError(f'Imp sent {event!r} before the key wisp was ready')
    async def eval(self,
        js:str # One line of JavaScript to evaluate in the page
    ):
        "Evaluate one line of JavaScript; a dismissed panel makes later calls no-ops"
        if '\n' in js or '\r' in js: raise ValueError('keywisp.eval needs one line of JavaScript')
        if self.dismissed: return
        try:
            self.p.stdin.write((js+'\n').encode())
            await self.p.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): await _wisp_done(self)
    async def call(self,
        fn:str, # Name of a global page function
        *args # Its JSON-serializable arguments
    ):
        "Call the global page function `fn` with JSON-serializable `args`"
        await self.eval(f"globalThis[{json.dumps(fn)}]({', '.join(json.dumps(a) for a in args)})")
    async def messages(self):
        "Values posted with webkit.messageHandlers.imp.postMessage, until the wisp closes"
        while line := await self.p.stdout.readline():
            event = json.loads(line)
            if event.get('kind') != 'message': raise ImpError(f'unknown Imp key wisp event: {event!r}')
            yield event.get('value')
        await _wisp_done(self)
    async def close(self):
        "Close the panel and wait for Imp to finish"
        with suppress(BrokenPipeError, ConnectionResetError): self.p.stdin.close()
        await _wisp_done(self)


@asynccontextmanager
async def keywisp(
    target:str, # A URL, or a path to a local file to display
    title:str='macmage', # The panel title
    frame:str=None, # An Imp --frame spec
):
    "A live web wisp that takes the keyboard while the previous app stays frontmost"
    p = await asyncio.create_subprocess_exec(*_argv(web=(title, str(target)), live=True, key=True, **_frame(frame)),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    w = KeyWisp(p)
    try:
        await w._ready()
        yield w
    except BaseException:
        with suppress(BrokenPipeError, ConnectionResetError): p.stdin.close()
        await p.wait()
        raise
    else: await w.close()
