"""Showing things to the user. The notification test is marked `visible` and deselected by
default, since a suite that fires banners at you is a suite you stop running."""
import pytest

from macmage import imp_check, notify, pick


@pytest.mark.visible
@pytest.mark.skipif(not imp_check('notifications'), reason='Imp has no notifications permission')
def test_notify():
    "A notification goes out, and Imp reports whether Notification Center took it"
    assert notify('macmage tests', 'this is what a notification looks like')


def test_pick_rejects_bad_argument_lists():
    "Imp refuses an empty or oversized menu with a usage error, which pick reports as a dismissal"
    assert pick('macmage tests', []) is None
    assert pick('macmage tests', list(range(11))) is None
