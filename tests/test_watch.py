"Loading and watching agent configuration."
import asyncio, gc, os

import cfloop

import macmage


def test_config_loads_dotenv_without_overriding_environment(tmp_path, monkeypatch):
    "The agent's environment file is loaded before config, while inherited values win"
    (tmp_path/'.env').write_text('FROM_DOTENV=loaded\nALREADY_SET=from-file\n')
    monkeypatch.setattr(macmage, 'config_dir', tmp_path)
    monkeypatch.setattr(macmage, '_watch_config', lambda loop: None)
    monkeypatch.setenv('ALREADY_SET', 'inherited')
    monkeypatch.delenv('FROM_DOTENV', raising=False)
    seen = []
    def import_config(name): seen.append((os.environ['FROM_DOTENV'], os.environ['ALREADY_SET']))
    monkeypatch.setattr(macmage.importlib, 'import_module', import_config)
    async def main(): macmage._load_config()
    asyncio.run(main())
    assert seen == [('loaded', 'inherited')]


def test_watch_config_fires_after_return(tmp_path, monkeypatch):
    "A config write wakes the loop after `_watch_config` returns, so its kqueue must remain referenced"
    (tmp_path/'config.py').write_text('x = 1\n')
    monkeypatch.setattr(macmage, 'config_dir', tmp_path)
    fired = []
    monkeypatch.setattr(macmage, '_quit_loop', lambda: fired.append(True))
    async def main():
        macmage._watch_config(asyncio.get_running_loop())
        gc.collect()  # a locally-held kqueue dies here, taking its fd with it
        (tmp_path/'config.py').write_text('x = 2\n')
        for _ in range(50):
            if fired: break
            await asyncio.sleep(0.02)
    cfloop.run(main())
    assert fired, 'the watcher never woke the loop for a config write'
