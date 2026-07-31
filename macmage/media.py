"Photos, audio recording, and speech transcription, each needing its Imp permission"

import asyncio, tempfile

from fastcore.utils import *
from fastcore.aio import athreaded
from Foundation import NSObject  # raw: delegate subclasses come from unswept NSObject
from fastcocoa import Sig, camera, nsurl, sortd, topy, wait_cb
from fastcocoa.avfoundation import AVAudioRecorder, AVCapturePhotoSettings, AVFormatIDKey, AVNumberOfChannelsKey, AVSampleRateKey
from fastcocoa.foundation import NSOperationQueue
from fastcocoa.photos import PHAsset, PHImageManager
from fastcocoa.speech import SFSpeechRecognizer, SFSpeechURLRecognitionRequest

from .imp import need, aneed

__all__ = ['photos', 'save_photo', 'snap', 'record', 'transcribe']


def _phdict(a):
    d = dict(id=a.localIdentifier, created=a.creationDate, w=a.pixelWidth, h=a.pixelHeight, video=a.mediaType==2, favorite=a.favorite)
    if a.location is not None: d['lat'],d['lon'] = a.location.coordinate
    return d


@athreaded
def photos(
    n:int=10 # How many, newest first
):
    "Metadata for the newest `n` photo library assets: id, created, size, location, and kind"
    need('photos')
    return PHAsset.fetchAssets(sortDescriptors=sortd('-creationDate'), fetchLimit=n).map(_phdict)


@athreaded
def save_photo(
    id:str, # An id from `photos`
    path # Where to write the original image data
):
    "Export an asset's original data to `path`, returning it"
    need('photos')
    a = req(first(PHAsset.fetchAssets(localIdentifiers=[id], options=None)), f'no asset {id}')
    data = req(wait_cb(PHImageManager.default().requestImageDataAndOrientation, for_=a, networkAccessAllowed=True,
        resultHandler=...)[0], f'no data for {id}', RuntimeError)
    path = Path(path)
    path.write_bytes(data)
    return path


# `Imp --snap` remains as the sample bytes-over-stdout Swift verb; python captures in-process.
class _SnapDelegate(NSObject):
    def captureOutput_didFinishProcessingPhoto_error_(self, o, photo, error):
        self.data = photo.fileDataRepresentation()
        self.sig.set()


async def snap(
    path=None # Where to write the still; a temp file if None
):
    "Capture a photo from the default camera, returning the path"
    await aneed('camera')
    path = Path(path or tempfile.mktemp(suffix='.jpg'))
    with camera() as outp:
        await asyncio.sleep(1.0)  # the first frames are dark while exposure settles
        d = _SnapDelegate()
        d.data, d.sig = None, Sig()
        outp.capturePhoto(settings=AVCapturePhotoSettings.photoSettings(), delegate=d)
        await d.sig.wait(10)
    path.write_bytes(bytes(req(d.data, 'no photo data', RuntimeError)))
    return path


async def record(
    secs:float=5, # How long to record
    path=None # Where to write the m4a; a temp file if None
):
    "Record from the default microphone, returning the path"
    await aneed('microphone')
    path = Path(path or tempfile.mktemp(suffix='.m4a'))
    settings = {AVFormatIDKey: int.from_bytes(b'aac ', 'big'), AVSampleRateKey: 44100.0, AVNumberOfChannelsKey: 1}
    rec = AVAudioRecorder(URL=nsurl(path), settings=settings)
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
    rec = SFSpeechRecognizer()
    rec.queue = NSOperationQueue()  # keep handlers off the main queue
    sreq = SFSpeechURLRecognitionRequest(URL=nsurl(path))
    got, sig = {}, Sig()
    def cb(res, err):
        res = topy(res)  # a raw block callback is the one path that doesn't cross the bridge: sweep it ourselves
        if res is not None and res.final:
            got['text'] = res.bestTranscription.formattedString
            sig.set()
        elif err is not None:
            got.setdefault('err', err)
            sig.set()
    rec.recognitionTask(request=sreq, resultHandler=cb)
    await sig.wait(timeout)
    if 'text' not in got: raise RuntimeError(str(got['err']))
    return got['text']
