"""Re-download the exact source snapshots used by this deliverable."""
import json
from pathlib import Path
from fetch_wordlists import get

ROOT = Path(__file__).resolve().parents[1]
REVISIONS = {
    'ecdict': ('skywind3000/ECDICT', 'bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b'),
    'kajweb': ('kajweb/dict', '3992bcb94c800a2fd38a9fd6ff95b2353e755363'),
}


def main():
    for name, (repo, revision) in REVISIONS.items():
        directory = ROOT / 'sources' / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'source.json').write_text(json.dumps({'repository': repo, 'commit': revision}, indent=2), encoding='utf-8')
        get(f'https://api.github.com/repos/{repo}/git/trees/{revision}?recursive=1', directory / 'tree.json')
        for file in ['README.md'] + (['LICENSE', 'ecdict.csv'] if name == 'ecdict' else []):
            get(f'https://raw.githubusercontent.com/{repo}/{revision}/{file}', directory / file)
    from fetch_wordlists import main as wordlists
    wordlists()


if __name__ == '__main__':
    main()
