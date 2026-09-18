"""Verify upstream Git blobs, source counts, local files, and SQLite relationships."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / '精简词库'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    checks = []
    for source in ('ecdict','kajweb'):
        directory = ROOT / 'sources' / source
        tree = {x['path']:x for x in load(directory / 'tree.json')['tree']}
        names = ['ecdict.csv','README.md','LICENSE'] if source=='ecdict' else ['README.md',*(x['source_path'] for x in load(directory / 'lists.json'))]
        for name in names:
            data = (directory / name).read_bytes()
            assert len(data) == tree[name]['size'], name
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == tree[name]['sha'], name
            checks.append({'path': (directory/name).relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    db = sqlite3.connect(OUT / '英语词库.sqlite')
    assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    books = load(ROOT / 'metadata/books.json')
    assert {r['id'] for r in books} == {r[0] for r in db.execute('SELECT id FROM textbooks')}
    assert db.execute('SELECT count(*) FROM entries').fetchone()[0] == sum(i['expected_count'] for i in load(ROOT/'sources/kajweb/lists.json'))
    assert not db.execute("SELECT 1 FROM ready_vocabulary WHERE phonetic='' OR NOT meaning GLOB '*[一-鿿]*' LIMIT 1").fetchone()
    assert not db.execute('SELECT 1 FROM entries WHERE unit IS NOT NULL LIMIT 1').fetchone(), 'Upstream wordlists contain no verified unit assignments'
    manifest = [x for x in load(ROOT / 'metadata/manifest.json') if x['kind']=='textbook']
    actions = []
    for row in manifest:
        path = ROOT / row['path']
        if row['status']=='complete':
            data = path.read_bytes()
            assert len(data)==row['size']
            assert hashlib.md5(data).hexdigest()==row['md5']
            checks.append({'path': row['path'],'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
        record = db.execute('SELECT stage,edition,grade,volume,coverage FROM textbooks WHERE id=?',(row['book_id'],)).fetchone()
        actions.append(dict(book_id=row['book_id'],stage=record[0],edition=record[1],grade=record[2],volume=record[3],
                            coverage=record[4],title=row['title'],pdf_bytes=row['size'],md5=row['md5'],
                            action='review_extracted_sample' if row['status']=='complete' else 'obtain_and_verify_wordlist_or_extract_pdf',
                            local_pdf=row['path'] if row['status']=='complete' else '',page_url=row['page_url']))
    with (ROOT/'reports/pdf-action-plan.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(actions[0]));writer.writeheader();writer.writerows(actions)
    missing = [x[0] for x in db.execute('SELECT DISTINCT word FROM missing_fields')]
    simple = [w for w in missing if re.fullmatch(r"[A-Za-z]+(?:[-'][A-Za-z]+)*",w)]
    extra = {'missing_phonetic_unique_items':len(missing),'simple_word_or_abbreviation_count':len(simple),
             'simple_word_or_abbreviation_items':simple,
             'phrases_or_punctuated_items_count':len(missing)-len(simple),
             'note':'Classification by spelling only. No phonetic strings were guessed or assembled from component words.'}
    (ROOT/'reports/missing-phonetic-breakdown.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2),encoding='utf-8')
    db.close()
    checks.append({'path':'../精简词库/英语词库.sqlite','sha256':hashlib.sha256((OUT/'英语词库.sqlite').read_bytes()).hexdigest(),'bytes':(OUT/'英语词库.sqlite').stat().st_size})
    result={'status':'passed','checks':['upstream_git_blob_hashes','expected_source_counts','sqlite_integrity','foreign_keys','379_official_ids','ready_fields','no_invented_units','downloaded_pdf_md5'], 'files':checks}
    (ROOT/'reports/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verification passed:',len(checks),'file hashes; official IDs and all wordlist counts reconciled.')


if __name__ == '__main__':
    main()
