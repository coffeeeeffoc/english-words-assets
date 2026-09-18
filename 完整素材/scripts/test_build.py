"""Small offline regression checks for normalization, mapping, and fallback provenance."""
import sqlite3
from build_dictionary import word_key, describe_list, candidates, SCHEMA

assert word_key('  ice   cream ') == 'ice cream'
assert word_key('don’t') == "don't"
assert word_key('US') != word_key('us')
assert word_key('café') == 'café'
row = {'id':'PEPChuZhong9_1','title':'人教版初中英语-九年级全册'}
stage, edition, grade, volume, kind = describe_list(row)
assert (stage,grade,volume,kind) == ('初中',9,'全册','textbook')
lists = [dict(id=row['id'],stage=stage,edition=edition,grade=grade,volume=volume)]
assert not candidates(dict(stage=stage,edition=edition,grade=9,volume='上册'),lists)
assert not candidates(dict(stage='初中（五•四学制）',edition=edition,grade=9,volume=volume),lists)
assert candidates(lists[0],lists) == [row['id']]
db = sqlite3.connect(':memory:'); db.executescript(SCHEMA)
db.executemany('INSERT INTO sources VALUES(?,?,?,?)',[('base','','',''),('list','','','')])
db.execute("INSERT INTO words VALUES(1,'apple','苹果','base-ipa','','base')")
db.execute("INSERT INTO wordlists VALUES('sample','test','小学','edition',3,'上册','textbook','legacy_unverified',2,'list','raw')")
db.execute("INSERT INTO entries VALUES('sample',1,1,1,'apple','','','','',NULL,'raw-1')")
assert db.execute('SELECT meaning,phonetic,meaning_source,phonetic_source FROM vocabulary').fetchone() == ('苹果','base-ipa','base','base')
db.execute("INSERT INTO words VALUES(2,'test','test','','','base')")
db.execute("INSERT INTO entries VALUES('sample',2,2,2,'test','','','','',NULL,'raw-2')")
assert db.execute('SELECT count(*) FROM missing_fields').fetchone()[0] == 1
assert db.execute('SELECT count(*) FROM ready_vocabulary').fetchone()[0] == 1
print('Build self-check passed')
