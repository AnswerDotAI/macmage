# Development notes

macmage runs a user's `config.py` as a launchd agent under [Imp](https://github.com/AnswerDotAI/imp), and owns the keyboard engine: Carbon hotkeys, layout-aware combos, event taps, and synthetic input. Imp owns permission grants, code signing, and the bundle; its DEV.md records the signing and TCC-identity findings. Everything below is about the keyboard stack and the agent.

## Verified 2026-07-27 (live, on this machine)

These were verified under the pre-Imp stack (MacMage.app, pynput); the mechanisms carried over unchanged, but the rewired stack has not yet had a live install.

- The config-reload `execv` keeps pid and TCC trust; no re-prompt across reloads. `_reload_on_change` calls `stop_keys()` first, since `execv` skips atexit and a Carbon loop dying mid-run shadows layout queries system-wide.
- A config.py that raises at import logs the traceback and the process stays alive waiting for the next change; no launchd respawn loop.
- The launcher forwards SIGTERM, so `launchctl kickstart -k` cycles launcher and python child cleanly. `macmage --install` does the same through bootout plus bootstrap, and is what the README tells users to run.
- A config save re-executes the python child only; the Imp launcher, which is what TCC attributes the agent to, keeps running the binary it started with. So a new Imp build, or a permission granted since the agent started, needs the agent restarted, not touched. This bit us on 2026-07-28 with a launcher still running a binary image that had been replaced on disk.

## Gotchas

- Run in the foreground (bare `macmage`), TCC attributes to the terminal app, not Imp, so `need()` raises; run it as `Imp macmage` to match production. Tests likewise: `Imp pytest`.

## Deferred ideas

- `--status` doctor command: `launchctl print` state plus permission preflights, for when the venv path is gone and the agent cannot start at all.
## Role-model repos (shallow clones in ~/aai-ws/links)

- `KeyboardShortcuts` (sindresorhus): registers `kEventHotKeyPressed` *and* `Released`; every registration has a deliberate unregister (tests use `defer`); the test suite never posts synthetic events - lifecycle is asserted via registration conflicts (`canRegisterHotKey`: try a competing registration, expect `eventHotKeyExistsErr`).
- `hammerspoon`: the only role model that tests dispatch synthetically (`hs.eventtap.keyStroke` at its own hotkey, polling); posts with a `kCGEventSourceStatePrivate` source to the session tap, paired down/up, 1ms sleeps; documents shadowing: same-combo registrations stack, newest active wins, older resumes on disable.
- `QuickMacHotKey` (glyph): the pyobjc HIToolbox metadata this package's `_hitoolbox.py` is built from.
- `skhd.zig`: event-tap school; retries `CGEventTapCreate` at early login; synthesizes modifiers as real key events with `CGEnableEventStateCombining(false)`; synthesize is a separate CLI invocation, not in-process.

## Synthetic input fired while the trigger is still held (2026-07-28)

A hotkey handler runs while its own combination is still physically down, and that breaks synthetic input in two separate ways.

macOS merges currently-held hardware modifiers into any event we post, so `press('a')` from an Option-held hotkey arrives as Option-A. `CGEnableEventStateCombining(False)` at import turns the merging off, as skhd does, after which `press` works from inside a handler with the modifiers still down (verified by hand in ghostty: Ctrl-Alt-Cmd-1 bound to `press('a')` types `a`).

Combining does not govern unicode-payload events, which is how `type_text` works: the receiving application reads live modifier state itself when interpreting them, so text typed under a held Option is mangled or dropped. Ctrl-Alt-Cmd-2 bound to `type_text('b')` produced nothing in ghostty while the modifiers were held, though the same binding worked in Spotlight. So `type_text` polls `CGEventSourceFlagsState` for up to a second and types once no modifier is held. Typing by key code instead of unicode payload would sidestep this, but it cannot express characters absent from the layout, and the motivating handler types a zero-width space.

## Press, release, and hold (2026-07-28)

`hold=True` splits a generator handler in two: the body before its `yield` becomes the press handler and the rest becomes the release handler. The generator runs on its own thread and blocks at the `yield` on a `threading.Event` that the release handler sets, so a press body that blocks for the length of the hold (recording audio, say) cannot wedge the shared worker thread, which the plain `up=` form would, since press and release handlers both queue on it. Ordering is safe because both halves run on that one worker: the press handler appends its event before starting the thread, and the release handler pops it.

One shape to keep in mind: a `hold` thread waits on its event indefinitely, so a press whose release never arrives (the combination was unregistered mid-hold, for instance) leaves the generator suspended until the process exits.

