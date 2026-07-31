"Development helpers for working on macmage from the kernel; Imp build helpers live in imp/devtool.py."

import ctypes

from fastcore.utils import *
from macmage import Imp

__all__ = ['run_tests', 'kill_imp']


def _ppid(pid):
    "Parent pid via PROC_PIDT_SHORTBSDINFO, whose second uint32 is pbsi_ppid"
    from macmage.imp import _libc
    buf = (ctypes.c_uint32*128)()
    return buf[1] if _libc.proc_pidinfo(pid, 13, 0, buf, ctypes.sizeof(buf)) else 0


def kill_imp(
    sig=15 # Signal to send; SIGTERM by default
):
    "Kill running Imps, for hung verbs during development. Spares this process's own Imp ancestors (the kernel runs under one); launchd restarts the agent by itself"
    from macmage.imp import _exe, _libc, launcher
    mine, p = set(), os.getpid()
    while p > 1:
        mine.add(p)
        p = _ppid(p)
    n = _libc.proc_listallpids(None, 0)
    buf = (ctypes.c_int*(n+64))()
    n = _libc.proc_listallpids(buf, ctypes.sizeof(buf))
    tgt = str(launcher.resolve())
    pids = [p for p in buf[:n] if p and p not in mine and _exe(p)==tgt]
    for p in pids: os.kill(p, sig)
    return pids


def run_tests(
    *args # Extra pytest arguments; defaults to the whole suite
):
    "Run the tests under Imp, whose permissions the keyboard tests need"
    pytest = Path(sys.executable).with_name('pytest')
    r = Imp(pytest, '-q', *(args or ['tests']), timeout=None)
    return r.stdout + r.stderr

