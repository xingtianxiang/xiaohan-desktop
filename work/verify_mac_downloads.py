"""Verify downloaded artifacts and copy their unchanged distribution ZIPs."""
import hashlib
import io
import json
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'arm64': 'e8dc2b83269fd7317db138517387edf22b13dac0fb16bbdeda8d4f9d3635bec1',
    'x64': '604ef1db5c9326b7dd7280921455ab31f02fc7463e288a711f64f5c518366406',
}
reports = {}
for arch, expected in EXPECTED.items():
    raw = (ROOT / 'work/desktop-qa/cloud-upload' / f'{arch}-artifact.zip').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, arch
    with zipfile.ZipFile(io.BytesIO(raw)) as artifact:
        assert artifact.testzip() is None
        build = json.loads(artifact.read('build.json'))
        verification = json.loads(artifact.read('verification.json'))
        archive = artifact.read(build['archive'])
        print(arch, build['archive'], build['bytes'], build['sha256'], json.dumps(verification['verification']))
        # ditto writes UTF-8 names without the ZIP language flag; macOS decodes them correctly.
        with zipfile.ZipFile(io.BytesIO(archive), metadata_encoding='utf-8') as bundle:
            assert bundle.testzip() is None
            exe = bundle.getinfo('小汉 Mac/小汉.app/Contents/MacOS/小汉')
            assert (exe.external_attr >> 16) & 0o111, 'Missing executable mode'
            links = [p.filename for p in bundle.infolist() if stat.S_ISLNK(p.external_attr >> 16)]
            assert links, 'Missing framework symlinks'
            assert not any(p.filename.endswith('/pet.json') for p in bundle.infolist()), 'Personal save bundled'
        digest = hashlib.sha256(archive).hexdigest()
        assert digest == build['sha256'], 'Archive hash differs from build manifest'
        target = ROOT / 'outputs' / build['archive']
        if target.exists():
            assert target.read_bytes() == archive
        else:
            target.write_bytes(archive)
        reports[arch] = {'build': build, 'verification': verification['verification'],
                         'artifact_sha256': expected, 'local_path': str(target),
                         'zip_crc_verified': True, 'executable_mode_verified': True,
                         'symlinks_preserved': len(links)}
report = {'repository': 'https://github.com/xingtianxiang/xiaohan-desktop',
          'run': 'https://github.com/xingtianxiang/xiaohan-desktop/actions/runs/43402795962',
          'commit': 'a4c9613bb2928bdeca9f7506969c9a25bf94c7be',
          'unit_tests_per_architecture': 52, 'unit_tests_passed_per_architecture': 52,
          'previous_run': {'id': 43402352296, 'result': 'failed',
                           'cause': 'Test expected unresolved macOS /var temporary path; production resolves /private/var.',
                           'fix': 'Resolve expected executable parent consistently; all tests rerun.'},
          'packages': reports}
(ROOT / 'outputs/XiaohanDesktop/verification-macos.json').write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
