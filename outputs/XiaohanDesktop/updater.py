"""Portable Windows updates from GitHub Releases. The data folder is never read or replaced.

Flow: fetch latest.json -> download the zip and check its size and SHA-256 -> extract into
<install>/.update/<version> -> the new build's exe waits for the old process to exit, moves
the old program files to .update/previous, copies the new ones in and starts the pet again.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import zipfile

from version import VERSION, RELEASE_REPO

MANIFEST_URL = f'https://github.com/{RELEASE_REPO}/releases/latest/download/latest.json'
PACKAGE_ROOT = '小汉'
EXE_NAME = '小汉.exe'
UPDATE_DIR = '.update'
# Never replaced: the player's save and the updater's own working folder.
KEEP = frozenset({'data', UPDATE_DIR})
MANIFEST_LIMIT = 64 * 1024
MAX_PACKAGE_BYTES = 200 * 2**20
MAX_EXTRACTED_BYTES = 600 * 2**20
NETWORK_TIMEOUT = 20
CHUNK = 256 * 1024
# Antivirus scanners often hold files briefly right after the old process exits.
MOVE_ATTEMPTS = 10
MOVE_RETRY_SECONDS = .3
EXIT_WAIT_SECONDS = 60


class UpdateError(Exception):
    pass


def parse_version(text):
    if not isinstance(text, str) or not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}', text):
        raise UpdateError('版本号格式不对')
    return tuple(int(part) for part in text.split('.'))


def is_newer(version, current=VERSION):
    return parse_version(version) > parse_version(current)


def _check_url(url, schemes):
    if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme not in schemes:
        raise UpdateError('更新地址不安全')


def validate_manifest(data, allow_file=False):
    schemes = {'https', 'file'} if allow_file else {'https'}
    if not isinstance(data, dict):
        raise UpdateError('更新信息格式不对')
    parse_version(data.get('version'))
    if not isinstance(data.get('notes', ''), str):
        raise UpdateError('更新说明格式不对')
    if 'page' in data:
        _check_url(data['page'], schemes)
    package = data.get('windows')
    if not isinstance(package, dict):
        raise UpdateError('更新信息缺少 Windows 安装包')
    urls = package.get('urls')
    if not isinstance(urls, list) or not urls:
        raise UpdateError('更新信息缺少下载地址')
    for url in urls:
        _check_url(url, schemes)
    if not isinstance(package.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', package['sha256']):
        raise UpdateError('更新信息缺少校验值')
    size = package.get('bytes')
    if type(size) is not int or not 0 < size <= MAX_PACKAGE_BYTES:
        raise UpdateError('安装包大小不对')
    return data


def fetch_manifest(url=MANIFEST_URL, allow_file=False):
    _check_url(url, {'https', 'file'} if allow_file else {'https'})
    try:
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
            body = response.read(MANIFEST_LIMIT + 1)
    except OSError as exc:
        raise UpdateError(f'连不上更新服务器：{exc}') from exc
    if len(body) > MANIFEST_LIMIT:
        raise UpdateError('更新信息过大')
    try:
        data = json.loads(body.decode('utf-8'))
    except ValueError as exc:
        raise UpdateError('更新信息格式不对') from exc
    return validate_manifest(data, allow_file)


def download(package, target, progress=lambda fraction: None):
    """Try each URL in order; a file only counts when its size and SHA-256 both match."""
    total = package['bytes']
    failures = []
    for url in package['urls']:
        digest = hashlib.sha256()
        received = 0
        try:
            with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response, open(target, 'wb') as out:
                while chunk := response.read(CHUNK):
                    received += len(chunk)
                    if received > total:
                        raise UpdateError('下载大小和更新信息不一致')
                    digest.update(chunk)
                    out.write(chunk)
                    progress(received / total)
            if received != total or digest.hexdigest() != package['sha256']:
                raise UpdateError('下载的安装包校验不通过')
            return target
        except (OSError, UpdateError) as exc:
            failures.append(str(exc))
    raise UpdateError('下载失败：' + '；'.join(failures))


def extract(archive, destination):
    """Unpack a release zip whose entries all sit under 小汉/ and never touch data/."""
    try:
        with zipfile.ZipFile(archive) as bundle:
            total = 0
            for info in bundle.infolist():
                name = info.filename
                parts = PurePosixPath(name).parts
                # zipfile already turns backslashes into '/' when reading entry names.
                if (':' in name or name.startswith('/') or '..' in parts
                        or not parts or parts[0] != PACKAGE_ROOT):
                    raise UpdateError('安装包里有不安全的路径')
                if len(parts) > 1 and parts[1] in KEEP:
                    raise UpdateError('安装包不能包含存档或更新目录')
                total += info.file_size
            if total > MAX_EXTRACTED_BYTES:
                raise UpdateError('安装包解压后过大')
            bundle.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise UpdateError('安装包已损坏') from exc
    root = Path(destination) / PACKAGE_ROOT
    if not (root / EXE_NAME).is_file() or not (root / '_internal').is_dir():
        raise UpdateError('安装包缺少程序文件')
    return root


def prepare(install_dir, manifest, progress=lambda fraction: None):
    """Download and unpack the new build next to the installation; returns the staged root."""
    work = Path(install_dir) / UPDATE_DIR / manifest['version']
    if work.exists():
        remove_tree(work)
    work.mkdir(parents=True)
    archive = download(manifest['windows'], work / 'package.zip', progress)
    root = extract(archive, work)
    archive.unlink()
    return root


def remove_tree(path):
    def clear_read_only(function, target, _):
        os.chmod(target, stat.S_IREAD | stat.S_IWRITE)
        function(target)
    shutil.rmtree(path, onerror=clear_read_only)


def cleanup(install_dir):
    """Remove the previous update's staging and backup once the new version has started."""
    work = Path(install_dir) / UPDATE_DIR
    if work.exists():
        try:
            remove_tree(work)
        except OSError:
            pass  # The finished installer may still be exiting; the next start retries.


