# macmage

`macmage` runs `$XDG_CONFIG_HOME/macmage/config.py` as ordinary Python in a background macOS LaunchAgent, and provides the keyboard automation that configuration usually wants: global hotkeys, keystroke watching, and synthetic typing. `XDG_CONFIG_HOME` defaults to `~/.config`, and the configuration can use any package installed in the same virtual environment.

The keyboard functions work anywhere, agent or not, so `macmage` is usable as a plain library too.

## Install

Permissions on macOS belong to a program, not to a script, so `macmage` runs under [Imp](https://github.com/AnswerDotAI/imp), a small signed app that holds the grants and passes them to whatever it launches. Install Imp first, and grant it Accessibility, which is what synthetic typing and keystroke watching need:

```bash
curl -fsSL https://raw.githubusercontent.com/AnswerDotAI/imp/main/install.sh | sh
Imp --grant accessibility
```

Then install `macmage` into a virtual environment and register its LaunchAgent:

```bash
pip install git+https://github.com/AnswerDotAI/macmage.git
macmage --install
```

`macmage --install` writes `~/Library/LaunchAgents/com.answerdotai.macmage.plist`, which runs the current virtual environment's `python` under Imp. It is also how you restart the agent: run it again after upgrading `macmage` or Imp, after granting a permission, and after moving or rebuilding the virtual environment, since the plist names an absolute path. It never creates or modifies `config.py`.

`macmage --status` checks the whole arrangement, and `macmage --uninstall` stops the agent and removes its plist, leaving the configuration, logs, `Imp.app`, and its permission grants alone.

## Configure

Create `$XDG_CONFIG_HOME/macmage/config.py`, normally `~/.config/macmage/config.py`. `examples/config.py` in the repo is a complete working configuration - menus, demos, clipboard transforms, dictation - ready to copy or crib from, and `import config_local` at its foot is the hook for additions that stay out of any repo. This example binds Alt-` to type a backtick, a zero-width space, and two more backticks:

```python
from macmage import mage, type_text

@mage(keys='alt-`')
async def backticks(): await type_text('`​``')
```

`backticks` here is a cantrip: a small function bound to a trigger, which is all any macmage configuration is. The triggers are hotkeys (`keys=`), held modifiers (`holdmod`), leader keys (`leader`), and clipboard changes (`watch_clip`); the actions are whatever Python you like, with typing, clipboard, application, and panel helpers below. `@mage` wraps a cantrip so an exception is logged instead of stopping the process. A cantrip may be `async def`: the agent runs on an asyncio loop (via [cfloop](https://github.com/AnswerDotAI/cfloop)), so async cantrips run concurrently as tasks, while plain ones run inline and should stay quick, since a slow one delays every other trigger. `hold=True` takes a generator instead - sync or async - for cantrips that run while the key is held. The `cantrips/` directory in the repo holds ready-made ones, written to be copied next to `config.py` and imported from it.

`config.py` need not block. `macmage` keeps the process alive, and re-executes it whenever any `.py` file in the configuration directory changes, so a bare `touch` reloads it. An error while loading it is logged to `stderr.log` and shown in a panel with the traceback, and the process waits for the next change rather than exiting, so the answer to "did my save load?" is that a panel means no. The configuration can import sibling files from its directory as ordinary Python modules.

To run the same configuration in the foreground, use `Imp macmage` rather than bare `macmage`. Started directly from a terminal, macOS treats the process as the terminal, so it has your terminal's permissions instead of Imp's.

## Hotkeys

```python
from macmage import hotkey

@hotkey('ctrl-alt-cmd-t')
def hello(): print('pressed')
```

Hotkeys go through Carbon's `RegisterEventHotKey`, so they need no macOS permission at all, and the bound keystroke is suppressed system-wide rather than reaching the frontmost app.

Combos name keys as typed on the current keyboard layout (`'cmd-alt-`'`, `'ctrl-shift-space'`). They can also name special keys such as `'esc'`, `'f5'` and `'left'` (see `specials`), or a raw key code as `'alt-<50>'`. Registering a combo again replaces its handler, and `unhotkey(combo)` releases it.

Hotkeys dispatch on the agent's asyncio loop, so registration needs that loop running: the agent provides it, and a standalone script wraps its main in `run_loop(setup)`, registering inside `setup`. Async cantrips run as concurrent tasks; plain ones run inline on the loop, so a slow one delays other triggers (asyncio debug mode names offenders), and `hold` cantrips are async generators, running as tasks. Everything is released at process exit. A process that replaces itself with `os.exec*` skips that, so call `stop_keys()` first.

To do something for as long as a key is held, pass `hold=True` and write the handler as an async generator. The body before its `yield` runs on the press, and the rest on the release.

```python
@hotkey('ctrl-alt-cmd-r', hold=True)
async def record_while_held():
    rec = start_recording()
    yield
    await type_text(await transcribe(rec.stop()))
```

The generator runs as a task and waits at the `yield`, so a body awaiting for the length of the hold cannot stall other cantrips, and whatever it holds between the two halves stays an ordinary local variable. Carbon repeats nothing, so a long hold is exactly one press and one release. To handle the two edges separately instead, pass `up=`, as in `hotkey(combo, on_press, up=on_release)`.

A bare modifier such as right Option cannot be a Carbon hotkey, so `holdmod` reads the event tap instead, and takes the same handlers:

```python
from macmage import holdmod

@holdmod('ropt', hold=True)
async def talk():
    rec = start_recording()
    yield
    rec.stop()
```

`modkeys` lists the names, which are a side plus a modifier (`'ropt'`, `'lshift'`, `'rcmd'`), plus `'fn'`. Unlike `hotkey`, `holdmod` needs an Accessibility grant, and it cannot suppress the key, so the modifier still reaches whatever is focused. `unholdmod(name)` stops it.

## Modes

A leader key captures the next keystroke, so a family of related commands costs one combination instead of one each:

```python
from functools import partial
from macmage import leader, map_clip

leader('ctrl-alt-cmd-c', {
    'u': partial(map_clip, str.upper),
    'l': partial(map_clip, str.lower)})
```

While the mode is active its keys are registered as bare hotkeys, so they are suppressed rather than typed, and one press runs its handler and releases them again. `escape` leaves without running anything, and so does waiting out `timeout`, which defaults to three seconds, so a stray leader press can never leave the keyboard captured. Entering a mode takes a few milliseconds, well under the gap between two deliberate keystrokes. `unleader(combo)` releases the leader itself.

The keys are ordinary combinations rather than single letters, so a mode can bind `'cmd-s'` as readily as `'s'`.


## Watching keystrokes

```python
from macmage import watch

@watch
def log(kind, vk, flags): print(kind, vk, flags)
```

`watch` reports every key event system-wide through a listen-only event tap. `kind` is `'down'`, `'up'`, or `'flags'` (a modifier change), `vk` the key code, and `flags` the modifier mask. It observes without consuming, so every event still reaches its application, including combos a `hotkey` in the same process claims. `unwatch(fn)` stops the reports. Watching needs an Accessibility grant.

## Typing

```python
from macmage import press, type_text

await type_text('Hello from macmage\n')
press('cmd-s')
```

`type_text` (a coroutine, like everything here that touches the outside world) types a string into the focused application. `press` sends one key combination. Both need an Accessibility grant, and raise `ImpError` when it is missing rather than failing silently, since macOS drops unauthorized synthetic events without an error.

`type_text` waits, for up to a second, until no modifier key is physically held. Applications read live modifier state when interpreting its events, so text typed while the triggering hotkey is still down arrives mangled or not at all. In practice a hotkey handler that types will do so the moment you let go of the combination.

## The clipboard, and opening things

```python
from macmage import get_clip, set_clip, open_url, open_app

set_clip(get_clip().upper())
open_url('https://example.com')
open_app('Ghostty')
```

`get_clip` returns the clipboard's text, or `None` when it holds none. `set_clip` replaces it, dropping every other representation, so styled text put through `set_clip(get_clip())` pastes plain. `map_clip(f)` is the pair of them: it replaces the clipboard with `f` applied to its text, and does nothing when the clipboard holds none. None of them needs a permission, which makes clipboard rewriting the cheapest kind of shortcut to write: read it, change it, put it back, and nothing else on the desktop is disturbed.

`watch_clip(fn)` calls `fn` with the clipboard's new text after every change, polling `changeCount` twice a second, and `unwatch_clip(fn)` stops it. Copies marked concealed or transient, the convention password managers use, are never reported, so a recorder built on it cannot capture passwords. `cantrips/clipboard_history.py` is the worked example: it remembers what you copy and offers the last ten through `pick` on a hotkey.

`open_url` opens a URL in whichever application handles it, custom schemes included. `open_app` takes an application's name the way `open -a` does, launches it if it is not running, and brings it to the front if it is, which covers what a launcher shortcut usually does. An unknown name raises `ValueError`.

## Telling you something

```python
from macmage import alert, notify, pick, show, web

await notify('macmage', 'clipboard cleaned')
if await alert('Delete everything?', 'This cannot be undone.', 'Delete', 'Cancel') == 0: wipe()
await show('macmage logs', log_text)
if (i := await pick('Reply with', ['thanks!', 'on it', 'ship it'])) is not None: await type_text(replies[i])
await web('https://answer.ai')
```

A background agent has nowhere to print, and macOS will not let an unbundled process speak to the user at all: Notification Center refuses a process with no bundle, and a window needs an application to own it. These helpers hand the job to Imp, which is one. `notify` posts a banner and returns at once. `alert` returns the button index once dismissed. `show` displays text monospaced, scrollable, and selectable, so long output needs neither an alert's single box nor the clipboard. `pick` shows a numbered menu, returns the chosen index, and returns `None` when dismissed; a leader keymap's actions read better through it than as blind letters. `web` shows a page or local file. Esc or the close button dismisses any of them. All five are coroutines: a wisp waits on a person, so awaiting it parks only that cantrip, and every other trigger stays live while a panel is up.

## Driving Imp

```python
from macmage import Imp, aimp

Imp(grant='microphone')
ok = Imp(check='screen,accessibility').returncode == 0
r = Imp('python', 'watch_keys.py')
r = await aimp(pick=('choose', 'a', 'b'))
```

`Imp()` builds and runs an Imp command line, and the helpers above go through it. Keyword arguments become flags, in the order given and ahead of the positional arguments: a value is passed through (`grant='microphone'`), `True` makes a bare flag (`status=True`), a list or tuple becomes one argument each (`alert=('Delete?', '', 'Delete', 'Cancel')`), and an underscore in a name becomes a hyphen. Positional arguments are the command Imp runs, with Imp's permissions. The return is the `CompletedProcess` with output captured as text, so `--check` answers in `.returncode` and `--pick` in `.stdout`; `input=` feeds stdin, which `--show` displays. When Imp is not installed it raises `ImpError`, naming the install command. `aimp` is its awaitable twin, returning the same `CompletedProcess` shape (and taking `timeout=`, default None, which kills the child): use it from cantrips for anything that waits on a person (wisps, `--grant`), where blocking the loop would freeze every other trigger.

## Contacts, calendars, photos, and audio

```python
from macmage import contact, events, add_reminder, photos, record, snap, transcribe

await contact('Rachel')               # {'name': 'Rachel ...', 'phones': [...], 'emails': [...]}
await events(days=3)                  # what the next three days hold
await add_reminder('buy milk')
await photos(5)                       # newest five: id, created, size, location
await snap('still.jpg')               # a camera still, exposure settled
await type_text(await transcribe(await record(5)))  # push-to-talk dictation
```

Each of these asks the real macOS store, so each needs its Imp grant: `contacts`, `calendars`, `reminders`, `photos`, `microphone` for `record`, `camera` for `snap`, and `speech` for `transcribe`. One `Imp --grant contacts,calendars,reminders,photos,microphone,camera,speech` covers the lot, and a missing grant raises `ImpError` naming the command. `contacts`/`contact` search by name the way the Contacts app does. `events` looks ahead, and `add_event`/`del_event` write to the default calendar; `reminders`/`add_reminder`/`del_reminder` do the same for the default list. `photos` returns metadata for the newest assets and `save_photo` exports one's original bytes. All of them are coroutines. The store fetches wrap Apple APIs that only exist in blocking form, so each runs its body on a worker thread (fastcore's `athreaded`); the capture trio is natively async, since each spends seconds against a device. `snap` takes a camera still in-process (the agent's loop delivers the capture delegate), `record` writes an m4a from the default microphone, and `transcribe` turns any audio file into text with Apple's on-device recognizer. Outside the agent, run one with `cfloop.run(record(5))`.

## Permissions
## Permissions

Hotkeys need no permission at all, because macOS delivers a registered hotkey without showing the process anything else. Everything that reads or writes the keyboard more broadly needs Accessibility: `type_text`, `press`, `watch`, and `holdmod`.

That grant belongs to Imp rather than to `macmage` or to your virtual environment, and `Imp --grant accessibility` is how to get it. macOS ties the grant to Imp's bundle identifier and signing team rather than to a hash of its binary, so it survives package upgrades, virtual environment moves, and new versions of Imp itself. Anything `macmage` does that needs a permission raises `ImpError` when it is missing, naming the command to run.

A permission applies only to processes started after it was granted, so run `macmage --install` once you have granted it. Saving `config.py` is not enough here, since that reloads the configuration without restarting the process the grant attaches to.

## Checking on it

`macmage --status` reports on everything the agent depends on, and exits non-zero if any of it is missing:

```
ok   imp: installed, with accessibility granted
ok   agent: com.answerdotai.macmage loaded, pid 41605
ok   paths: every program the plist names exists
ok   config: /Users/you/.config/macmage/config.py, with no error logged since its last edit
ok   layout: 52 keys cached at /Users/you/.cache/macmage/layout.json
```

The `paths` check catches a failure with no other symptom. The plist names an absolute path to the virtual environment's `python`, so moving or rebuilding that environment stops the agent from starting at all, silently. Re-run `macmage --install` to point it at the current one.

The agent writes stdout and stderr under `$XDG_STATE_HOME/macmage`, normally `~/.local/state/macmage`, and starts each run with a `--- <timestamp> macmage <version> started ---` marker line, so the log reads in eras:

```bash
tail -f ~/.local/state/macmage/stdout.log ~/.local/state/macmage/stderr.log
```

Saving `config.py` reloads the configuration, which is all that is needed while editing handlers. It re-executes the Python process only, leaving the Imp launcher that owns the permissions in place, so a new version of `macmage` or of Imp, and a permission granted since the agent started, all need the agent itself restarted:

```bash
macmage --install
```

## Development

```bash
pip install -e .[dev]
Imp pytest
```

The tests drive real macOS APIs rather than fakes, registering hotkeys and posting synthetic keystrokes at themselves, so run them under `Imp`. Started from a terminal they would otherwise use the terminal's permissions. `DEV.md` records the macOS behaviour the package is built around, which is worth reading before changing `keys.py`.

The package version is in `macmage/__init__.py`. Use `ship-bump` to bump it and `ship-release` to publish a release.
