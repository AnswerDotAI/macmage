"""`apart` runs real functions in fresh spawned processes: results, exceptions, and timeouts
all cross the process boundary, which is what makes it safe to build capabilities on."""
import pytest

from macmage import apart


def _double(x, plus=0): return x*2 + plus


def _boom(): raise ValueError('from apart')


def _sleepy():
    import time
    time.sleep(60)


def test_apart():
    "A result comes back, an exception re-raises, and a hang is bounded"
    assert apart(_double, 21) == 42
    assert apart(_double, 20, plus=2) == 42
    with pytest.raises(ValueError, match='from apart'): apart(_boom)
    with pytest.raises(TimeoutError): apart(_sleepy, timeout=2)
