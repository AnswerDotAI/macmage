"The clipboard, as plain text"

from AppKit import NSPasteboard, NSPasteboardTypeString

__all__ = ['get_clip', 'set_clip', 'map_clip']


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
