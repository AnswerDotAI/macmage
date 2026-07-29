"Showing things to the user, which goes through Imp because only a bundled app may"

from .imp import Imp

__all__ = ['notify', 'alert', 'pick', 'show']


def notify(
    title:str, # The bold first line
    body:str='' # The rest of the notification
):
    "Post a notification, returning whether it went out. Needs Imp's `notifications` permission"
    return Imp(notify=(title, body)).returncode == 0


def alert(
    title:str, # The bold first line
    body:str='', # The rest of the message
    *buttons:str # Button titles, left to right; one `OK` button when none are given
):
    "Show a message box and wait, returning the index of the button pressed. Blocks the handler until it is dismissed"
    return Imp(alert=(title, body, *buttons), timeout=None).returncode


def pick(
    title:str, # The panel title
    items:list, # Up to ten choices, shown with their digits
):
    "Show a numbered menu and wait, returning the chosen index, or None when dismissed. Blocks the handler until answered"
    r = Imp(pick=(title, *items), timeout=None)
    return int(r.stdout) if r.returncode == 0 else None


def show(
    title:str, # The panel title
    text:str, # What to display, monospaced and selectable
):
    "Show text in a scrollable panel and wait until it is dismissed"
    Imp(show=title, input=text, timeout=None)
