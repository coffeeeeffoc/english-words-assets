"""Rebuild reviewed primary books from page-labelled transcriptions; no network needed."""
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parent


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    database = ROOT.parents[1] / '精简词库/英语词库.sqlite'
    connection = sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)
    books = []
    for source in json.loads((ROOT / 'sources/primary-manifest.json').read_text(encoding='utf-8')):
        entries = []
        page = unit = None
        for line in (ROOT / 'sources' / source['file']).read_text(encoding='utf-8').splitlines():
            if line.startswith('# PDF '):
                page = int(line[6:])
            elif line.startswith('# Module '):
                unit = line[2:]
            elif line.strip():
                word, meaning = line.split('\t', 1)
                meaning = ' '.join(meaning.split())
                assert page and unit and word and re.search('[一-鿿]', meaning), line
                assert source['pages'][0] <= page <= source['pages'][1]
                # The primary textbook has no IPA. Supplement only exact dictionary matches.
                match = connection.execute('SELECT phonetic, source FROM words WHERE word=?', (word,)).fetchone()
                phonetic = match[0] if match else ''
                entries.append(dict(ordinal=len(entries)+1, word=word, meaning=meaning,
                                    phonetic=phonetic, unit=unit, pdfPage=page,
                                    phoneticSource=match[1] if phonetic else ''))
        units = list(dict.fromkeys(e['unit'] for e in entries))
        assert units == [f'Module {i}' for i in range(1, 11)], source['id']
        assert len({(e['unit'],e['word']) for e in entries}) == len(entries), source['id']
        book_id = source['id']
        save(ROOT / 'books' / (book_id + '.json'), dict(id=book_id, entries=entries))
        books.append(dict(id=book_id, title=f"外研版·陈琳 小学{source['grade']}年级{source['volume']}（2011课标）",
                          publisherId='fltrp', publisher='外语教学与研究出版社',
                          edition=source['edition'], grade=source['grade'], volume=source['volume'],
                          units=units, count=len(entries), source='外研社教材PDF逐页核验',
                          verification=dict(status='pdf-reviewed', unitGranularity='module',
                            evidence=[dict(url=source['url'], pages=source['pages'], sha256=source['sha256'])],
                            notes='按教材末尾 Words and Expressions in Each Module 原表完整收录，包含星号拓展词；Module 是本套教材词表的教学单元。未将词表猜分至 Unit 1/2 课时。歌曲、专名和分级阅读附录不混入模块。小学原表无音标，非空音标来自本地词典精确词形补充，未匹配则留空。此为陈琳旧版，不能替代孙有中新版。'),
                          url='books/' + book_id + '.json'))
    books.sort(key=lambda b: (b['grade'], 0 if b['volume']=='上册' else 1))
    save(ROOT / 'catalog-primary.json', dict(schema=1, books=books))
    print(f"Primary: {len(books)} books, {sum(b['count'] for b in books)} entries, 80 modules")


if __name__ == '__main__':
    main()
