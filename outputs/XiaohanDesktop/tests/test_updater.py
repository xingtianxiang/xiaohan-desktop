import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import updater
from model import PetState
from version import VERSION


def manifest_for(archive, version='9.9.9', url=None):
    data = archive.read_bytes()
    return {'version': version, 'notes': '测试', 'windows': {
        'urls': [url or archive.as_uri()], 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}}


def write_release(folder, files):
    archive = Path(folder) / 'release.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        for name, text in files.items():
            bundle.writestr(name, text)
    return archive


RELEASE = {'小汉/小汉.exe': 'new exe', '小汉/_internal/core.dll': 'new dll', '小汉/使用说明.txt': 'new notes'}


class VersionAndManifestTests(unittest.TestCase):
    def test_versions_compare_numerically(self):
        self.assertTrue(updater.is_newer('1.10.0', '1.9.9'))
        self.assertFalse(updater.is_newer(VERSION))
        for bad in ('1.2', 'v1.2.3', '1.2.3-beta', 3):
            with self.assertRaises(updater.UpdateError):
                updater.parse_version(bad)

    def test_manifest_requires_https_hash_and_size(self):
        good = {'version': '1.2.0', 'windows': {'urls': ['https://example.com/a.zip'], 'sha256': 'a'*64, 'bytes': 10}}
        self.assertIs(updater.validate_manifest(good), good)
        broken = [
            {**good, 'windows': {**good['windows'], 'urls': ['http://example.com/a.zip']}},
            {**good, 'windows': {**good['windows'], 'urls': ['file:///C:/a.zip']}},
            {**good, 'windows': {**good['windows'], 'sha256': 'A'*64}},
            {**good, 'windows': {**good['windows'], 'bytes': updater.MAX_PACKAGE_BYTES+1}},
            {**good, 'windows': {**good['windows'], 'bytes': True}},
            {**good, 'version': '1.2'},
            {'version': '1.2.0'},
            [],
        ]
        for manifest in broken:
            with self.subTest(manifest=manifest), self.assertRaises(updater.UpdateError):
                updater.validate_manifest(manifest)

    def test_local_files_only_allowed_through_test_hook(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'latest.json'
            archive = write_release(folder, RELEASE)
            path.write_text(json.dumps(manifest_for(archive)), encoding='utf-8')
            with self.assertRaises(updater.UpdateError):
                updater.fetch_manifest(path.as_uri())
            self.assertEqual(updater.fetch_manifest(path.as_uri(), allow_file=True)['version'], '9.9.9')
            path.write_text('{"version":', encoding='utf-8')
            with self.assertRaises(updater.UpdateError):
                updater.fetch_manifest(path.as_uri(), allow_file=True)


class DownloadAndExtractTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_download_checks_hash_and_falls_back_to_next_url(self):
        archive = write_release(self.root, RELEASE)
        package = manifest_for(archive)['windows']
        missing = (self.root / 'missing.zip').as_uri()
        package['urls'].insert(0, missing)
        seen = []
        target = updater.download(package, self.root / 'download.zip', seen.append)
        self.assertEqual(target.read_bytes(), archive.read_bytes())
        self.assertEqual(seen[-1], 1)
        package['sha256'] = '0'*64
        with self.assertRaises(updater.UpdateError):
            updater.download(package, self.root / 'download.zip')
        package = manifest_for(archive)['windows']
        package['bytes'] -= 1
        with self.assertRaises(updater.UpdateError):
            updater.download(package, self.root / 'download.zip')

    def test_extract_rejects_unsafe_or_save_entries(self):
        for name in ('小汉/../evil.txt', '小汉\\..\\evil.txt', 'other/小汉.exe', '小汉/data/pet.json', '小汉/.update/x', '/小汉/a', 'C:/小汉/a'):
            with self.subTest(name=name):
                archive = write_release(self.root, {**RELEASE, name: 'x'})
                with self.assertRaises(updater.UpdateError):
                    updater.extract(archive, self.root / 'out')
        archive = write_release(self.root, {'小汉/使用说明.txt': 'only notes'})
        with self.assertRaises(updater.UpdateError):
            updater.extract(archive, self.root / 'out2')
        (self.root / 'bad.zip').write_bytes(b'not a zip')
        with self.assertRaises(updater.UpdateError):
            updater.extract(self.root / 'bad.zip', self.root / 'out3')

    def test_prepare_stages_inside_install_folder(self):
        archive = write_release(self.root, RELEASE)
        install = self.root / 'install'
        install.mkdir()
        staged = updater.prepare(install, manifest_for(archive))
        self.assertEqual(staged, install / '.update' / '9.9.9' / '小汉')
        self.assertEqual((staged / '_internal/core.dll').read_text(), 'new dll')
        self.assertFalse((install / '.update/9.9.9/package.zip').exists())


class ApplyUpdateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.install = root / '小汉'
        (self.install / '_internal').mkdir(parents=True)
        (self.install / '小汉.exe').write_text('old exe')
        (self.install / '_internal/core.dll').write_text('old dll')
        (self.install / '_internal/removed.dll').write_text('old only')
        (self.install / '使用说明.txt').write_text('old notes')
        state = PetState()
        state.outfit = 'yellow'
        state.save(self.install / 'data/pet.json')
        self.save_bytes = (self.install / 'data/pet.json').read_bytes()
        self.staged = updater.extract(write_release(root, RELEASE), root / 'staged')

    def tearDown(self):
        self.folder.cleanup()

    def assert_old_version(self):
        self.assertEqual((self.install / '小汉.exe').read_text(), 'old exe')
        self.assertEqual((self.install / '_internal/core.dll').read_text(), 'old dll')
        self.assertEqual((self.install / '_internal/removed.dll').read_text(), 'old only')
        self.assertEqual((self.install / 'data/pet.json').read_bytes(), self.save_bytes)

    def test_swap_replaces_program_and_keeps_save(self):
        updater.apply_update(self.staged, self.install)
        self.assertEqual((self.install / '小汉.exe').read_text(), 'new exe')
        self.assertEqual((self.install / '_internal/core.dll').read_text(), 'new dll')
        self.assertFalse((self.install / '_internal/removed.dll').exists())
        self.assertEqual((self.install / 'data/pet.json').read_bytes(), self.save_bytes)
        self.assertEqual((self.install / '.update/previous/小汉.exe').read_text(), 'old exe')
        updater.cleanup(self.install)
        self.assertFalse((self.install / '.update').exists())

    def test_copy_failure_restores_old_program(self):
        real_copy = shutil.copy2
        def fail_on_notes(source, target, *args, **kwargs):
            if Path(source).name == '使用说明.txt':
                raise PermissionError('blocked by scanner')
            return real_copy(source, target, *args, **kwargs)
        with patch('updater.shutil.copy2', side_effect=fail_on_notes):
            with self.assertRaises(updater.UpdateError) as caught:
                updater.apply_update(self.staged, self.install)
        self.assertIn('已恢复原来的版本', str(caught.exception))
        self.assert_old_version()
        self.assertEqual((self.install / '使用说明.txt').read_text(), 'old notes')

    @unittest.skipUnless(os.name == 'nt', 'Windows file locking')
    def test_locked_old_file_aborts_without_partial_install(self):
        with patch.object(updater, 'MOVE_RETRY_SECONDS', 0), open(self.install / '使用说明.txt', 'rb'):
            # Python's open() denies delete sharing, so the move fails like an antivirus lock.
            with self.assertRaises(updater.UpdateError):
                updater.apply_update(self.staged, self.install)
        self.assert_old_version()
        self.assertEqual((self.install / '使用说明.txt').read_text(), 'old notes')


@unittest.skipUnless(os.name == 'nt', 'Windows process API')
class WaitForExitTests(unittest.TestCase):
    def test_returns_after_process_exits(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(.3)'])
        updater.wait_for_exit(child.pid, timeout=10)
        self.assertIsNotNone(child.poll())

    def test_times_out_while_process_runs(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'])
        try:
            with self.assertRaises(updater.UpdateError):
                updater.wait_for_exit(child.pid, timeout=.2)
        finally:
            child.kill()
            child.wait()

    def test_missing_process_counts_as_exited(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        child.wait()
        updater.wait_for_exit(child.pid, timeout=1)
