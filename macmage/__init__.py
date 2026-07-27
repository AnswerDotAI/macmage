from fastcore.utils import *
from fastcore.xdg import *
from fastcore.script import call_parse
import importlib, select, threading, time, traceback
from macimp import hotkey, stop_keys
from macimp.app import agent, unagent

__version__ = "0.1.0"

name = 'macmage'
label = f'com.answerdotai.{name}'
config_home, state_home = xdg_config_home(), xdg_state_home()
config_dir, state_dir = config_home/name, state_home/name
run_args = [str(Path(sys.executable).with_name('python')), '-u', str(Path(sys.executable).with_name(name))]


def _log_exc(e, ctx):
    print(f'{time.strftime("%F %T")} macmage: unhandled exception in {ctx}', file=sys.stderr, flush=True)
    traceback.print_exception(e)


def mage(
    f=None, # Handler to wrap; None when used as `@mage(keys=...)`
    *,
    keys:str|list=None # macimp combo(s), e.g. 'alt-<50>' or 'ctrl-alt-cmd-t', to bind the handler to
):
    "Wrap a handler so exceptions are logged instead of propagating; with `keys`, also register it as a global hotkey"
    if f is None: return partial(mage, keys=keys)
    @functools.wraps(f)
    def _f(*args, **kwargs):
        try: return f(*args, **kwargs)
        except Exception as e: _log_exc(e, f.__name__)
    for o in L(keys): hotkey(o, _f)
    return _f


def _reload_on_change(path):
    fds = [os.open(p, os.O_EVTONLY) for p in (path, *path.glob('*.py'))]
    flags = select.KQ_NOTE_WRITE | select.KQ_NOTE_ATTRIB | select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE
    events = [select.kevent(o, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT, fflags=flags) for o in fds]
    select.kqueue().control(events, 1)
    stop_keys()  # execv skips atexit, and a Carbon loop dying mid-run shadows layout queries system-wide (macimp DEV.md)
    os.execv(run_args[0], run_args)


def run():
    threading.excepthook = lambda a: _log_exc(a.exc_value, f'thread {a.thread.name}')
    sys.excepthook = lambda t,v,tb: _log_exc(v, 'main thread')
    config_dir.mkdir(parents=True, exist_ok=True)
    watcher = threading.Thread(target=_reload_on_change, args=(config_dir,), daemon=True)
    watcher.start()
    sys.path.insert(0, str(config_dir))
    try: importlib.import_module('config')
    except Exception as e: _log_exc(e, 'config')
    watcher.join()


def _install():
    for o in (config_dir, state_dir): o.mkdir(parents=True, exist_ok=True)
    env = dict(XDG_CONFIG_HOME=config_home, XDG_STATE_HOME=state_home)
    p = agent(label, run_args, workdir=config_dir, env=env, stdout=state_dir/'stdout.log', stderr=state_dir/'stderr.log')
    print(f'Installed {p}')


def _uninstall():
    unagent(label)
    print(f'Uninstalled {label}. Imp.app and its permission grants are shared, so they stay.')


@call_parse
def main(
    install:bool=False, # Install and start the LaunchAgent
    uninstall:bool=False # Stop the LaunchAgent and remove its plist
):
    "Run MacMage or manage its LaunchAgent"
    (_install if install else _uninstall if uninstall else run)()
