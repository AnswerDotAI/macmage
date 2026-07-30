from fastcore.utils import *
import asyncio, subprocess, time
from functools import partial
from itertools import cycle
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from macmage import *

state = Path('~/.local/state/macmage').expanduser()


@mage(keys='alt-`')
async def backticks(): await type_text('`​``')


@mage(keys='ctrl-shift-a')
def solveit():
    "Bring up the Solveit workspace"
    open_app('Solveit-aai-ws')


# Clipboard: ctrl-alt-cmd-c, then one letter

def spongebob(s):
    "aLtErNaTiNg cApS, skipping over anything that is not a letter"
    case = cycle((str.lower, str.upper))
    return ''.join(next(case)(c) if c.isalpha() else c for c in s)


def unwrap(s):
    "Join hard-wrapped lines, keeping paragraph breaks, for pasting into a chat box"
    return '\n\n'.join(' '.join(p.split()) for p in re.split(r'\n\s*\n', s))


def fence(s): return f'```\n{s.strip()}\n```'


def untrack(s):
    "Drop the tracking parameters a copied URL collects"
    junk = {'fbclid', 'gclid', 'mc_eid', 'igshid', 'si', 'ref', 'ref_src', 'spm'}
    u = urlsplit(s.strip())
    q = [(k, v) for k, v in parse_qsl(u.query) if not (k.startswith('utm_') or k in junk)]
    return urlunsplit(u._replace(query=urlencode(q)))


leader('ctrl-alt-cmd-c', dict(
    s=partial(map_clip, spongebob),
    p=partial(map_clip, str),        # same text, one flavour, so it pastes unstyled
    u=partial(map_clip, str.upper),
    l=partial(map_clip, str.lower),
    t=partial(map_clip, str.title),
    j=partial(map_clip, unwrap),
    f=partial(map_clip, fence),
    q=partial(map_clip, untrack)))


# Applications: ctrl-alt-cmd-a, then one letter

leader('ctrl-alt-cmd-a', dict(g=partial(open_app, 'Ghostty'), s=partial(open_app, 'Solveit-aai-ws'),
    v=partial(open_app, 'MacVim'), c=partial(open_app, 'Google Chrome')))


# macmage itself: one hotkey, then a menu.

def restart():
    "Exit, and let launchd's KeepAlive start the agent again, launcher included"
    stop_keys()
    os._exit(0)


async def status():
    r = subprocess.run([Path(sys.executable).with_name('macmage'), '--status'], capture_output=True, text=True)
    await show('macmage status', (r.stdout + r.stderr).strip())


async def logs(): await show('macmage logs', '\n'.join((state/'stderr.log').read_text().splitlines()[-100:]))


async def _menu(title, acts):
    "Pick an entry and run it, awaiting the async ones"
    if (i := await pick(title, [name for name, _ in acts])) is not None: await maybe_await(acts[i][1]())


@mage(keys='ctrl-alt-cmd-m')
async def mage_menu():
    await _menu('macmage', [('_status', status), ('_logs', logs), ('_automate frontmost', automate_this),
        ('_edit config', partial(open_app, 'MacVim', '~/.config/macmage/config.py')), ('_restart agent', restart)])


# Timer: ctrl-alt-cmd-t toggles. Pick a duration; 0 is a stopwatch the same key stops, putting
# the elapsed seconds in the clipboard; the rest count down in a badge to an alert and a tone.
_timer = {}


async def _run_timer(secs):
    t0 = time.monotonic()
    try:
        if secs:
            async with badge(str(secs), title='timer') as b:
                for left in range(secs - 1, -1, -1):
                    await asyncio.sleep(1)
                    await b.set(str(left))
                    if b.dismissed: return
            tone()
            await alert('timer', f'{secs} seconds are up')
        else:
            async with badge('0', title='stopwatch') as b:
                while not b.dismissed:
                    await asyncio.sleep(1)
                    await b.set(str(round(time.monotonic() - t0)))
    except asyncio.CancelledError:
        if not secs: set_clip(str(round(time.monotonic() - t0)))
        raise
    finally: _timer.pop('task', None)


@mage(keys='ctrl-alt-cmd-t')
async def timer():
    "Toggle: start a timer from a pick, or stop the running one (a stopped stopwatch's seconds go to the clipboard)"
    if (t := _timer.pop('task', None)): return t.cancel()
    secs = [0, 5, 10, 20, 60, 120, 240, 600]
    if (i := await pick('timer secs', ['0 (stopwatch)'] + [str(o) for o in secs[1:]])) is not None:
        _timer['task'] = asyncio.create_task(_run_timer(secs[i]))


# Demos: every wisp and every Imp grant, one menu. ctrl-alt-cmd-d

def _lines(rows, f): return '\n'.join(f(o) for o in rows) or '(none)'


async def demo_contact(): await show('contact', repr(await contact('Rachel')))
async def demo_events(): await show('next 7 days', _lines(await events(), lambda e: f"{e['start']:%a %d %H:%M}  {e['title']}"))
async def demo_photos():
    await show('newest photos', _lines(await photos(5),
        lambda p: f"{p['created']:%Y-%m-%d %H:%M}  {p['w']}x{p['h']}" + ('  video' if p['video'] else '')))


async def demo_reminders():
    await show('open reminders', _lines(await reminders(),
        lambda r: r['title'] + (f"  (due {r['due']:%a %d %b})" if r['due'] else '')))


async def demo_snap(): await web(await snap(), 'snap')


async def automate_this():
    "Get an automation grant for whatever app is frontmost, which is when its dialog can appear"
    f = frontmost()
    rc = (await aimp(grant=f"automation:{f['bundle_id']}")).returncode
    await notify('macmage', f"automation of {f['name']}: {'granted' if rc == 0 else 'missing'}")


async def demo_dictate():
    "The composition demo: speak for five seconds, and it gets typed wherever focus is"
    await notify('macmage', 'speak now: five seconds')
    await type_text(await transcribe(await record(5)))


@mage(keys='ctrl-alt-cmd-d')
async def demo():
    await _menu('demos', [('_notify', partial(notify, 'macmage', 'this banner came from Python, via Imp')),
        ('_alert', partial(alert, 'A wisp', 'Buttons exit with their index.', 'Nice', 'Very nice')),
        ('_web', partial(web, 'https://answer.ai', 'a web wisp')), ('_contact', demo_contact), ('_events', demo_events),
        ('_reminders', demo_reminders), ('_photos', demo_photos), ('_snap', demo_snap), ('_dictate', demo_dictate)])


# Site-local additions that do not belong in the repo: create config_local.py beside config.py
try: import config_local  # chkstyle: ignore - the side-effect import is the mechanism
except ImportError: pass
