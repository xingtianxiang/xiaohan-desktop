"""Publish the built portable zip and latest.json as a GitHub release, then verify it anonymously.

Run after work/build_portable.py and work/check_portable.py, from a commit that is already pushed:
    python work/publish_release.py --notes-file <说明.md>
Installed copies read releases/latest/download/latest.json, so publishing is what offers the update.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'outputs/XiaohanDesktop'
sys.path.insert(0, str(APP))
from version import VERSION, RELEASE_REPO  # noqa: E402
import updater  # noqa: E402


def run(*args, check=True):
    return subprocess.run(args, cwd=ROOT, check=check, text=True, encoding='utf-8', capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--notes-file', type=Path, required=True)
    args = parser.parse_args()
    notes = args.notes_file.read_text(encoding='utf-8').strip()
    if not notes:
        raise SystemExit('更新说明不能为空')

    build = json.loads((APP / 'portable-build.json').read_text(encoding='utf-8'))
    if build.get('version') != VERSION:
        raise SystemExit('portable-build.json 不是当前版本，先运行 work/build_portable.py')
    archive = ROOT / 'outputs/releases' / VERSION / build['archive']
    data = archive.read_bytes()
    if len(data) != build['bytes'] or hashlib.sha256(data).hexdigest() != build['sha256']:
        raise SystemExit('安装包和构建记录不一致')

    # The release tag must point at pushed source identical to what was packaged.
    if run('git', 'status', '--porcelain', '--', str(APP)).stdout.strip():
        raise SystemExit('outputs/XiaohanDesktop 还有未提交的改动')
    current = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in APP.glob('*.py')}
    if current != build['source_sha256']:
        raise SystemExit('安装包不是用当前源码构建的，请重新打包')
    commit = run('git', 'rev-parse', 'HEAD').stdout.strip()
    run('git', 'fetch', 'origin')
    if not run('git', 'branch', '-r', '--contains', commit).stdout.strip():
        raise SystemExit('当前提交还没有推送到 GitHub')

    tag = f'v{VERSION}'
    if run('gh', 'release', 'view', tag, '--repo', RELEASE_REPO, check=False).returncode == 0:
        raise SystemExit(f'{tag} 已经发布过，先在 version.py 里提高版本号')

    manifest = updater.validate_manifest({
        'version': VERSION,
        'notes': notes,
        'page': f'https://github.com/{RELEASE_REPO}/releases/tag/{tag}',
        'windows': {
            'urls': [f'https://github.com/{RELEASE_REPO}/releases/download/{tag}/{archive.name}'],
            'sha256': build['sha256'],
            'bytes': build['bytes'],
        },
    })
    latest = archive.parent / 'latest.json'
    latest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    run('gh', 'release', 'create', tag, '--repo', RELEASE_REPO, '--target', commit,
        '--title', f'小汉 {VERSION}', '--notes-file', str(args.notes_file), str(archive), str(latest))

    # Verify exactly what installed copies will see, without GitHub credentials.
    published = updater.fetch_manifest()
    if published != manifest:
        raise SystemExit('线上 latest.json 和本次发布不一致')
    with tempfile.TemporaryDirectory() as folder:
        updater.download(published['windows'], Path(folder) / archive.name)
    print(json.dumps({'release': manifest['page'], 'commit': commit, 'sha256': build['sha256'],
                      'bytes': build['bytes'], 'anonymous_download_verified': True}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