def _move(source, target):
    for attempt in range(MOVE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == MOVE_ATTEMPTS - 1:
                raise
            time.sleep(MOVE_RETRY_SECONDS)


def apply_update(staged_root, install_dir):
    """Swap program files; on failure put the old files back. data/ is never touched."""
    staged_root, install_dir = Path(staged_root), Path(install_dir)
    backup = install_dir / UPDATE_DIR / 'previous'
    if backup.exists():
        remove_tree(backup)
    backup.mkdir(parents=True)
    names = sorted(path.name for path in staged_root.iterdir() if path.name not in KEEP)
    moved, copied = [], []
    try:
        for name in names:
            if (install_dir / name).exists():
                _move(install_dir / name, backup / name)
                moved.append(name)
        for name in names:
            copied.append(name)
            source, target = staged_root / name, install_dir / name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    except OSError as exc:
        try:
            for name in copied:
                target = install_dir / name
                if target.is_dir():
                    remove_tree(target)
                elif target.exists():
                    target.unlink()
            for name in moved:
                _move(backup / name, install_dir / name)
        except OSError as restore_error:
            raise UpdateError(f'更新失败：{exc}\n恢复旧版也失败：{restore_error}\n旧版文件在 {backup}') from exc
        raise UpdateError(f'更新失败，已恢复原来的版本：{exc}') from exc


def wait_for_exit(pid, timeout=EXIT_WAIT_SECONDS):
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    synchronize = 0x00100000
    handle = kernel.OpenProcess(synchronize, False, pid)
    if not handle:
        return  # Already exited.
    try:
        if kernel.WaitForSingleObject(handle, int(timeout * 1000)) != 0:
            raise UpdateError('旧版小汉没有退出，更新已取消')
    finally:
        kernel.CloseHandle(handle)


def launch_installer(staged_root, install_dir, pid):
    subprocess.Popen([str(Path(staged_root) / EXE_NAME), '--apply-update', str(install_dir), '--wait-pid', str(pid)],
                     cwd=str(staged_root), close_fds=True)


def launch(install_dir):
    subprocess.Popen([str(Path(install_dir) / EXE_NAME)], cwd=str(install_dir), close_fds=True)


class Job:
    """Run one blocking update step off the Tk thread; the UI polls done/result/error."""

    def __init__(self, work):
        self.progress = 0.
        self.result = None
        self.error = ''
        self.done = False
        self.thread = threading.Thread(target=self._run, args=(work,), name='XiaohanUpdate', daemon=True)
        self.thread.start()

    def _run(self, work):
        try:
            self.result = work(self)
        except UpdateError as exc:
            self.error = str(exc)
        except Exception as exc:  # A background thread has no console; surface the cause in the UI.
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            self.done = True
