"Development helpers for working on macmage and Imp from the kernel."

import re

from fastcore.utils import *
from macmage import Imp
from swifttool import build_app

__all__ = ['run_tests', 'imp_dir', 'imp_plist', 'build_imp']

imp_dir = Path('~/git/imp').expanduser()

# One entry per permission Imp can ask for, keyed by Info.plist name (NS{k}UsageDescription). macOS kills
# the process outright when a category is requested and its string is missing, and shows the string in the dialog.
_usage = dict(Microphone='record audio', Camera='use the camera', SpeechRecognition='transcribe speech',
    Contacts='read your contacts', CalendarsFullAccess='manage your calendars',
    RemindersFullAccess='manage your reminders', PhotoLibrary='access your photo library')
imp_plist = {f'NS{k}UsageDescription': f'so programs you run through Imp can {v}' for k,v in _usage.items()}


def run_tests(
    *args # Extra pytest arguments; defaults to the whole suite
):
    "Run the tests under Imp, whose permissions the keyboard tests need"
    pytest = Path(sys.executable).with_name('pytest')
    r = Imp(pytest, '-q', *(args or ['tests']))
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