## The keyboard stack is single-threaded: TIS/TSM (learned the hard way, 2026-07-27)

An afternoon of debugging "hotkeys register fine but never fire" ended with macOS's own words, from the crash report of a SIGABRT (`~/Library/Logs/DiagnosticReports/python*.ips`, `asi` field): "Text Input Sources or Text Services Manager API is being called in two threads concurrently... you must not call TIS/TSM API from multiple threads concurrently." The faulting stack was `RunCurrentEventLoopInMode -> _CheckEventsInited -> InitTSMFirstEventTime -> ... -> islGetInputSourceListWithAdditions -> abort`.

What this means in practice: the Carbon event loop initialises Text Services at loop entry on whatever thread runs it, and CGEvent keyboard calls (`CGEventCreateKeyboardEvent`, `CGEventKeyboardGetUnicodeString`) touch the same TIS state from the calling thread. Concurrency between them is undefined behaviour: a loud abort when the race is hit at init, and - far worse - *silently dead hotkey dispatch* when the state was initialised by the wrong thread first. That silent mode cost most of a day, because every call involved still returns success.

How each piece was established:

- Building the layout map (128 `CGEventKeyboardGetUnicodeString` round-trips) on the main thread before starting the loop thread kills dispatch for the rest of the process, deterministically. Proven with an A/B pytest pair: the hotkey test passes selected alone, fails whenever `test_parse_combo` (which builds the map) runs first in the same process - 7 runs out of 7 consistent, fresh key codes each time. The map source made no difference (`None` source, HID-state source, and the packaged `char2vk` all poisoned dispatch equally in a 3-way probe).
- The HID-system-state event source also *degrades* the map itself: 22 entries vs 52 from a `None` source.
- `RunApplicationEventLoop` is the only pump that dispatches hotkey events from a background thread: it services the application-wide queue from any thread. `RunCurrentEventLoop` on the registering (non-main) thread pumps only that thread's queue and never dispatched a hotkey, and a `CFRunLoopPerformBlock` scheduled on the loop thread's CFRunLoop is never serviced by `RunApplicationEventLoop` either. Both dead ends verified by 5-run pytest batches.
- Posting synthetic keystrokes from the main thread in the first moments after the loop thread starts hits the init race and aborts the process. Hence `_start()` sleeps 250ms after starting the loop thread.

The resulting architecture in `keys.py`: the layout map is built in a throwaway child process (`_layout_src`), so this process never translates keyboard events; the loop thread runs `RunApplicationEventLoop` and nothing else; posting happens from the caller's thread, which is safe once loop init is past. The role models agree: Hammerspoon runs its entire keyboard universe on the main thread; skhd's synthesize feature (`skhd -k`) is a *separate invocation*, never in-process with its event tap.

If this ever needs revisiting (e.g. layout-change notifications, dead keys), the proper route is `UCKeyTranslate` over layout data fetched once - but note TIS fetch calls obey the same single-thread rule.

## Layout queries are flaky system-wide; never cache a failure

`CGEventKeyboardGetUnicodeString` intermittently returns partial maps or nothing at all, in a fresh single-threaded process, correlating with adjacent keyboard-stack activity (an agent that just exited, a run seconds earlier) and with the first minute or two after login. Partial comes in more than one grade: ~22 of 52 keys with letters missing, and also (observed 2026-07-27, after `watch()` existed) letters present but punctuation missing, so "has 'a'" is not a sufficient validity check. skhd.zig documents the same family of flake for `CGEventTapCreate` at early login and retries; `char2vk` retries too (child process, up to 8 attempts, requiring letters AND >40 entries, never caching a bad map - `functools.cache` does not cache exceptions, so a failed call retries next time). The escalation fired the same day: after exhausted retries `char2vk` now falls back to a last-known-good map cached in `~/.cache/macimp/layout.json`, written on every good query. A shadow was observed lasting 15+ seconds across process boundaries, well past the ~2.4s retry budget, so the cache is what actually makes daemons at login and back-to-back test runs reliable. The known cost: a layout switch during a flake window can serve the old layout's map once.

A major aggravator was our own exits: a daemon thread running `RunApplicationEventLoop` dies mid-loop at interpreter shutdown, and for seconds afterwards layout queries system-wide return partial maps (observed as back-to-back pytest runs failing where isolated runs passed). The fix is graceful teardown: `_stop()` at `atexit` unregisters every hotkey and calls `QuitApplicationEventLoop()`. The tap thread gets the same treatment: `_stop()` disables the tap and `CFRunLoopStop`s its runloop, since a CFRunLoop thread carrying a tap dying mid-run at interpreter exit is the same pattern (shadowing resumed after `watch()` was added and back-to-back runs failed again; with teardown plus the disk cache, six consecutive suite runs pass).

