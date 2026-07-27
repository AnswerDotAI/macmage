# macmage

`macmage` runs `$XDG_CONFIG_HOME/macmage/config.py` as ordinary Python in a background macOS LaunchAgent. `XDG_CONFIG_HOME` defaults to `~/.config`. The configuration can use any package installed in the same virtual environment.

## Install

Install `macmage` in an activated virtual environment, then register its LaunchAgent:

```bash
pip install macmage
macmage --install
```

`macmage --install` writes `~/Library/LaunchAgents/com.answerdotai.macmage.plist`, which runs the current virtual environment's `python` under `Imp.app`, the signed launcher bundle from the `macimp` package (built on first install; compiling it uses the Xcode Command Line Tools, which macOS offers to install if missing). Running `--install` again replaces the LaunchAgent definition. It does not create or modify `config.py`.

`macmage --uninstall` stops the agent and removes its plist. It leaves the configuration, logs, `Imp.app`, and its permission grants untouched.

## Configure

Create `$XDG_CONFIG_HOME/macmage/config.py`, normally `~/.config/macmage/config.py`. This example binds Alt-` to type a backtick, a zero-width space, and two more backticks:

```python
from macimp import type_text
from macmage import mage

@mage(keys='alt-`')
def backticks(): type_text('`​``')
```

`@mage` wraps a handler so an exception is logged instead of stopping the process; `keys` also binds the handler to one or more global hotkeys through `macimp`. Combos name keys as typed on the current layout (`'alt-`'`, `'ctrl-shift-space'`, `'cmd-alt-t'`), and `'alt-<50>'` names a raw key code directly. The bound keystroke is suppressed system-wide, so it does not reach the frontmost app. `config.py` need not block: macmage keeps the process alive, and restarts it when any `.py` file in the configuration directory changes (a bare `touch` suffices). An error while loading `config.py` is logged, and the process waits for the next change to reload. The configuration can import sibling files from its directory through normal Python imports.

Run `macmage` without arguments to use the same configuration in the foreground.

## Permissions

Hotkeys need no permission at all. Synthetic typing (`macimp.type_text` and `macimp.press`) needs Accessibility, granted once to `Imp.app`, the signed launcher every macimp-based agent runs under. macimp checks at each call and logs anything missing to `stderr.log`, and because `Imp.app` is signed with a stable identity, the grant survives package upgrades and virtual environment moves. For other permissions your automation needs, call `require` at the top of `config.py`:

```python
from macimp import require
require('input_monitoring')
```

## Logs

The LaunchAgent writes stdout and stderr under `$XDG_STATE_HOME/macmage`, normally `~/.local/state/macmage`:

```bash
tail -f ~/.local/state/macmage/stdout.log ~/.local/state/macmage/stderr.log
```

Restart the installed agent with:

```bash
launchctl kickstart -k gui/$(id -u)/com.answerdotai.macmage
```

## Development

```bash
pip install -e .[dev]
```

The package version lives in `macmage/__init__.py`. Use `ship-bump` to bump it and `ship-release` to publish a release.
