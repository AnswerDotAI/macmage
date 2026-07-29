"Photos, audio recording, and speech transcription, each needing its Imp permission"

import tempfile, threading, time
from datetime import datetime

from fastcore.utils import *
from AVFoundation import AVAudioRecorder, AVFormatIDKey, AVNumberOfChannelsKey, AVSampleRateKey
from Foundation import NSSortDescriptor, NSURL
from Photos import PHAsset, PHFetchOptions, PHImageManager, PHImageRequestOptions

from .imp import need

__all__ = ['photos', 'save_photo', 'record', 'transcribe']


def _phdict(a):
    d = dict(id=str(a.localIdentifier()),
        created=datetime.fromtimestamp(a.creationDate().timeIntervalSince1970()) if a.creationDate() else None,
        w=int(a.pixelWidth()), h=int(a.pixelHeight()), video=a.mediaType()==2, favorite=bool(a.isFavorite()))
    if a.location() is not None:
        c = a.location().coordinate()
        d['lat'],d['lon'] = c.latitude,c.longitude
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
