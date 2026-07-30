"Photos, audio recording, and speech transcription, each needing its Imp permission"

import asyncio, tempfile

from fastcore.utils import *
from AVFoundation import AVAudioRecorder, AVCapturePhotoSettings, AVFormatIDKey, AVNumberOfChannelsKey, AVSampleRateKey
from Foundation import NSObject, NSOperationQueue, NSSortDescriptor
from Photos import PHAsset, PHFetchOptions, PHImageManager, PHImageRequestOptions

from fastcore.aio import athreaded
from .cocoa import Sig, camera, chk, fetchiter, mk, nsurl, pydate, wait_cb
from .imp import need, aneed

__all__ = ['photos', 'save_photo', 'snap', 'record', 'transcribe']


def _phdict(a):
    d = dict(id=str(a.localIdentifier()), created=pydate(a.creationDate()), w=int(a.pixelWidth()),
        h=int(a.pixelHeight()), video=a.mediaType()==2, favorite=bool(a.isFavorite()))
    if a.location() is not None: d['lat'],d['lon'] = a.location().coordinate()
    return d


@athreaded
def photos(
    n:int=10 # How many, newest first
):
    "Metadata for the newest `n` photo library assets: id, created, size, location, and kind"
    need('photos')
    o = mk(PHFetchOptions, sortDescriptors=[NSSortDescriptor.sortDescriptorWithKey_ascending_('creationDate', False)], fetchLimit=n)
    return L(fetchiter(PHAsset.fetchAssetsWithOptions_(o))).map(_phdict)


@athreaded
def save_photo(
    id:str, # An id from `photos`
    path # Where to write the original image data
):
    "Export an asset's original data to `path`, returning it"
    need('photos')
    a = PHAsset.fetchAssetsWithLocalIdentifiers_options_([id], None).firstObject()
    if a is None: raise ValueError(f'no asset {id}')
    o = mk(PHImageRequestOptions, synchronous=True, networkAccessAllowed=True)
    data, *_ = wait_cb(lambda cb: PHImageManager.defaultManager().requestImageDataAndOrientationForAsset_options_resultHandler_(a, o, cb))
    if data is None: raise RuntimeError(f'no data for {id}')
    path = Path(path)
    path.write_bytes(bytes(data))
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
        d = _SnapDelegate.alloc().init()
        d.data, d.sig = None, Sig()
        outp.capturePhotoWithSettings_delegate_(AVCapturePhotoSettings.photoSettings(), d)
        await d.sig.wait(10)
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
    rec = chk(AVAudioRecorder.alloc().initWithURL_settings_error_(nsurl(path), settings, None))
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
    rec.setQueue_(mk(NSOperationQueue))  # keep handlers off the main queue
    req = SFSpeechURLRecognitionRequest.alloc().initWithURL_(nsurl(path))
    got, sig = {}, Sig()
    def cb(res, err):
        if res is not None and res.isFinal():
            got['text'] = str(res.bestTranscription().formattedString())
            sig.set()
        elif err is not None:
            got.setdefault('err', err)
            sig.set()
    rec.recognitionTaskWithRequest_resultHandler_(req, cb)
    await sig.wait(timeout)
    if 'text' not in got: raise RuntimeError(str(got['err']))
    return got['text']
