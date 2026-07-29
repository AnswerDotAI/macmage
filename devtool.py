"Development helpers for working on macmage and Imp from the kernel."

import ctypes, re

from fastcore.utils import *
from macmage import Imp
from swifttool import build_app

__all__ = ['run_tests', 'kill_imp', 'imp_dir', 'imp_plist', 'build_imp']

imp_dir = Path('~/git/imp').expanduser()


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


# One entry per permission Imp can ask for, keyed by Info.plist name (NS{k}UsageDescription). macOS kills
# the process outright when a category is requested and its string is missing, and shows the string in the dialog.
_usage = dict(Microphone='record audio', Camera='use the camera', SpeechRecognition='transcribe speech',
    Contacts='read your contacts', CalendarsFullAccess='manage your calendars', AppleEvents='control other apps',
    RemindersFullAccess='manage your reminders', PhotoLibrary='access your photo library')
imp_plist = {f'NS{k}UsageDescription': f'so programs you run through Imp can {v}' for k,v in _usage.items()}


def run_tests(
    *args # Extra pytest arguments; defaults to the whole suite
):
    "Run the tests under Imp, whose permissions the keyboard tests need"
    pytest = Path(sys.executable).with_name('pytest')
    r = Imp(pytest, '-q', *(args or ['tests']), timeout=None)
    return r.stdout + r.stderr


def imp_version():
    "The version Imp reports, which is the one the bundle must claim"
    return re.search(r'impVersion = "([^"]+)"', (imp_dir/'Sources/Imp/main.swift').read_text())[1]


def build_imp(
    hardened:bool=False # Hardened runtime blocks TCC prompts without a per-resource entitlement (see Imp's DEV.md)
):
    "Build, sign, and zip Imp, so its bundle id, version, usage strings, and signing flags live in one place"
    ver = imp_version()
    return build_app(imp_dir, 'com.answerdotai.imp', hardened=hardened,
        CFBundleShortVersionString=ver, CFBundleVersion=ver, **imp_plist)
