"""Build the compact SQLite dictionary and auditable reports using stdlib only."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import unicodedata

ARCHIVE = Path(__file__).resolve().parents[1]
OUTPUT = ARCHIVE.parent / '精简词库'
REPORTS = ARCHIVE / 'reports'
sys.stdout.reconfigure(encoding='utf-8')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def clean(text):
    return unicodedata.normalize('NFC', (text or '').strip()).replace('\\n', '\n')


def word_key(text):
    # Keep case and accents: US/us and proper names must not be conflated.
    return ' '.join(clean(text).replace('’', "'").split())


def describe_list(item):
    title = item['title']
    stage = '小学' if '小学' in title else '初中'
    grade = next((i for i in range(1, 10) if '一二三四五六七八九'[i-1]+'年级' in title), None)
    volume = '上册' if '上册' in title else '下册' if '下册' in title else '全册' if '全册' in title else None
    edition = '人教版（主编：吴欣）' if item['id'].startswith('PEPXiaoXue') else '人教版' if item['id'].startswith('PEPChuZhong') else '外研社版（主编：孙有中）' if item['id'].startswith('WaiYanSheChuZhong') else None
    return stage, edition, grade, volume, 'textbook' if grade else 'exam'


def candidates(book, lists):
    return [l['id'] for l in lists if
            l['stage'] == book['stage'] and l['edition'] == book['edition'] and
            l['grade'] == book['grade'] and l['volume'] == book['volume']]


def export_csv(db, sql, path):
    cursor = db.execute(sql)
    with path.open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.writer(output)
        writer.writerow([x[0] for x in cursor.description])
        writer.writerows(cursor)


SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE sources(id TEXT PRIMARY KEY, url TEXT, revision TEXT, license_note TEXT);
CREATE TABLE words(
 id INTEGER PRIMARY KEY, word TEXT UNIQUE NOT NULL, meaning TEXT NOT NULL,
 phonetic TEXT NOT NULL, tags TEXT NOT NULL, source TEXT REFERENCES sources(id));
CREATE TABLE wordlists(
 id TEXT PRIMARY KEY, title TEXT, stage TEXT, edition TEXT, grade INTEGER,
 volume TEXT, kind TEXT, status TEXT, entry_count INTEGER,
 source TEXT REFERENCES sources(id), source_file TEXT);
CREATE TABLE entries(
 list_id TEXT REFERENCES wordlists(id), ordinal INTEGER, source_rank INTEGER,
 word_id INTEGER REFERENCES words(id), original_word TEXT, meaning TEXT,
 phonetic TEXT, uk_phonetic TEXT, us_phonetic TEXT, unit TEXT,
 source_record_id TEXT, PRIMARY KEY(list_id,ordinal));
CREATE INDEX entries_word ON entries(word_id);
CREATE TABLE textbooks(
 id TEXT PRIMARY KEY, title TEXT, stage TEXT, edition TEXT, grade INTEGER, volume TEXT,
 revised_2022 INTEGER, updated_at TEXT, page_url TEXT, pdf_bytes INTEGER,
 coverage TEXT, candidate_lists TEXT, reason TEXT);
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
CREATE VIEW ready_words AS
 SELECT * FROM words WHERE meaning GLOB '*[一-鿿]*' AND trim(phonetic)!='';
CREATE VIEW vocabulary AS
 SELECT l.id AS list_id,l.title,l.stage,l.edition,l.grade,l.volume,l.status,
 e.ordinal,e.unit,w.id AS word_id,w.word,e.original_word,
 CASE WHEN trim(e.meaning)!='' THEN e.meaning ELSE w.meaning END AS meaning,
 COALESCE(NULLIF(e.uk_phonetic,''),NULLIF(e.us_phonetic,''),NULLIF(e.phonetic,''),NULLIF(w.phonetic,''),'') AS phonetic,
 e.uk_phonetic,e.us_phonetic,
 CASE WHEN trim(e.meaning)!='' THEN l.source ELSE w.source END AS meaning_source,
 CASE WHEN e.uk_phonetic!='' OR e.us_phonetic!='' OR e.phonetic!='' THEN l.source ELSE w.source END AS phonetic_source
 FROM entries e JOIN words w ON w.id=e.word_id JOIN wordlists l ON l.id=e.list_id;
CREATE VIEW ready_vocabulary AS
 SELECT * FROM vocabulary WHERE meaning GLOB '*[一-鿿]*' AND trim(phonetic)!='';
CREATE VIEW missing_fields AS
 SELECT *,CASE WHEN NOT meaning GLOB '*[一-鿿]*' THEN 'missing_chinese' ELSE '' END AS meaning_issue,
 CASE WHEN trim(phonetic)='' THEN 'missing_phonetic' ELSE '' END AS phonetic_issue
 FROM vocabulary WHERE NOT meaning GLOB '*[一-鿿]*' OR trim(phonetic)='';
CREATE VIEW missing_textbooks AS SELECT * FROM textbooks WHERE coverage!='verified';
CREATE VIEW textbook_slots AS
 SELECT stage,edition,grade,volume,revised_2022,count(*) AS resource_count,
 group_concat(id) AS resource_ids FROM textbooks GROUP BY stage,edition,grade,volume,revised_2022;
'''


def main():
    OUTPUT.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    database = OUTPUT / '英语词库.sqlite'
    temp = OUTPUT / '英语词库.build.sqlite'
    if temp.exists():
        temp.unlink()
    db = sqlite3.connect(temp)
    db.executescript(SCHEMA)
    for key in ('ecdict', 'kajweb'):
        provenance = load(ARCHIVE / 'sources' / key / 'source.json')
        license_note = 'Repository MIT; see bundled license and upstream data origins.' if key == 'ecdict' else 'Third-party collected data; upstream README does not establish a content redistribution license.'
        db.execute('INSERT INTO sources VALUES(?,?,?,?)',
                   (key, 'https://github.com/'+provenance['repository'], provenance['commit'], license_note))
    db.execute('INSERT INTO sources VALUES(?,?,?,?)', ('smartedu', 'https://basic.smartedu.cn/elecEdu', '2026-09-18 catalog snapshot', 'Textbook content belongs to its respective rights holders.'))
    counts = Counter()
    issues = []
    with (ARCHIVE / 'sources/ecdict/ecdict.csv').open(encoding='utf-8-sig', newline='') as source:
        reader = csv.DictReader(source)
        assert {'word', 'translation', 'phonetic', 'tag'} <= set(reader.fieldnames)
        for raw in reader:
            counts['ecdict_rows'] += 1
            word, meaning, phonetic = word_key(raw['word']), clean(raw['translation']), clean(raw['phonetic'])
            if not word:
                issues.append({'kind': 'empty_word', 'row': counts['ecdict_rows']})
                continue
            try:
                db.execute('INSERT INTO words(word,meaning,phonetic,tags,source) VALUES(?,?,?,?,?)',
                           (word, meaning, phonetic, clean(raw['tag']), 'ecdict'))
            except sqlite3.IntegrityError:
                # Keep the first upstream entry; preserve collision evidence instead of guessing.
                issues.append({'kind': 'normalized_duplicate', 'row': counts['ecdict_rows'], 'word': word,
                               'meaning': meaning, 'phonetic': phonetic})
    db.commit()
    counts['ecdict_unique'] = db.execute('SELECT count(*) FROM words').fetchone()[0]
    print('Base imported', counts['ecdict_unique'], flush=True)
    normalized_lists = []
    for item in load(ARCHIVE / 'sources/kajweb/lists.json'):
        stage, edition, grade, volume, kind = describe_list(item)
        normalized_lists.append(dict(id=item['id'], stage=stage, edition=edition, grade=grade, volume=volume))
        raw_rows = []
        for filename in item['files']:
            if filename.endswith('.json'):
                path = ARCHIVE / 'sources/kajweb/extracted' / item['id'] / filename
                raw_rows.extend(json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip())
        if len(raw_rows) != item['expected_count']:
            raise ValueError(f"{item['id']}: source count mismatch")
        db.execute('INSERT INTO wordlists VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (item['id'], item['title'], stage, edition, grade, volume, kind,
                    'legacy_unverified' if kind == 'textbook' else 'exam_reference', len(raw_rows), 'kajweb', item['source_path']))
        for ordinal, raw in enumerate(raw_rows, 1):
            assert raw['bookId'] == item['id']
            detail = raw['content']['word']['content']
            original = raw['headWord']
            word = word_key(original)
            assert word
            meaning = '\n'.join((clean(t.get('pos'))+'. ' if t.get('pos') else '')+clean(t.get('tranCn'))
                                for t in detail.get('trans', []) if clean(t.get('tranCn')))
            generic, uk, us = [clean(detail.get(k)) for k in ('phone', 'ukphone', 'usphone')]
            existing = db.execute('SELECT id FROM words WHERE word=?', (word,)).fetchone()
            if not existing:
                db.execute('INSERT INTO words(word,meaning,phonetic,tags,source) VALUES(?,?,?,?,?)',
                           (word, meaning, uk or us or generic, '', 'kajweb'))
                existing = (db.execute('SELECT last_insert_rowid()').fetchone()[0],)
                counts['added_from_wordlists'] += 1
            db.execute('INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (item['id'], ordinal, raw.get('wordRank'), existing[0], original,
                        meaning, generic, uk, us, None, raw['content']['word'].get('wordId')))
        print('List imported', item['id'], len(raw_rows), flush=True)
    manifest = {r['book_id']: r for r in load(ARCHIVE / 'metadata/manifest.json') if r['kind'] == 'textbook'}
    for book in load(ARCHIVE / 'metadata/books.json'):
        tags = {t['tag_dimension_id']: t['tag_name'] for t in book['tag_list']}
        grade = next((i for i in range(1,10) if tags.get('zxxnj') == '一二三四五六七八九'[i-1]+'年级'), None)
        info = dict(stage=tags['zxxxd'], edition=tags['zxxbb'], grade=grade, volume=tags.get('zxxcc'))
        found = candidates(info, normalized_lists)
        status = 'candidate_unverified' if found else 'missing'
        reason = 'Same stage/edition family/grade/volume only; revision and contents not verified.' if found else 'No matching wordlist in the imported source snapshot.'
        if '2022' in book['title'] and found:
            reason = '2022-curriculum revision; legacy list cannot establish coverage.'
        db.execute('INSERT INTO textbooks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (book['id'], book['title'], info['stage'], info['edition'], grade, info['volume'],
                    int('2022' in book['title']), book.get('update_time'), manifest[book['id']]['page_url'],
                    manifest[book['id']]['size'], status, json.dumps(found, ensure_ascii=False), reason))
    counts.update({name: db.execute(sql).fetchone()[0] for name, sql in {
        'words': 'SELECT count(*) FROM words',
        'ready_words': 'SELECT count(*) FROM ready_words',
        'base_missing_chinese': "SELECT count(*) FROM words WHERE source='ecdict' AND NOT meaning GLOB '*[一-鿿]*'",
        'base_missing_phonetic': "SELECT count(*) FROM words WHERE source='ecdict' AND trim(phonetic)=''",
        'wordlists': 'SELECT count(*) FROM wordlists',
        'textbook_wordlists': "SELECT count(*) FROM wordlists WHERE kind='textbook'",
        'exam_wordlists': "SELECT count(*) FROM wordlists WHERE kind='exam'",
        'list_entries': 'SELECT count(*) FROM entries',
        'list_unique_words': 'SELECT count(DISTINCT word_id) FROM entries',
        'ready_list_entries': 'SELECT count(*) FROM ready_vocabulary',
        'list_missing_fields': 'SELECT count(*) FROM missing_fields',
        'list_missing_chinese': "SELECT count(*) FROM vocabulary WHERE NOT meaning GLOB '*[一-鿿]*'",
        'list_missing_phonetic': "SELECT count(*) FROM vocabulary WHERE trim(phonetic)=''",
        'official_textbooks': 'SELECT count(*) FROM textbooks',
        'official_slots': 'SELECT count(*) FROM textbook_slots',
        'verified_textbooks': "SELECT count(*) FROM textbooks WHERE coverage='verified'",
        'candidate_textbooks': "SELECT count(*) FROM textbooks WHERE coverage='candidate_unverified'",
        'no_candidate_textbooks': "SELECT count(*) FROM textbooks WHERE coverage='missing'",
    }.items()})
    counts['normalization_issues'] = len(issues)
    (REPORTS / 'normalization-issues.json').write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, sql in {
        'textbook-coverage.csv': 'SELECT * FROM textbooks ORDER BY stage,edition,grade,volume',
        'missing-word-fields.csv': 'SELECT * FROM missing_fields',
        'wordlists.csv': 'SELECT * FROM wordlists',
        'textbook-slots.csv': 'SELECT * FROM textbook_slots',
        'coverage-by-edition.csv': '''SELECT stage,edition,count(*) AS books,
          sum(coverage='candidate_unverified') AS legacy_candidates,
          sum(coverage='missing') AS no_candidate,sum(coverage='verified') AS verified
          FROM textbooks GROUP BY stage,edition ORDER BY stage,edition''',
    }.items():
        export_csv(db, sql, REPORTS / name)
    (REPORTS / 'summary.json').write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding='utf-8')
    db.execute('INSERT INTO metadata VALUES(?,?)', ('summary', json.dumps(counts, ensure_ascii=False)))
    db.execute('INSERT INTO metadata VALUES(?,?)', ('scope', '2026-09-18 SmartEdu primary and middle-school English; kajweb legacy textbook lists plus exam references; complete imported ECDICT CSV.'))
    db.commit()
    assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert counts['list_entries'] == sum(i['expected_count'] for i in load(ARCHIVE / 'sources/kajweb/lists.json'))
    assert counts['candidate_textbooks'] + counts['no_candidate_textbooks'] + counts['verified_textbooks'] == counts['official_textbooks']
    db.execute('VACUUM')
    db.close()
    temp.replace(database)
    shutil.copyfile(ARCHIVE / 'sources/ecdict/LICENSE', OUTPUT / 'LICENSE-ECDICT.txt')
    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print('Database SHA256', hashlib.sha256(database.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
