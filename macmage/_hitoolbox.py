"""Minimal HIToolbox (Carbon) bridge: the hotkey APIs pyobjc doesn't wrap.

The pyobjc metadata in `_metadata.py` is taken from glyph's quickmachotkey (MIT licensed),
which documents the authoritative references: HIToolbox's `.bridgesupport` file, and the
`CarbonEventsCore.h` / `CarbonEvents.h` headers in the macOS SDK.
"""
import objc

from . import _metadata

_path = objc.pathForFramework(
    '/System/Library/Frameworks/Carbon.framework/Versions/Current/Frameworks/HIToolbox.framework')
_dir, _getattr = objc.createFrameworkDirAndGetattr(
    name='Foundation', frameworkIdentifier='com.apple.HIToolbox', frameworkPath=_path,
    globals_dict=globals(), inline_list=None, parents=(), metadict=_metadata.__dict__)
__dir__, __getattr__ = _dir, _getattr

objc.loadBundleFunctions(objc.loadBundle('HIToolbox', {}, bundle_path=_path), globals(),
                        [('RunApplicationEventLoop', b'v'), ('QuitApplicationEventLoop', b'v')])
