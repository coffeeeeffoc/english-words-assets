"""Fetch pinned upstream files and all primary/middle-school kajweb wordlists."""
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import zipfile
import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'sources'
sys.stdout.reconfigure(encoding='utf-8')
session = requests.Session()
session.trust_env = False


def get(url, path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            with session.get(url, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                temp = path.with_suffix(path.suffix + '.part')
                with temp.open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024):
                        output.write(chunk)
                if response.headers.get('Content-Length') and temp.stat().st_size != int(response.headers['Content-Length']):
                    raise ValueError('Incomplete download')
                temp.replace(path)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    directory = SOURCES / 'kajweb'
    provenance = directory / 'source.json'
    if not provenance.exists():
        response = session.get('https://api.github.com/repos/kajweb/dict/commits/master', timeout=60)
        response.raise_for_status()
        provenance.write_text(json.dumps({'repository': 'kajweb/dict', 'commit': response.json()['sha']}), encoding='utf-8')
    revision = json.loads(provenance.read_text(encoding='utf-8'))['commit']
    base = f'https://raw.githubusercontent.com/kajweb/dict/{revision}/'
    get(base + 'README.md', directory / 'README.md')
    lists = []
    for line in (directory / 'README.md').read_text(encoding='utf-8').splitlines():
        if not line.startswith('|') or not any(t in line for t in ('小学', '初中', '中考')):
            continue
        cells = [c.strip() for c in line.split('|')]
        link = re.search(r'\[本地地址\]\(([^)]+)\)', line)
        if not link:
            continue
        title, count, list_id = cells[3], int(cells[4]), cells[-3]
        archive = directory / link[1]
        get(base + link[1], archive)
        raw_dir = directory / 'extracted' / list_id
        raw_dir.mkdir(parents=True, exist_ok=True)
        files = []
        with zipfile.ZipFile(archive) as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue
                # Extract only the basename, never trust archive paths.
                target = raw_dir / Path(info.filename).name
                if target.name in files:
                    raise ValueError('Duplicate archive member')
                target.write_bytes(zipped.read(info))
                files.append(target.name)
        lists.append({'id': list_id, 'title': title, 'expected_count': count,
                      'source_path': link[1], 'source_url': base + link[1],
                      'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': files})
        print(list_id, title, count, flush=True)
    (directory / 'lists.json').write_text(json.dumps(lists, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Downloaded', len(lists), 'wordlists')


if __name__ == '__main__':
    main()
