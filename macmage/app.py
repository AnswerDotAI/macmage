"Applications and the desktop"

from fastcore.utils import Path, req

from fastcocoa import nsurl
from fastcocoa.appkit import NSWorkspace, NSWorkspaceOpenConfiguration
from fastcocoa.foundation import NSURL

__all__ = ['open_url', 'open_app', 'frontmost', 'tell']


def open_url(
    url:str # Any URL, including custom schemes an application has registered
):
    "Open `url` in whichever application handles it, as clicking a link would"
    return NSWorkspace.sharedWorkspace().openURL(NSURL(string=url))


def open_app(
    name:str, # An application's name, as `open -a` takes it, with or without `.app`
    *paths # Files for it to open
):
    "Launch `name`, or bring it to the front when it is already running. Returns the bundle's path"
    ws = NSWorkspace.sharedWorkspace()
    path = req(ws.fullPathForApplication(name), f'No application named {name!r}')
    url, cfg = nsurl(path), NSWorkspaceOpenConfiguration.configuration()
    if paths: ws.open([nsurl(Path(o).expanduser().resolve()) for o in paths], withApplicationAt=url,
        configuration=cfg, completionHandler=None)  # resolve: MacVim mismatches documents opened via a symlink path
    else: ws.openApplication(at=url, configuration=cfg, completionHandler=None)
    return path


def frontmost():
    "The frontmost application: a dict of name, bundle_id, and pid. Needs no permission"
    a = NSWorkspace.sharedWorkspace().frontmostApplication
    return dict(name=a.localizedName, bundle_id=a.bundleIdentifier, pid=a.processIdentifier)


async def tell(
    bundle_id:str, # The target app, e.g. from `frontmost`
    script:str, # AppleScript to run inside its tell block
    timeout:float=30 # Seconds before the run is killed
):
    "Run AppleScript against one app through Imp, whose `automation:<bundle_id>` grant it uses"
    from .imp import aimp
    r = await aimp('osascript', '-e', f'tell application id "{bundle_id}"\n{script}\nend tell', timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr.strip() or f'osascript failed ({r.returncode})')
    return r.stdout.strip()
