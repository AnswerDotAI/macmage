"""What the clipboard helpers do, checked against the real pasteboard.

These tests replace the clipboard's contents and put them back afterwards.
"""
import pytest
from AppKit import NSPasteboard, NSPasteboardTypeHTML, NSPasteboardTypeString

from macmage import get_clip, set_clip


@pytest.fixture
def clipboard():
    "The pasteboard, with whatever it held restored afterwards"
    pb = NSPasteboard.generalPasteboard()
    was = get_clip()
    yield pb
    if was is not None: set_clip(was)


def test_round_trip(clipboard):
    "Text put on the clipboard comes back"
    set_clip('hello ❤ world')
    assert get_clip() == 'hello ❤ world'


def test_set_clip_drops_other_flavours(clipboard):
    "Styled text becomes plain, which is what makes a plain-text paste possible"
    clipboard.clearContents()
    clipboard.setString_forType_('Styled text', NSPasteboardTypeString)
    clipboard.setString_forType_('<i>Styled text</i>', NSPasteboardTypeHTML)
    assert NSPasteboardTypeHTML in clipboard.types()
    set_clip(get_clip())
    assert NSPasteboardTypeHTML not in clipboard.types()
    assert get_clip() == 'Styled text'


def test_get_clip_without_text(clipboard):
    "An empty clipboard reads as None rather than raising"
    clipboard.clearContents()
    assert get_clip() is None
