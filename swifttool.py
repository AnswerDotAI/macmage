"Swift build, bundle, and code-signing helpers, so macOS app work happens in the kernel instead of one-off shell calls."

from fastcore.utils import *
import re, plistlib, shutil

__all__ = ['swift_version', 'signing_ids', 'swift_build', 'mk_app', 'sign', 'verify_sig', 'codesign_req', 'zip_app',
    'unzip_app', 'build_app']


def build_app(
    path, # Swift package directory
    bundle_id:str, # CFBundleIdentifier, which TCC grants attach to
    identity:str=None, # Signing identity; the sole Developer ID one if None
    hardened:bool=True, # Enable the hardened runtime, which requires an entitlement per protected resource
    **plist # Extra Info.plist entries
):
    "Build, sign, and archive a Swift package, always as `build/<Name>.app` and `dist/<Name>.app.zip`, so the two cannot drift from the source or each other"
    path = Path(path).expanduser()
    exe = swift_build(path)
    app = mk_app(exe, path/f'build/{exe.name}.app', bundle_id, **plist)
    sign(app, identity, hardened)
    return app, zip_app(app, path/f'dist/{exe.name}.app.zip')


def verify_sig(
    path # Bundle or binary to check
):
    "Whether `path`'s signature is intact, checked strictly"
    return run('codesign', '--verify', '--strict', path, ignore_ex=True)[0] == 0


def zip_app(
    app, # `.app` bundle to archive
    dest # Zip file to write
):
    "Archive `app` with `ditto`, the only archiver that keeps a bundle's signature intact"
    app,dest = Path(app),Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    run('ditto', '-c', '-k', '--keepParent', app, dest)
    return dest


def unzip_app(
    src, # Zip file made by `zip_app`
    dest # Directory to extract into
):
    "Extract a `zip_app` archive, preserving the signature"
    run('ditto', '-x', '-k', src, dest)
    return Path(dest)/Path(src).name.replace('.zip','')


def mk_app(
    exe, # Built executable to install as the bundle's binary
    dest, # Path of the `.app` to create, replacing any existing one
    bundle_id:str, # CFBundleIdentifier, which TCC grants attach to
    **plist # Extra Info.plist entries
):
    "Assemble a minimal macOS app bundle around `exe`"
    exe,dest = Path(exe),Path(dest)
    if dest.exists(): shutil.rmtree(dest)
    macos = dest/'Contents/MacOS'
    macos.mkdir(parents=True)
    shutil.copy2(exe, macos/exe.name)
    info = dict(CFBundleIdentifier=bundle_id, CFBundleExecutable=exe.name, CFBundleName=exe.name,
        CFBundlePackageType='APPL', LSUIElement=True, **plist)  # LSUIElement, not LSBackgroundOnly: no Dock icon, but a window can still come to the front
    (dest/'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    return dest


def sign(
    path, # Bundle or binary to sign
    identity:str=None, # Signing identity; the sole Developer ID one if None
    hardened:bool=True # Enable the hardened runtime, which requires an entitlement per protected resource
):
    "Code-sign `path`, replacing any existing signature"
    if identity is None: identity = first(o for o in signing_ids() if o.startswith('Developer ID'))
    opts = ['--options', 'runtime'] if hardened else []
    run('codesign', '--force', '--sign', identity, *opts, path)
    return identity


def codesign_req(
    path # Bundle or binary to inspect
):
    "The designated requirement `path`'s signature is keyed to, which is what TCC grants match against"
    return run('codesign', '-d', '-r-', path)


def swift_build(
    path, # Package directory
    config:str='release' # Build configuration
):
    "Build the Swift package at `path`, returning the built executable"
    path = Path(path)
    run('swift', 'build', '--package-path', path, '-c', config)
    bindir = run('swift', 'build', '--package-path', path, '-c', config, '--show-bin-path')
    exe = [o for o in Path(bindir).ls() if o.is_file() and os.access(o, os.X_OK)]
    return exe[0]


def swift_version():
    "The active Swift toolchain's version banner"
    return run('swift --version')


def signing_ids():
    "Code-signing identities in the keychain, as `{name: sha1}`"
    out = run('security', 'find-identity', '-v', '-p', 'codesigning')
    return {nm:h for h,nm in re.findall(r'\)\s+(\w+)\s+"([^"]+)"', out)}
