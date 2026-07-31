"Showing things to the user: wisps through Imp, because only a bundled app may, and sounds locally"

import asyncio
from contextlib import asynccontextmanager, suppress

from AppKit import NSSound

from .imp import aimp as _imp, _argv

__all__ = ['notify', 'alert', 'pick', 'show', 'web', 'badge', 'tone']


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
        except (BrokenPipeError, ConnectionResetError): self.dismissed = True


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
    finally:
        with suppress(BrokenPipeError, ConnectionResetError): p.stdin.close()
        await p.wait()
        if p.returncode == 2: b.dismissed = True
