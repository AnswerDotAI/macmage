"Photos, audio recording, and speech transcription, each needing its Imp permission"

import tempfile, threading, time
from datetime import datetime

from fastcore.utils import *
from AVFoundation import (AVAudioRecorder, AVCaptureDevice, AVCaptureDeviceInput, AVCapturePhotoOutput,
    AVCapturePhotoSettings, AVCaptureSession, AVFormatIDKey, AVMediaTypeVideo, AVNumberOfChannelsKey, AVSampleRateKey)
from Foundation import NSDate, NSDefaultRunLoopMode, NSObject, NSOperationQueue, NSRunLoop, NSSortDescriptor, NSURL
from Photos import PHAsset, PHFetchOptions, PHImageManager, PHImageRequestOptions

from .imp import need
from .util import apart

__all__ = ['photos', 'save_photo', 'snap', 'snap_py', 'record', 'transcribe']


def _phdict(a):
    d = dict(id=str(a.localIdentifier()),
        created=datetime.fromtimestamp(a.creationDate().timeIntervalSince1970()) if a.creationDate() else None,
        w=int(a.pixelWidth()), h=int(a.pixelHeight()), video=a.mediaType()==2, favorite=bool(a.isFavorite()))
    if a.location() is not None: d['lat'],d['lon'] = a.location().coordinate()
    return d


def photos(
    n:int=10 # How many, newest first
):
    "Metadata for the newest `n` photo library assets: id, created, size, location, and kind"
    need('photos')
    o = PHFetchOptions.alloc().init()
    o.setSortDescriptors_([NSSortDescriptor.sortDescriptorWithKey_ascending_('creationDate', False)])
    o.setFetchLimit_(n)
    res = PHAsset.fetchAssetsWithOptions_(o)
    return L(res.objectAtIndex_(i) for i in range(res.count())).map(_phdict)


def save_photo(
    id:str, # An id from `photos`
    path # Where to write the original image data
):
    "Export an asset's original data to `path`, returning it"
    need('photos')
    a = PHAsset.fetchAssetsWithLocalIdentifiers_options_([id], None).firstObject()
    if a is None: raise ValueError(f'no asset {id}')
    o = PHImageRequestOptions.alloc().init()
    o.setSynchronous_(True)
    o.setNetworkAccessAllowed_(True)
    got = {}
    def cb(data, uti, orient, info): got['data'] = data
    PHImageManager.defaultManager().requestImageDataAndOrientationForAsset_options_resultHandler_(a, o, cb)
    if got.get('data') is None: raise RuntimeError(f'no data for {id}')
    path = Path(path)
    path.write_bytes(bytes(got['data']))
    return path


def snap(
    path=None # Where to write the still; a temp file if None
):
    "Capture a photo from the default camera in a fresh process (`apart`), returning the path"
    return apart(snap_py, path, timeout=15)  # capture takes a couple of seconds, so the default is roomier still


# The pyobjc capture that `snap` runs in a fresh process via `apart`: in-process it cannot
# coexist with the hotkey engine's *background* Carbon loop, which breaks main-run-loop pumping
# (see DEV.md), though under `keys.run_loop` (the agent's arrangement) it works with no pumping.
# `Imp --snap` remains as the sample bytes-over-stdout Swift verb until another replaces it.
class _SnapDelegate(NSObject):
    def captureOutput_didFinishProcessingPhoto_error_(self, o, photo, error):
        self.data = photo.fileDataRepresentation()
        self.done = True


def snap_py(
    path=None # Where to write the still; a temp file if None
):
    "Capture a photo from the default camera with pyobjc directly, returning the path"
    need('camera')
    from . import keys
    if keys._started and not keys._own_loop: raise RuntimeError('the hotkey engine is running its background Carbon loop, which breaks main-run-loop pumping, so the photo delegate can never arrive (see DEV.md); use snap(), or run under keys.run_loop')
    path = Path(path or tempfile.mktemp(suffix='.jpg'))
    dev = AVCaptureDevice.defaultDeviceWithMediaType_(AVMediaTypeVideo)
    if dev is None: raise RuntimeError('no camera')
    sess = AVCaptureSession.alloc().init()
    inp, err = AVCaptureDeviceInput.deviceInputWithDevice_error_(dev, None)
    if err is not None: raise RuntimeError(str(err))
    sess.addInput_(inp)
    outp = AVCapturePhotoOutput.alloc().init()
    sess.addOutput_(outp)
    sess.startRunning()
    time.sleep(1.0)  # the first frames are dark while exposure settles
    d = _SnapDelegate.alloc().init()
    d.done,d.data = False,None
    outp.capturePhotoWithSettings_delegate_(AVCapturePhotoSettings.photoSettings(), d)
    # The delegate may be served by the main queue, so run the loop rather than block (see Imp's DEV.md)
    end = time.time()+10
    while not d.done and time.time() < end:
        NSRunLoop.currentRunLoop().runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.dateWithTimeIntervalSinceNow_(0.1))
    sess.stopRunning()
    if d.data is None: raise RuntimeError('no photo data')
    path.write_bytes(bytes(d.data))
    return path



def record(
    secs:float=5, # How long to record
    path=None # Where to write the m4a; a temp file if None
):
    "Record from the default microphone, returning the path"
    need('microphone')
    path = Path(path or tempfile.mktemp(suffix='.m4a'))
    settings = {AVFormatIDKey: int.from_bytes(b'aac ', 'big'), AVSampleRateKey: 44100.0, AVNumberOfChannelsKey: 1}
    rec, err = AVAudioRecorder.alloc().initWithURL_settings_error_(NSURL.fileURLWithPath_(str(path)), settings, None)
    if err is not None: raise RuntimeError(str(err))
    rec.record()
    time.sleep(secs)
    rec.stop()
    return path


def transcribe(
    path, # An audio file (anything AVFoundation reads)
    timeout:float=60 # How long to wait for the final result
):
    "Speech in `path` as text, via Apple's recognizer"
    need('speech')
    from Speech import SFSpeechRecognizer, SFSpeechURLRecognitionRequest
    rec = SFSpeechRecognizer.alloc().init()
    rec.setQueue_(NSOperationQueue.alloc().init())  # handlers default to the main queue, which the caller is blocking
    req = SFSpeechURLRecognitionRequest.alloc().initWithURL_(NSURL.fileURLWithPath_(str(Path(path))))
    got, evt = {}, threading.Event()
    def cb(res, err):
        if res is not None and res.isFinal():
            got['text'] = str(res.bestTranscription().formattedString())
            evt.set()
        elif err is not None:
            got.setdefault('err', err)
            evt.set()
    rec.recognitionTaskWithRequest_resultHandler_(req, cb)
    if not evt.wait(timeout): raise TimeoutError('recognizer did not finish')
    if 'text' not in got: raise RuntimeError(str(got['err']))
    return got['text']
