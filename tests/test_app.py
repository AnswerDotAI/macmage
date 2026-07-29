"What `open_app` does before it opens anything, since launching an application is not a test."

import pytest

from macmage import frontmost, imp_check, open_app, tell


def test_open_app_unknown_name():
    "An unknown name fails at once, rather than silently opening nothing"
    with pytest.raises(ValueError): open_app('NoSuchApplicationExists')


def test_frontmost_shape():
    "Whatever is frontmost has a name, a bundle id, and a live pid"
    f = frontmost()
    assert f['name'] and '.' in f['bundle_id'] and f['pid'] > 0


@pytest.mark.skipif(not imp_check('automation:com.apple.finder'), reason='Imp has no Finder automation grant')
def test_tell_finder():
    "AppleScript reaches Finder through Imp's per-target automation grant"
    assert tell('com.apple.finder', 'return name of home')
