"""The config watcher: a change to a watched file must wake the loop after `_watch_config`
returns - which is exactly when a locally-held kqueue would be garbage-collected and its
fd silently closed (the bug that shipped: the agent never reloaded on config saves)."""
import asyncio, gc

import cfloop

import macmage


def test_watch_config_fires_after_return(tmp_path, monkeypatch):
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
