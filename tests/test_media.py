"""Recording, transcription, and photo metadata against the real devices and library, so
these need Imp's `microphone`, `speech`, and `photos` grants. `say` synthesizes known
speech, giving the transcription check ground truth without anyone talking."""
import subprocess

from macmage import photos, record, save_photo, snap, transcribe


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
    "The camera delivers a real still through Imp"
    p = snap(tmp_path/'still.jpg')
    assert p.stat().st_size > 10000



def test_photos_metadata(tmp_path):
    "The newest assets carry ids and sizes, and one exports as real image data"
    ps = photos(3)
    for p in ps: assert p['id'] and p['w'] > 0 and p['h'] > 0
    if ps:
        f = save_photo(ps[0]['id'], tmp_path/'photo')
        assert f.stat().st_size > 1000
