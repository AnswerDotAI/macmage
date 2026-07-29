from fastcore.utils import *
from fastcore.xdg import *
from fastcore.script import call_parse
import asyncio, importlib, inspect, json, plistlib, re, select, threading, time, traceback
from .util import *
from .app import *
from .clip import *
from .keys import *
from .keys import _layout_cache, _quit_loop
from .ui import *
from .pim import *
from .media import *
from .imp import ImpError, agent, agent_state, Imp, aimp, imp_check, install_msg, launcher, unagent, as_imp, need

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
    keys:str|list=None, # Combo(s), e.g. 'alt-`' or 'ctrl-alt-cmd-t', to bind the handler to
    hold:bool=False # Take `f` as an async generator: the body before `yield` runs on press and the rest on release
):
    "Wrap a handler so exceptions are logged instead of propagating; with `keys`, also register it as a global hotkey"
    if f is None: return partial(mage, keys=keys, hold=hold)
    # a wrapper is a generator (or async) function only by its own body's syntax, so the cases cannot share one body
    if hold:
        if not inspect.isasyncgenfunction(f):
            raise ValueError(f'A `hold` handler needs `async def` with a `yield`: {f.__name__} is not an async generator function')
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            try:
                async for x in f(*args, **kwargs): yield x
            except Exception as e: _log_exc(e, f.__name__)
    elif inspect.iscoroutinefunction(f):
        @functools.wraps(f)
        async def _f(*args, **kwargs):
            try: return await f(*args, **kwargs)
            except Exception as e: _log_exc(e, f.__name__)
    else:
        @functools.wraps(f)
        def _f(*args, **kwargs):
            try: return f(*args, **kwargs)
            except Exception as e: _log_exc(e, f.__name__)
    for o in L(keys): hotkey(o, _f, hold=hold)
    return _f


def _watch_config(loop):
    "Reload on any config change: kqueue vnode events surface through the loop's own selector"
    kq = select.kqueue()
    fds = [os.open(p, os.O_EVTONLY) for p in (config_dir, *config_dir.glob('*.py'))]
    flags = select.KQ_NOTE_WRITE | select.KQ_NOTE_ATTRIB | select.KQ_NOTE_RENAME | select.KQ_NOTE_DELETE
    events = [select.kevent(o, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT, fflags=flags) for o in fds]
    kq.control(events, 0)
    loop.add_reader(kq.fileno(), _quit_loop)  # `run` reloads on the main thread once its loop exits


def _load_config():
    loop = asyncio.get_running_loop()
    _watch_config(loop)
    sys.path.insert(0, str(config_dir))
    try: importlib.import_module('config')
    except Exception as e:
        _log_exc(e, 'config')
        # The panel is the answer to "did my save load?", as a task so the loop still runs and the
        # watcher's reload still works. The log already has the traceback, so a display failure
        # (e.g. Imp missing) must not take down the process that waits for the fix.
        async def _show():
            try: await show(f'macmage: config.py failed to load at {time.strftime("%T")}', ''.join(traceback.format_exception(e)))
            except Exception: pass
        loop.create_task(_show())


def run():
    print(f'--- {time.strftime("%F %T")} macmage {__version__} started, watching {config_dir} ---', file=sys.stderr, flush=True)
    threading.excepthook = lambda a: _log_exc(a.exc_value, f'thread {a.thread.name}')
    sys.excepthook = lambda t,v,tb: _log_exc(v, 'main thread')
    config_dir.mkdir(parents=True, exist_ok=True)
    run_loop(_load_config)  # config registrations deliver via the main-thread loop (see DEV.md)
    stop_keys()  # execv skips atexit, and a Carbon loop dying mid-run shadows layout queries system-wide (see DEV.md)
    os.execv(run_args[0], run_args)

def _st_imp():
    "Whether Imp is installed and granted what the agent needs, asked of Imp so a terminal's own grants cannot answer"
    if not launcher.exists(): return False, f'Imp is not installed: {install_msg}'
    if not imp_check('accessibility'): return False, 'Imp lacks accessibility: run Imp --grant accessibility'
    return True, 'installed, with accessibility granted'


def _st_agent():
    "Whether launchd has the agent loaded"
    p, loaded, txt = agent_state(label)
    if not p.exists(): return False, f'no plist at {p}: run macmage --install'
    if not loaded: return False, f'{label} is not loaded: run macmage --install'
    pid = re.search(r'pid = (\d+)', txt)
    return True, f'{label} loaded' + (f', pid {pid[1]}' if pid else '')


def _st_paths():
    "Whether the programs the plist names still exist, which a moved virtual environment breaks silently"
    p, *_ = agent_state(label)
    if not p.exists(): return False, 'no plist to read'
    args = plistlib.loads(p.read_bytes())['ProgramArguments']
    gone = [o for o in args if o.startswith('/') and not Path(o).exists()]
    if gone: return False, f'the plist names missing programs ({", ".join(gone)}): run macmage --install'
    return True, 'every program the plist names exists'


def _st_config():
    "Whether config.py exists, and whether it has raised since it was last edited"
    cfg, log = config_dir/'config.py', state_dir/'stderr.log'
    if not cfg.exists(): return False, f'no {cfg}'
    errs = [o for o in log.read_text().splitlines() if 'unhandled exception in config' in o] if log.exists() else []
    if errs and time.mktime(time.strptime(errs[-1][:19], '%Y-%m-%d %H:%M:%S')) > cfg.stat().st_mtime:
        return False, f'config.py raised at {errs[-1][:19]}, since its last edit: see {log}'
    return True, f'{cfg}, with no error logged since its last edit'


def _st_layout():
    "Whether a keyboard layout map is cached, since querying one can fail for seconds at a time"
    if not _layout_cache.exists(): return False, f'nothing cached at {_layout_cache}: run macmage --install'
    n = len(json.loads(_layout_cache.read_text()))
    return n>40, f'{n} keys cached at {_layout_cache}'


def _status():
    "Report on everything the agent needs, exiting 1 if any of it is missing"
    res = dict(imp=_st_imp(), agent=_st_agent(), paths=_st_paths(), config=_st_config(), layout=_st_layout())
    for k,(ok,msg) in res.items(): print(f'{"ok  " if ok else "FAIL"} {k}: {msg}')
    sys.exit(0 if all(ok for ok,_ in res.values()) else 1)




def _install():
    for o in (config_dir, state_dir): o.mkdir(parents=True, exist_ok=True)
    char2vk()  # seed the layout cache: the agent's first query can hit a system-wide flake window lasting longer than its retry budget, with nothing yet to fall back on
    env = dict(XDG_CONFIG_HOME=config_home, XDG_STATE_HOME=state_home)
    p = agent(label, run_args, workdir=config_dir, env=env, stdout=state_dir/'stdout.log', stderr=state_dir/'stderr.log')
    print(f'Installed {p}')


def _uninstall():
    unagent(label)
    print(f'Uninstalled {label}. Imp.app and its permission grants are shared, so they stay.')


@call_parse
def main(
    install:bool=False, # Install and start the LaunchAgent
    uninstall:bool=False, # Stop the LaunchAgent and remove its plist
    status:bool=False # Report on the agent, its permissions, and its configuration
):
    "Run MacMage or manage its LaunchAgent"
    (_install if install else _uninstall if uninstall else _status if status else run)()
