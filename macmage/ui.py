"Showing things to the user, which goes through Imp because only a bundled app may"

from .imp import aimp as _imp

__all__ = ['notify', 'alert', 'pick', 'show', 'web']


async def web(
    target:str, # A URL, or a path to a local file to display
    title:str='macmage' # The panel title
):
    "Show a page or file in a web wisp until it is dismissed"
    await _imp(web=(title, str(target)))


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


async def pick(
    title:str, # The panel title
    items:list, # Up to ten choices, shown with their digits
):
    "Show a numbered menu, returning the chosen index, or None when dismissed"
    r = await _imp(pick=(title, *items))
    return int(r.stdout) if r.returncode == 0 else None


async def show(
    title:str, # The panel title
    text:str, # What to display, monospaced and selectable
):
    "Show text in a scrollable panel until it is dismissed"
    await _imp(show=title, input=text)
