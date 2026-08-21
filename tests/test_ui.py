"""Showing things to the user. The notification test is marked `visible` and deselected by
default, since a suite that fires banners at you is a suite you stop running."""
import asyncio, cfloop, pytest

from macmage import badge, ImpError, imp_check, keywisp, notify, pick


@pytest.mark.visible
@pytest.mark.skipif(not imp_check('notifications'), reason='Imp has no notifications permission')
def test_notify():
    "A notification goes out, and Imp reports whether Notification Center took it"
    assert cfloop.run(notify('macmage tests', 'this is what a notification looks like'))


def test_pick_rejects_bad_argument_lists():
    "Imp refuses an empty menu (a dismissal); more than 36 unmarked items fail fast in Python"
    async def main(): return await pick('macmage tests', [])
    assert cfloop.run(main()) is None
    with pytest.raises(ValueError): cfloop.run(pick('macmage tests', list(range(37))))


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
    "An Imp crash is not mistaken for the person dismissing its panel"
    async def main():
        async with badge('x', title='macmage tests') as b:
            b.p.kill()
            await b.p.wait()
            await b.set('y')
    with pytest.raises(ImpError, match='status -9'): cfloop.run(main())


def test_keywisp_round_trip(tmp_path):
    "Ready precedes loading-time posts, and structured messages cross intact without sleeps or caller framing"
    f = tmp_path/'k.html'
    f.write_text("""<script>
webkit.messageHandlers.imp.postMessage('loading')
function handle(value) { webkit.messageHandlers.imp.postMessage(value) }
</script>""")
    async def main():
        async with keywisp(f, title='macmage tests') as w:
            it = w.messages()
            loading = await asyncio.wait_for(anext(it), 5)
            await w.call('handle', {'text': 'hello\nworld'})
            message = await asyncio.wait_for(anext(it), 5)
        return w, loading, message
    w, loading, message = cfloop.run(main())
    assert loading == 'loading' and message == {'text': 'hello\nworld'}
    assert not w.dismissed and w.p.returncode == 0
