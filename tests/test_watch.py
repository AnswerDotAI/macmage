"A saved configuration wakes the agent after config loading has returned and its local objects have been collected."
import os, subprocess, sys


def test_config_reload(tmp_path):
    config = tmp_path/'macmage'
    config.mkdir()
    (config/'config.py').write_text('''import asyncio, gc
from pathlib import Path

def edit():
    gc.collect()
    Path(__file__).write_text('# saved configuration\\n')

asyncio.get_running_loop().call_soon(edit)
''')
    r = subprocess.run([sys.executable, '-c', 'from macmage import _load_config, run_loop; run_loop(_load_config)'],
        env=dict(os.environ, XDG_CONFIG_HOME=str(tmp_path)), capture_output=True, text=True, timeout=5)
    assert r.returncode == 0, r.stdout+r.stderr
