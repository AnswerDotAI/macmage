"Photos, audio recording, and speech transcription, each needing its Imp permission"

import asyncio, tempfile
from types import SimpleNamespace
from datetime import datetime

from fastcore.utils import *
from AVFoundation import (AVAudioRecorder, AVCaptureDevice, AVCaptureDeviceInput, AVCapturePhotoOutput,
    AVCapturePhotoSettings, AVCaptureSession, AVFormatIDKey, AVMediaTypeVideo, AVNumberOfChannelsKey, AVSampleRateKey)
from Foundation import NSObject, NSOperationQueue, NSSortDescriptor, NSURL
from Photos import PHAsset, PHFetchOptions, PHImageManager, PHImageRequestOptions

from fastcore.aio import athreaded
from .imp import need, aneed

__all__ = ['photos', 'save_photo', 'snap', 'record', 'transcribe']


def _phdict(a):
    d = dict(id=str(a.localIdentifier()),
        created=datetime.fromtimestamp(a.creationDate().timeIntervalSince1970()) if a.creationDate() else None,
        w=int(a.pixelWidth()), h=int(a.pixelHeight()), video=a.mediaType()==2, favorite=bool(a.isFavorite()))
    if a.location() is not None: d['lat'],d['lon'] = a.location().coordinate()
    return d


@athreaded
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


@athreaded
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


# `Imp --snap` remains as the sample bytes-over-stdout Swift verb; python captures in-process.
class _SnapDelegate(NSObject):
    def captureOutput_didFinishProcessingPhoto_error_(self, o, photo, error):
        self.data = photo.fileDataRepresentation()
        self.signal()


async def _signalled(obj, coro_wait):
    "Arm `obj.signal` to set an event from any thread or queue, then await `coro_wait(event)`"
    loop, evt = asyncio.get_running_loop(), asyncio.Event()
    obj.signal = lambda: loop.call_soon_threadsafe(evt.set)
    return await coro_wait(evt)


async def snap(
    path=None # Where to write the still; a temp file if None
):
    "Capture a photo from the default camera, returning the path"
    await aneed('camera')
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
    try:
        await asyncio.sleep(1.0)  # the first frames are dark while exposure settles
        d = _SnapDelegate.alloc().init()
        d.data = None
        async def _wait(evt):
            outp.capturePhotoWithSettings_delegate_(AVCapturePhotoSettings.photoSettings(), d)
            await asyncio.wait_for(evt.wait(), 10)
        await _signalled(d, _wait)
    finally: sess.stopRunning()
    if d.data is None: raise RuntimeError('no photo data')
    path.write_bytes(bytes(d.data))
    return path


async def record(
    secs:float=5, # How long to record
    path=None # Where to write the m4a; a temp file if None
):
    "Record from the default microphone, returning the path"
    await aneed('microphone')
    path = Path(path or tempfile.mktemp(suffix='.m4a'))
    settings = {AVFormatIDKey: int.from_bytes(b'aac ', 'big'), AVSampleRateKey: 44100.0, AVNumberOfChannelsKey: 1}
    rec, err = AVAudioRecorder.alloc().initWithURL_settings_error_(NSURL.fileURLWithPath_(str(path)), settings, None)
    if err is not None: raise RuntimeError(str(err))
    rec.record()
    try: await asyncio.sleep(secs)
    finally: rec.stop()
    return path


async def transcribe(
    path, # An audio file (anything AVFoundation reads)
    timeout:float=60 # How long to wait for the final result
):
    "Speech in `path` as text, via Apple's recognizer"
    await aneed('speech')
    from Speech import SFSpeechRecognizer, SFSpeechURLRecognitionRequest
    rec = SFSpeechRecognizer.alloc().init()
    rec.setQueue_(NSOperationQueue.alloc().init())  # keep handlers off the main queue
    req = SFSpeechURLRecognitionRequest.alloc().initWithURL_(NSURL.fileURLWithPath_(str(Path(path))))
    got, sig = {}, SimpleNamespace()
    def cb(res, err):
        if res is not None and res.isFinal():
            got['text'] = str(res.bestTranscription().formattedString())
            sig.signal()
        elif err is not None:
            got.setdefault('err', err)
            sig.signal()
    async def _wait(evt):
        rec.recognitionTaskWithRequest_resultHandler_(req, cb)
        await asyncio.wait_for(evt.wait(), timeout)
    await _signalled(sig, _wait)
    if 'text' not in got: raise RuntimeError(str(got['err']))
    return got['text']
