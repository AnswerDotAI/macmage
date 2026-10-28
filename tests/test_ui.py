"Wisps expose their lifetime and deliver structured page messages only after WebKit is ready."
import asyncio, cfloop, pytest

from macmage import badge, ImpError, keywisp
from macmage.ui import _pick_keys


def test_menu_keys():
    assert _pick_keys(['_edit', '_expand', 'plain', 'end_']) == (['edit', 'expand', 'plain', 'end_'], 'e012')
    assert _pick_keys(['a', '_1st', 'b']) == (['a', '1st', 'b'], '012')
    with pytest.raises(ValueError): _pick_keys(list(range(37)))


def test_wisps(tmp_path):
    page = tmp_path/'page.html'
    page.write_text('''<script>
webkit.messageHandlers.imp.postMessage('loading')
function handle(value) { webkit.messageHandlers.imp.postMessage(value) }
</script>''')
    async def story():
        async with badge('one', title='macmage tests') as b: await b.set('two')
        assert not b.dismissed and b.p.returncode == 0

        with pytest.raises(ImpError):
            async with badge('x', title='macmage tests') as b:
                b.p.kill()
                await b.p.wait()
                await b.set('y')

        async with keywisp(page, title='macmage tests') as w:
            messages = w.messages()
            assert await asyncio.wait_for(anext(messages), 5) == 'loading'
            value = {'text': 'hello\nworld'}
            await w.call('handle', value)
            assert await asyncio.wait_for(anext(messages), 5) == value
        assert not w.dismissed and w.p.returncode == 0
    cfloop.run(story())
