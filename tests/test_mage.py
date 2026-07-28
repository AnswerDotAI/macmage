"""What `@mage` does to a handler, checked without touching the keyboard.

Wrapping is easy to get subtly wrong: a function that yields *anywhere* in its body is a
generator function, so one wrapper cannot serve both plain and `hold` handlers.
"""
import pytest

from macmage import mage


def test_mage_returns_and_swallows():
    "A wrapped handler still returns its value, and a raising one logs instead of propagating"
    @mage
    def double(x): return x*2
    assert double(21)==42

    @mage
    def boom(): raise ValueError('deliberate')
    assert boom() is None


def test_mage_hold_stays_a_generator():
    "A `hold` handler is wrapped as a generator, so both halves of the body still run"
    got = []
    @mage(hold=True)
    def rec():
        got.append('start')
        yield
        got.append('stop')
    gen = rec()
    next(gen)
    assert got==['start']
    next(gen, None)
    assert got==['start','stop']


def test_mage_hold_rejects_a_plain_function():
    "A `hold` handler without a `yield` fails at registration, not at the first press"
    with pytest.raises(ValueError): mage(lambda: None, hold=True)
