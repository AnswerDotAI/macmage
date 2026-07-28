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


def _wait(cond, secs=2.0):
    import time
    end = time.time() + secs
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    return False


def test_watch_clip_reports_changes(clipboard):
    "A watcher hears a copy, and stops hearing after unwatch"
    from macmage import unwatch_clip, watch_clip
    got = []
    watch_clip(got.append)
    set_clip('clip watch test')
    assert _wait(lambda: 'clip watch test' in got), 'watcher did not hear the change'
    unwatch_clip(got.append)
    n = len(got)
    set_clip('after unwatch')
    assert not _wait(lambda: len(got) > n, 1.2), 'watcher heard a change after unwatch'


def test_watch_clip_skips_concealed(clipboard):
    "A copy marked concealed, the password-manager convention, is never reported"
    from macmage import unwatch_clip, watch_clip
    got = []
    watch_clip(got.append)
    clipboard.declareTypes_owner_([NSPasteboardTypeString, 'org.nspasteboard.ConcealedType'], None)
    clipboard.setString_forType_('hunter2', NSPasteboardTypeString)
    assert not _wait(lambda: 'hunter2' in got, 1.2), 'a concealed copy was recorded'
    set_clip('visible again')
    assert _wait(lambda: 'visible again' in got), 'watching did not resume after a concealed copy'
    unwatch_clip(got.append)
