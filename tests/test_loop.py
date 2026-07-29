"""The agent's loop-on-main arrangement, exercised whole in a subprocess: a hotkey registered
before the loop starts fires from a synthetic press, an AVCapture delegate arrives with no
pumping while the main loop runs, and a worker thread's `stop_keys` exits the loop cleanly
(all three verified as probes first; see DEV.md). Punctuation combo per DEV.md: F-keys
silently eat synthetic presses."""
import subprocess, sys

SCRIPT = r'''
import threading, time
from macmage import hotkey, press, snap_py, stop_keys
from macmage.keys import run_loop

fired = threading.Event()
def worker():
    time.sleep(0.5)
    press('ctrl-alt-cmd-,')
    print('fired:', fired.wait(3), flush=True)
    p = snap_py()
    print('snap:', p.stat().st_size > 10000, flush=True)
    p.unlink()
    stop_keys()
def setup():
    hotkey('ctrl-alt-cmd-,', fired.set)
    threading.Thread(target=worker, daemon=True).start()
run_loop(setup)
print('clean exit', flush=True)
'''


def test_agent_arrangement():
    "Register, synthetic press, capture without pumping, then quit from a worker, under the main-thread loop"
    r = subprocess.run([sys.executable, '-c', SCRIPT], capture_output=True, text=True, timeout=30)
    assert 'fired: True' in r.stdout and 'snap: True' in r.stdout and 'clean exit' in r.stdout, r.stdout + r.stderr
