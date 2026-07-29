"""Driving Imp through `Imp()`. The argv rules are pure, so they are pinned directly;
the live runs go through `echo` and `cat`, exercising the real launcher."""
import pytest

import sys
from macmage import ImpError, Imp
from macmage.imp import _argv, launcher


def test_argv_construction_rules():
    "Flags come in order ahead of args; True is a bare flag; lists spread; underscores hyphenate"
    assert _argv('echo', 'hi') == [str(launcher), 'echo', 'hi']
    assert _argv(status=True) == [str(launcher), '--status']
    assert _argv(grant='microphone') == [str(launcher), '--grant', 'microphone']
    assert _argv(alert=('Del?', '', 'Del', 'Cancel')) == [str(launcher), '--alert', 'Del?', '', 'Del', 'Cancel']
    assert _argv(some_flag=1) == [str(launcher), '--some-flag', '1']
    assert _argv('cmd', check='screen') == [str(launcher), '--check', 'screen', 'cmd']


def test_live_run_captures_output():
    "A command runs under Imp, with stdout captured and stdin fed"
    r = Imp('echo', 'hi')
    assert r.returncode == 0 and r.stdout == 'hi\n'
    assert Imp('cat', input='meow').stdout == 'meow'


def test_missing_imp_names_the_install(monkeypatch, tmp_path):
    "Without Imp the error says how to get it"
    monkeypatch.setattr(sys.modules['macmage.imp'], 'launcher', tmp_path/'nope')
    with pytest.raises(ImpError, match='install.sh'): Imp(status=True)
