"""Clipboard history, as a cantrip: `watch_clip` remembers what you copy, and a hotkey
offers the last ten through `pick`.

To use it, copy this file next to your `config.py` and add `import clipboard_history`
there. Copies marked concealed (the password-manager convention) are never recorded,
but everything else lands in `clip_history.jsonl` in plain text.
"""
import json

from fastcore.xdg import xdg_state_home

from macmage import mage, pick, set_clip, watch_clip

hist = xdg_state_home()/'macmage'/'clip_history.jsonl'
KEEP = 300


def _load(): return [json.loads(l) for l in hist.read_text().splitlines()] if hist.exists() else []


@watch_clip
def remember(s):
    rows = [r for r in _load() if r != s] + [s]   # re-copying an old entry moves it to the front
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text('\n'.join(json.dumps(r) for r in rows[-KEEP:]) + '\n')


@mage(keys='ctrl-alt-cmd-v')
def clip_history():
    rows = _load()[::-1][:10]                     # newest first; row 0 is the current clipboard
    if not rows: return
    previews = [' '.join(r.split())[:70] or '(whitespace)' for r in rows]
    if (i := pick('Clipboard history', previews)) is not None: set_clip(rows[i])
