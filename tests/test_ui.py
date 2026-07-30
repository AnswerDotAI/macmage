"""Showing things to the user. The notification test is marked `visible` and deselected by
default, since a suite that fires banners at you is a suite you stop running."""
import asyncio, cfloop, pytest

from macmage import badge, imp_check, notify, pick


@pytest.mark.visible
@pytest.mark.skipif(not imp_check('notifications'), reason='Imp has no notifications permission')
def test_notify():
    "A notification goes out, and Imp reports whether Notification Center took it"
    assert cfloop.run(notify('macmage tests', 'this is what a notification looks like'))


def test_pick_rejects_bad_argument_lists():
    "Imp refuses an empty menu (a dismissal); more than ten unmarked items fail fast in Python"
    async def main(): return await pick('macmage tests', [])
    assert cfloop.run(main()) is None
    with pytest.raises(ValueError): cfloop.run(pick('macmage tests', list(range(11))))


def test_pick_keys():
    "`_` claims the next char; collisions and unmarked items get spare digits; trailing `_` is inert"
    from macmage.ui import _pick_keys
    assert _pick_keys(['_edit', '_expand', 'plain', 'end_']) == (['edit', 'expand', 'plain', 'end_'], 'e012')
    assert _pick_keys(['a', '_1st', 'b']) == (['a', '1st', 'b'], '012')



def test_badge_round_trip(tmp_path):
    "A badge appears without taking focus, takes updates, and exits 0 when its block ends"
    async def main():
        async with badge('one', title='macmage tests') as b:
            await b.set('two')
            await asyncio.sleep(0.3)  # long enough for the panel to render an update
        return b
    b = cfloop.run(main())
    assert not b.dismissed and b.p.returncode == 0


def test_badge_survives_early_process_death():
    "set() after the wisp is gone records dismissal instead of raising"
    async def main():
        async with badge('x', title='macmage tests') as b:
            b.p.kill()
            await b.p.wait()
            await b.set('y')
            await b.set('z')
        return b
    assert cfloop.run(main()).dismissed
