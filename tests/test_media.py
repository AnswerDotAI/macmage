"Native recording, streaming, recognition and photo export, expressed through macmage's Python API."
import subprocess

import cfloop, pytest
from macmage import listen, photos, record, save_photo, transcribe


def test_audio(tmp_path):
    aiff = tmp_path/'hello.aiff'
    subprocess.run(['say', '-o', str(aiff), 'hello world'], check=True)
    async def story():
        assert 'hello' in (await transcribe(aiff)).lower()
        recording = await record(0.5, tmp_path/'clip.m4a')
        assert recording.stat().st_size > 1000
        chunks = []
        async for chunk in listen(24000):
            chunks.append(chunk)
            if sum(map(len, chunks)) >= 24000: break
        assert len(chunks) > 1 and all(len(chunk)%2 == 0 for chunk in chunks)
    cfloop.run(story())


def test_photo_export(tmp_path):
    async def story():
        assets = await photos(3)
        if not assets: pytest.skip('photo library is empty')
        for photo in assets: assert photo['id'] and photo['w'] > 0 and photo['h'] > 0
        exported = await save_photo(assets[0]['id'], tmp_path/'photo')
        assert exported.stat().st_size > 1000
    cfloop.run(story())
