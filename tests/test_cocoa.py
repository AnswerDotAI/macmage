"""The cocoa plumbing helpers: `chk`'s two NSError shapes and `mk`'s kwarg-to-setter mapping,
checked against real Foundation objects (no store permissions needed)."""
import pytest
from Foundation import NSDateFormatter

from macmage.cocoa import chk, mk, setprops


def test_chk():
    "chk unpacks (val, err) and (ok, err), raising only on a reported error"
    assert chk(('v', None)) == 'v'
    assert chk((True, None)) is True
    with pytest.raises(RuntimeError, match='boom'): chk(('v', 'boom'))
    with pytest.raises(RuntimeError): chk((False, None))
    assert chk((0, None)) == 0  # falsy values that aren't False pass through


def test_mk():
    "mk allocs, inits, and maps each kwarg onto its Cocoa setter"
    f = mk(NSDateFormatter, dateFormat='yyyy', lenient=True)
    assert str(f.dateFormat()) == 'yyyy' and bool(f.isLenient())
    g = setprops(NSDateFormatter.alloc().init(), dateFormat='MM')
    assert str(g.dateFormat()) == 'MM'
