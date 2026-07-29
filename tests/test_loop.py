"""The agent arrangement, exercised whole in a subprocess: asyncio on cfloop's Carbon-pumping
selector, owning the main thread. One script pins the contract: a sync handler dispatches
inline from a synthetic press, an async handler runs as a task on the same loop, an AVCapture
delegate's main-queue delivery drains during the pump (asked from a worker thread), and
`stop_keys` from a worker ends the loop cleanly. Punctuation combos per DEV.md: F-keys
silently eat synthetic presses."""
import subprocess, sys

SCRIPT = r'''
import asyncio, threading, time
from macmage import hotkey, press, snap, stop_keys
from macmage import keys
from macmage.keys import run_loop

fired, afired = threading.Event(), threading.Event()
async def ahandler():
    await asyncio.sleep(0.01)
    afired.set()
hgot, hfired = [], threading.Event()
async def holder():
    hgot.append('start')
    yield
    hgot.append('stop')
    hfired.set()
def worker():
    try:
        time.sleep(0.5)
        press('ctrl-alt-cmd-,')
        press('ctrl-alt-cmd-.')
        print('fired:', fired.wait(3), flush=True)
        print('afired:', afired.wait(3), flush=True)
        press("ctrl-alt-cmd-'")
        print('hold:', 'start stop' if hfired.wait(3) and hgot == ['start', 'stop'] else hgot, flush=True)
        p = asyncio.run_coroutine_threadsafe(snap(), keys._loop).result(10)
        print('snap:', p.stat().st_size > 10000, flush=True)
        p.unlink()
    finally: stop_keys()
def setup():
    hotkey('ctrl-alt-cmd-,', fired.set)
    hotkey('ctrl-alt-cmd-.', ahandler)
    hotkey("ctrl-alt-cmd-'", holder, hold=True)
    threading.Thread(target=worker, daemon=True).start()
run_loop(setup)
print('clean exit', flush=True)
'''


def test_agent_arrangement():
    "Sync and async handlers from synthetic presses, capture via the pumped main queue, quit from a worker"
    r = subprocess.run([sys.executable, '-c', SCRIPT], capture_output=True, text=True, timeout=15)
    for want in ('fired: True', 'afired: True', 'hold: start stop', 'snap: True', 'clean exit'):
        assert want in r.stdout, r.stdout + r.stderr
