"""Recording, transcription, and photo metadata against the real devices and library, so
these need Imp's `microphone`, `speech`, and `photos` grants. `say` synthesizes known
speech, giving the transcription check ground truth without anyone talking."""
import subprocess

import pytest

from macmage import photos, record, save_photo, snap, snap_py, transcribe


def test_transcribe_knows_what_say_said(tmp_path):
    "Apple's recognizer round-trips Apple's synthesizer"
    aiff = tmp_path/'hello.aiff'
    subprocess.run(['say', '-o', str(aiff), 'hello world'], check=True)
    assert 'hello' in transcribe(aiff).lower()


def test_record_writes_audio(tmp_path):
    "A short recording produces a non-trivial m4a"
    p = record(0.5, tmp_path/'clip.m4a')
    assert p.exists() and p.stat().st_size > 1000


def test_snap_captures(tmp_path):
    "Both snap routes deliver a real still; the pyobjc twin only outside the background hotkey loop"
    assert snap(tmp_path/'a.jpg').stat().st_size > 10000
    from macmage import keys
    if keys._started and not keys._own_loop: pytest.skip('background hotkey loop active: snap_py cannot pump the main loop (see DEV.md); test_loop.py covers the run_loop arrangement')
    assert snap_py(tmp_path/'b.jpg').stat().st_size > 10000



def test_photos_metadata(tmp_path):
    "The newest assets carry ids and sizes, and one exports as real image data"
    ps = photos(3)
    for p in ps: assert p['id'] and p['w'] > 0 and p['h'] > 0
    if ps:
        f = save_photo(ps[0]['id'], tmp_path/'photo')
        assert f.stat().st_size > 1000
