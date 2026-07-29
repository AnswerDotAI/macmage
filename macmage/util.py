"Small shared helpers"

from fastcore.utils import *
import time

__all__ = ['wait_until', 'apart']


def wait_until(
    f:callable, # Called repeatedly until it returns something truthy
    secs:float=5, # Give up after this long
    pause:float=0.05 # Wait between attempts
):
    "Poll `f` until it returns something truthy and return that, or None once `secs` has elapsed"
    end = time.time()+secs
    while True:
        res = f()
        if res: return res
        if time.time()>=end: return None
        time.sleep(pause)


_spawn = None  # the spawn context, built on first use so importing macmage never touches multiprocessing


def _apart_run(conn, fn, args, kwargs):
    try: conn.send((True, fn(*args, **kwargs)))
    except Exception as e: conn.send((False, e))


def apart(
    fn:callable, # A module-level function; runs in a fresh process, which as a descendant of this one holds Imp's grants
    *args, # Positional arguments for `fn`
    timeout:float=30, # Seconds before the child is killed and TimeoutError raised
    **kwargs
):
    "Run `fn(*args, **kwargs)` in a fresh spawned process and return its result, re-raising what it raises. For capabilities that want their own main loop or must not block this process (see DEV.md)"
    global _spawn
    if _spawn is None:
        import multiprocessing
        _spawn = multiprocessing.get_context('spawn')
    rx, tx = _spawn.Pipe(False)
    p = _spawn.Process(target=_apart_run, args=(tx, fn, args, kwargs), daemon=True)
    p.start()
    tx.close()
    if not rx.poll(timeout):
        p.kill()
        raise TimeoutError(f'apart({fn.__name__}, ...) did not finish in {timeout}s')
    ok, res = rx.recv()
    p.join(1)
    if not ok: raise res
    return res
