"Development helpers for working on macmage from the kernel."

from fastcore.utils import *
from macmage.imp import launcher

__all__ = ['run_tests']


def run_tests(
    *args # Extra pytest arguments; defaults to the whole suite
):
    "Run the tests under Imp, whose permissions the keyboard tests need"
    pytest = Path(sys.executable).with_name('pytest')
    return run(launcher, pytest, '-q', *(args or ['tests']), ignore_ex=True)[1]
