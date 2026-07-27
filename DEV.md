# Development notes

macmage is a thin supervisor over `macimp`, which owns the keyboard engine, hotkey combos, Imp.app, code signing, and permissions. The macOS behaviour records (TSM threading, layout flakes, signing rules, TCC gotchas, prompt-UX deferral) live in macimp's DEV.md; notes here are macmage-specific.

## Verified 2026-07-27 (live, on this machine)

These were verified under the pre-macimp stack (MacMage.app, pynput); the mechanisms carried over unchanged, but the rewired stack has not yet had a live install.

- The config-reload `execv` keeps pid and TCC trust; no re-prompt across reloads. `_reload_on_change` calls `macimp.stop_keys()` first, since `execv` skips atexit and a Carbon loop dying mid-run shadows layout queries system-wide.
- A config.py that raises at import logs the traceback and the process stays alive waiting for the next change; no launchd respawn loop.
- The launcher forwards SIGTERM, so `launchctl kickstart -k` cycles launcher and python child cleanly.

## Gotchas

- Run in the foreground (bare `macmage`), TCC attributes to the terminal app, not Imp; permission behavior only matches production under the LaunchAgent.

## Deferred ideas

- `--status` doctor command: `launchctl print` state plus permission preflights, for when the venv path is gone and the agent cannot start at all.
