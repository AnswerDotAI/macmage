"""What `@mage` does to a handler, checked without touching the keyboard.

Wrapping is easy to get subtly wrong: a function that yields *anywhere* in its body is a
generator function, so one wrapper cannot serve plain, async, and `hold` handlers.
"""
import asyncio

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

    @mage
    async def adouble(x): return x*2
    assert asyncio.run(adouble(21))==42

    @mage
    async def aboom(): raise ValueError('deliberate')
    assert asyncio.run(aboom()) is None


def test_mage_hold_stays_an_async_generator():
    "A `hold` handler is wrapped as an async generator, so both halves of the body still run"
    got = []
    @mage(hold=True)
    async def rec():
        got.append('start')
        yield
        got.append('stop')
    async def drive():
        agen = rec()
        await anext(agen)
        assert got==['start']
        await anext(agen, None)
        assert got==['start','stop']
    asyncio.run(drive())


def test_mage_hold_rejects_a_sync_function():
    "A `hold` handler that is not an async generator fails at registration, not at the first press"
    with pytest.raises(ValueError): mage(lambda: None, hold=True)
    def sync_gen(): yield
    with pytest.raises(ValueError): mage(sync_gen, hold=True)
