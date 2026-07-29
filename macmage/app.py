"Applications and the desktop"

from AppKit import NSWorkspace, NSWorkspaceOpenConfiguration
from Foundation import NSURL
from fastcore.utils import Path

__all__ = ['open_url', 'open_app', 'frontmost', 'tell']


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


def frontmost():
    "The frontmost application: a dict of name, bundle_id, and pid. Needs no permission"
    a = NSWorkspace.sharedWorkspace().frontmostApplication()
    return dict(name=str(a.localizedName()), bundle_id=str(a.bundleIdentifier()), pid=int(a.processIdentifier()))


def tell(
    bundle_id:str, # The target app, e.g. from `frontmost`
    script:str, # AppleScript to run inside its tell block
    timeout:float=30 # Seconds before the run is killed
):
    "Run AppleScript against one app through Imp, whose `automation:<bundle_id>` grant it uses"
    from .imp import Imp
    r = Imp('osascript', '-e', f'tell application id "{bundle_id}"\n{script}\nend tell', timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr.strip() or f'osascript failed ({r.returncode})')
    return r.stdout.strip()
