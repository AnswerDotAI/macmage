"Showing things to the user, which goes through Imp because only a bundled app may"

import subprocess

from .imp import ImpError, install_msg, launcher

__all__ = ['notify', 'alert']


def _imp(*args):
    if not launcher.exists(): raise ImpError(f'Imp is not installed: {install_msg}')
    return subprocess.run([str(launcher), *[str(o) for o in args]]).returncode


def notify(
    title:str, # The bold first line
    body:str='' # The rest of the notification
):
    "Post a notification, returning whether it went out. Needs Imp's `notifications` permission"
    return _imp('--notify', title, body) == 0


def alert(
    title:str, # The bold first line
    body:str='', # The rest of the message
    *buttons:str # Button titles, left to right; one `OK` button when none are given
):
    "Show a message box and wait, returning the index of the button pressed. Blocks the handler until it is dismissed"
    return _imp('--alert', title, body, *buttons)