## The wedge that wasn't, and the one that was (2026-07-27)

Two system-level failure modes masqueraded as code bugs all day:

- A login session's hotkey dispatch can wedge entirely: registration returns 0 but no callback ever fires, for synthetic *and physical* presses, in every new process, while listen taps still see the events and all TCC preflights pass. Logout/login cleared it. (Trigger unproven; the session had had heavy hotkey/codesign/TCC churn all morning.) Diagnosis path that finally worked: strip to a minimal raw probe, observe it fail where it had passed, then physical-press test, then a listen tap to split posting from dispatch.
- A suspected per-combo wedge ("a combo fires once, then never again") was disproven by a 2x2 factorial - fire then exit with vs without `UnregisterEventHotKey`, our flags-stamped posting vs skhd-style modifier-event posting, fresh combo and two fresh processes per cell: 8/8 fired. Fire-and-exit without unregistering is harmless; the apparent one-shot pattern was the test-order poison above plus the session wedge.

Debugging lesson paid for twice today: when identical code flips between working and broken across runs, suspect the *environment* changed under the tests (session wedge, logout, TSM state) before re-architecting the code. Re-run the golden minimal probe first; keep using fresh key codes per experiment so stale claims can't confound.

## Headless Carbon hotkey spike (verified 2026-07-27)

Question: do `RegisterEventHotKey` callbacks fire in a headless process (no app bundle, no NSApplication, spawned from a terminal)? Test: pyobjc HIToolbox bridge cribbed from glyph's quickmachotkey (MIT), one handler printing on `kEventHotKeyPressed`, three event-loop variants, combo Ctrl-Opt-Cmd-T pressed by hand.

- Registration always succeeds headless: `InstallEventHandler` and `RegisterEventHotKey` both return 0 with no bundle, no NSApp, and no TCC grant of any kind.
- Bare `CFRunLoopRun()`: callback never fires. The Carbon event queue needs its own dispatcher; a plain CFRunLoop does not drain it.
- `RunApplicationEventLoop()` (HIToolbox, bound via `loadBundleFunctions`, signature `b"v"`): callback fires. No NSApplication involved.
- So the hotkey engine needs neither Cocoa nor any permission for detection; only synthetic typing needs an Accessibility grant.

Spike artifacts are in `meta/`: `spike2.py` (the harness), `hitoolbox.py` (the bridge), and quickmachotkey's `_metadata.py`, which is the seed for this package's HIToolbox bridge, with attribution owed. Hammerspoon's `libhotkey.m`, `libeventtap.m`, and `libkeycodes.m` are worth re-reading during the build; fetch them with ghapi rather than vendoring.

## Second spike, both questions yes (verified 2026-07-27)

- Synthetic events fire registered hotkeys: a `CGEventPost` of the combo at `kCGHIDEventTap` triggers the Carbon handler. So the library can test itself end to end, with no human keypress.
- `RunApplicationEventLoop` dispatches from a background thread. macimp can own a singleton loop thread started lazily on first registration, which makes `hotkey()` work in notebooks and kernels, not only in daemons.
- Handlers run on the loop thread, so a slow handler delays every later hotkey. Dispatch user callbacks to a worker by default.

Open questions for the build session:

- Do CGEventTap runloop sources (`watch()`) fire while `RunApplicationEventLoop` is running? Answered 2026-07-27: not tried on the Carbon loop thread; instead `watch()` runs its tap on its own thread with its own CFRunLoop (taps are CG, not TSM, so the single-thread rule doesn't apply), and the two coexist fine - `test_watch_sees_keystrokes` shows a listen tap reporting a keystroke that our own hotkey claims, suppresses, and handles in the same process.
- Combo suppression appeared total even in the bare-`CFRunLoopRun` variant where nothing drained the queue (registration alone claims the key). Answered 2026-07-28 for the rest: releases arrive as `kEventHotKeyReleased` for synthetic presses as well as physical ones, and a held key repeats nothing, so repeats would need our own timer as in Hammerspoon.
- `UCKeyTranslate` scan of vks 0-127 against the current layout, for `'cmd-alt-`'`-style binding by character. Sharp edges from `libkeycodes.m`: `kUCKeyTranslateNoDeadKeysMask`, and TIS calls can return NULL.

