"""Plumbing for pyobjc's recurring shapes, so leaf modules read as intent rather than ceremony.
Everything here traffics in NSObjects, so nothing is public macmage API: import from leaf modules only."""

import asyncio, threading
from contextlib import contextmanager
from datetime import datetime

from fastcore.utils import *
from AVFoundation import AVCaptureDevice, AVCaptureDeviceInput, AVCapturePhotoOutput, AVCaptureSession, AVMediaTypeVideo
from Foundation import NSDate, NSURL

__all__ = ['chk', 'setprops', 'mk', 'nsurl', 'nsdate', 'pydate', 'fetchiter', 'Sig', 'wait_cb', 'camera']


def chk(res):
    "Unpack a Cocoa `(value, error)` or `(ok, error)` out-param pair, raising on a reported failure"
    v, err = res
    if err is not None or v is False: raise RuntimeError(str(err) if err is not None else 'call failed')
    return v


def setprops(o, **kwargs):
    "Each kwarg through its Cocoa setter: `setprops(o, fooBar=x)` calls `o.setFooBar_(x)`, returning `o`"
    for k,v in kwargs.items(): getattr(o, f'set{k[0].upper()}{k[1:]}_')(v)
    return o


def mk(cls, **kwargs):
    "`cls.alloc().init()`, configured by `setprops`"
    return setprops(cls.alloc().init(), **kwargs)


def nsurl(path): return NSURL.fileURLWithPath_(str(Path(path).expanduser()))
def nsdate(dt): return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())
def pydate(d): return datetime.fromtimestamp(d.timeIntervalSince1970()) if d is not None else None


def fetchiter(res):
    "A Cocoa indexed collection (e.g. `PHFetchResult`) as a Python iterator"
    return (res.objectAtIndex_(i) for i in range(res.count()))


class Sig:
    "Await a Cocoa callback from the loop: pass `sig.set` (any thread or queue) and `await sig.wait(secs)`"
    def __init__(self): self.loop, self.evt = asyncio.get_running_loop(), asyncio.Event()
    def set(self): self.loop.call_soon_threadsafe(self.evt.set)
    async def wait(self,
        secs:float # Seconds before TimeoutError
    ): await asyncio.wait_for(self.evt.wait(), secs)


def wait_cb(
    f, # Called with a completion callback: `f(cb)` must arrange `cb(*args)` from any thread
    secs:float=10 # Seconds before TimeoutError
):
    "Blocking twin of `Sig` for `@athreaded` bodies: run `f`, return the callback's args"
    got, evt = [], threading.Event()
    def cb(*args):
        got.extend(args)
        evt.set()
    f(cb)
    if not evt.wait(secs): raise TimeoutError('Cocoa callback did not arrive')
    return got


@contextmanager
def camera():
    "A running capture session on the default camera, yielding its photo output"
    dev = AVCaptureDevice.defaultDeviceWithMediaType_(AVMediaTypeVideo)
    if dev is None: raise RuntimeError('no camera')
    sess = AVCaptureSession.alloc().init()
    sess.addInput_(chk(AVCaptureDeviceInput.deviceInputWithDevice_error_(dev, None)))
    outp = AVCapturePhotoOutput.alloc().init()
    sess.addOutput_(outp)
    sess.startRunning()
    try: yield outp
    finally: sess.stopRunning()
