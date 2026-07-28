"The clipboard, as plain text"

import threading, time

from AppKit import NSPasteboard, NSPasteboardTypeString

__all__ = ['get_clip', 'set_clip', 'map_clip', 'watch_clip', 'unwatch_clip']

# The convention password managers use to mark copies that must not be recorded
_SKIP = {'org.nspasteboard.ConcealedType', 'org.nspasteboard.TransientType'}


def get_clip():
    "The clipboard's text, or None when it holds none"
    return NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString)


def set_clip(
    s:str # Text to put on the clipboard
):
    "Replace the clipboard with `s`. Every other flavour goes, so what was styled text pastes plain"
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(s, NSPasteboardTypeString)


def map_clip(
    f:callable # Called with the clipboard's text, and returns what replaces it
):
    "Replace the clipboard with `f` applied to its text, doing nothing when it holds none"
    if (s := get_clip()) is not None: set_clip(f(s))


_clip_watchers = []


def _clip_poll():
    # There is no clipboard-change notification on macOS; polling `changeCount` is the
    # sanctioned mechanism, and the check is microseconds.
    pb = NSPasteboard.generalPasteboard()
    last = pb.changeCount()
    while _clip_watchers:
        time.sleep(0.5)
        c = pb.changeCount()
        if c == last: continue
        last = c
        if _SKIP & set(pb.types() or ()): continue
        if (s := get_clip()) is None: continue
        for f in list(_clip_watchers): f(s)


def watch_clip(
    fn:callable # Called with the clipboard's new text after every change
):
    "Report clipboard changes to `fn`, skipping copies marked concealed or transient (passwords). Usable as a decorator; needs no permission"
    _clip_watchers.append(fn)
    if len(_clip_watchers) == 1: threading.Thread(target=_clip_poll, daemon=True).start()
    return fn


def unwatch_clip(
    fn:callable # A function previously passed to `watch_clip`
):
    "Stop reporting clipboard changes to `fn`; the poll thread ends when nobody is watching"
    _clip_watchers.remove(fn)
