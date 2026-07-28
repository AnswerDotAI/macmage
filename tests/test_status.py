"""What `macmage --status` reports, exercised through its failing branches.

The passing branches depend on this machine being set up, so they are not asserted here;
what matters is that a failure names the fix, and that a logged config error goes stale
once the file is edited (saving `config.py` is what makes the agent reload it).
"""
import time

import macmage


def test_missing_pieces_name_their_fix(monkeypatch, tmp_path):
    "A failing check answers with a reason a person can act on"
    monkeypatch.setattr(macmage, 'launcher', tmp_path/'nope')
    ok, msg = macmage._st_imp()
    assert not ok and 'install.sh' in msg

    monkeypatch.setattr(macmage, 'config_dir', tmp_path)
    ok, msg = macmage._st_config()
    assert not ok and 'config.py' in msg

    monkeypatch.setattr(macmage, '_layout_cache', tmp_path/'layout.json')
    ok, msg = macmage._st_layout()
    assert not ok and 'macmage --install' in msg


def test_a_config_error_goes_stale_when_the_file_is_edited(monkeypatch, tmp_path):
    "An old traceback is history; one dated after the last edit is a live failure"
    state = tmp_path/'state'
    state.mkdir()
    (tmp_path/'config.py').write_text('x = 1\n')
    log = state/'stderr.log'
    monkeypatch.setattr(macmage, 'config_dir', tmp_path)
    monkeypatch.setattr(macmage, 'state_dir', state)

    log.write_text('2020-01-01 00:00:00 macmage: unhandled exception in config\n')
    ok, msg = macmage._st_config()
    assert ok, msg

    later = time.strftime('%F %T', time.localtime(time.time()+60))
    log.write_text(f'{later} macmage: unhandled exception in config\n')
    ok, msg = macmage._st_config()
    assert not ok and 'raised at' in msg
