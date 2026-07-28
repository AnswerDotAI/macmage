"Applications and the desktop"

from AppKit import NSWorkspace, NSWorkspaceOpenConfiguration
from Foundation import NSURL
from fastcore.utils import Path

__all__ = ['open_url', 'open_app']


def open_url(
    url:str # Any URL, including custom schemes an application has registered
):
    "Open `url` in whichever application handles it, as clicking a link would"
    return NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))


def open_app(
    name:str, # An application's name, as `open -a` takes it, with or without `.app`
    *paths # Files for it to open
):
    "Launch `name`, or bring it to the front when it is already running. Returns the bundle's path"
    ws = NSWorkspace.sharedWorkspace()
    path = ws.fullPathForApplication_(name)
    if path is None: raise ValueError(f'No application named {name!r}')
    url, cfg = NSURL.fileURLWithPath_(path), NSWorkspaceOpenConfiguration.configuration()
    if paths: ws.openURLs_withApplicationAtURL_configuration_completionHandler_(
        [NSURL.fileURLWithPath_(str(Path(o).expanduser())) for o in paths], url, cfg, None)
    else: ws.openApplicationAtURL_configuration_completionHandler_(url, cfg, None)
    return path
