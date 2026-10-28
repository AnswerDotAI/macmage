"Imp's argument protocol and captured stdin/stdout, without opening native UI or requesting permissions."
from macmage import Imp
from macmage.imp import _argv, launcher


def test_imp_protocol():
    assert _argv('echo', 'hi') == [str(launcher), 'echo', 'hi']
    assert _argv(status=True) == [str(launcher), '--status']
    assert _argv(grant='microphone') == [str(launcher), '--grant', 'microphone']
    assert _argv(alert=('Del?', '', 'Del', 'Cancel')) == [str(launcher), '--alert', 'Del?', '', 'Del', 'Cancel']
    assert _argv(some_flag=1) == [str(launcher), '--some-flag', '1']
    assert _argv('cmd', check='screen') == [str(launcher), '--check', 'screen', 'cmd']
    r = Imp('echo', 'hi')
    assert r.returncode == 0 and r.stdout == 'hi\n'
    assert Imp('cat', input='meow').stdout == 'meow'
