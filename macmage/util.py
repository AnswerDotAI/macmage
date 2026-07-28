"Small shared helpers"

from fastcore.utils import *
import time

__all__ = ['wait_until']


def wait_until(
    f:callable, # Called repeatedly until it returns something truthy
    secs:float=5, # Give up after this long
    pause:float=0.05 # Wait between attempts
):
    "Poll `f` until it returns something truthy and return that, or None once `secs` has elapsed"
    end = time.time()+secs
    while True:
        res = f()
        if res: return res
        if time.time()>=end: return None
        time.sleep(pause)
