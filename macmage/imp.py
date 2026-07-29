"Running under Imp.app, the signed bundle macOS attaches permission grants to"

from fastcore.utils import *
import ctypes, plistlib, subprocess
from .util import wait_until

__all__ = ['ImpError', 'app_path', 'launcher', 'install_msg', 'Imp', 'as_imp', 'need', 'imp_check', 'agent_state', 'agent', 'unagent']

app_path = Path.home()/'Applications/Imp.app'
launcher = app_path/'Contents/MacOS/Imp'
install_msg = 'curl -fsSL https://raw.githubusercontent.com/AnswerDotAI/imp/main/install.sh | sh'

_libc = ctypes.CDLL(None)
_libc.responsibility_get_pid_responsible_for_pid.argtypes = [ctypes.c_int]
_libc.responsibility_get_pid_responsible_for_pid.restype = ctypes.c_int


class ImpError(RuntimeError): pass


def _argv(*args, **flags):
    res = [str(launcher)]
    for k,v in flags.items():
        res.append(f'--{k.replace("_","-")}')
        if v is not True: res += [str(o) for o in v] if isinstance(v, (list,tuple)) else [str(v)]
    return res + [str(o) for o in args]


def Imp(
    *args, # The command for Imp to run, after any flags
    input:str=None, # Text to feed to stdin, which `--show` displays
    **flags # Imp flags, ahead of `args`: a value passes through, `True` makes a bare flag, a list or tuple becomes one argument each, and underscores become hyphens
):
    "Run Imp with `flags` and `args`, returning the `CompletedProcess` with text output captured"
    if not launcher.exists(): raise ImpError(f'Imp is not installed: {install_msg}')
    return subprocess.run(_argv(*args, **flags), capture_output=True, text=True, input=input)



def _exe(pid):
    buf = ctypes.create_string_buffer(4096)
    return buf.value.decode() if _libc.proc_pidpath(pid, buf, 4096) > 0 else ''


def as_imp():
    "Whether macOS attributes this process to Imp, which is what decides whose permissions apply"
    rpid = _libc.responsibility_get_pid_responsible_for_pid(os.getpid())
    return _exe(rpid) == str(launcher.resolve())


_ok = set()


def need(
    *names:str # Permission names, as `Imp --grant` takes them
):
    "Raise unless this process runs under Imp with `names` granted; a granted permission only reaches a fresh process, so each is checked once"
    todo = [o for o in names if o not in _ok]
    if not todo: return
    if not as_imp(): raise ImpError(
        f'macmage needs {", ".join(todo)}, which only applies to processes run under Imp.\n'
        f'Run it as: {launcher} {sys.executable} ...\n'
        f'For the agent: macmage --install' + ('' if launcher.exists() else f'\nImp is not installed: {install_msg}'))
    missing = [o for o in todo if Imp(check=o).returncode != 0]
    if missing: raise ImpError(
        f'Imp has not been granted {", ".join(missing)}.\n'
        f'Run: Imp --grant {",".join(missing)}\n'
        'Then restart this process (for the agent: touch its config.py)')
    _ok.update(todo)


def _domain(): return f'gui/{os.getuid()}'
def _plist(label): return Path.home()/f'Library/LaunchAgents/{label}.plist'


def imp_check(
    *names:str # Permission names, as `Imp --grant` takes them
):
    "Whether Imp has been granted `names`, asked of Imp itself, so the answer holds wherever this runs"
    if not launcher.exists(): return False
    return Imp(check=','.join(names)).returncode==0


def agent_state(
    label:str # launchd label, e.g. `com.answerdotai.macmage`
):
    "What launchd knows about `label`: its plist path, whether it is loaded, and `launchctl print`'s report"
    r = subprocess.run(['launchctl', 'print', f'{_domain()}/{label}'], capture_output=True, text=True)
    return _plist(label), r.returncode==0, r.stdout


def unagent(
    label:str # launchd label, e.g. `com.answerdotai.macmage`
):
    "Stop the agent named `label` and remove its plist"
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    gone = lambda: subprocess.run(['launchctl', 'print', f'{_domain()}/{label}'], **quiet).returncode
    subprocess.run(['launchctl', 'bootout', f'{_domain()}/{label}'], **quiet)
    wait_until(gone, 5)
    _plist(label).unlink(missing_ok=True)


def agent(
    label:str, # launchd label, also the plist filename
    args:list, # Command to run under Imp, e.g. `[python, '-u', script]`
    workdir=None, # Working directory for the agent
    env:dict=None, # Environment variables
    stdout=None, # Path to write standard output to
    stderr=None, # Path to write standard error to
    keepalive:bool=True # Restart the agent when it exits?
):
    "Write and start a launchd agent running `args` under Imp, so it inherits Imp's permissions"
    if not launcher.exists(): raise ImpError(f'Imp is not installed: {install_msg}')
    d = dict(Label=label, ProgramArguments=[str(launcher)]+[str(o) for o in args], RunAtLoad=True, KeepAlive=keepalive)
    if workdir: d['WorkingDirectory'] = str(workdir)
    if env: d['EnvironmentVariables'] = {k:str(v) for k,v in env.items()}
    if stdout: d['StandardOutPath'] = str(stdout)
    if stderr: d['StandardErrorPath'] = str(stderr)
    p = _plist(label)
    p.parent.mkdir(parents=True, exist_ok=True)
    unagent(label)
    p.write_bytes(plistlib.dumps(d))
    subprocess.run(['launchctl', 'bootstrap', _domain(), str(p)], check=True)
    return p
