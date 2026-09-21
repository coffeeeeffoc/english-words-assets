"""Rebuild/check the manually reviewed Sun Youzhong textbook unit lists.

python review_fltrp_sun.py [--check] [--pdf-dir path]
No network or OCR dependency. Optional PDFs must match the recorded SHA-256.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3

MATERIALS = Path(__file__).resolve().parents[1]
ROOT = MATERIALS / 'reviewed-units'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def output(path, value, check):
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if check:
        assert path.read_bytes() == text.encode('utf-8'), f'Rebuild needed: {path}'
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--pdf-dir', type=Path)
    args = parser.parse_args()
    books = []
    database = MATERIALS.parent / '精简词库/英语词库.sqlite'
    with sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True) as connection:
        for source in read(ROOT / 'sources/fltrp-sun-manifest.json'):
            if args.pdf_dir:
                pdf = args.pdf_dir / (source['bookId'] + '.pdf')
                assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source['sha256'], pdf
            entries, unit, page = [], None, None
            for line in (ROOT / 'sources' / source['file']).read_text(encoding='utf-8').splitlines():
                if line.startswith('# PDF '):
                    page = int(line[6:])
                elif line.startswith('# '):
                    unit = line[2:]
                elif line:
                    word, meaning = line.split('\t')
                    assert unit in source['expectedUnits'], (source['id'], unit)
                    assert source['pages'][0] <= page <= source['pages'][1]
                    assert re.search('[A-Za-z]', word) and re.search('[一-鿿]', meaning)
                    assert word == word.strip() and meaning == meaning.strip()
                    # The primary list has no IPA; exact dictionary matches are supplemental.
                    # Middle-school IPA is scanned: leave unreviewed pronunciation blank.
                    match = connection.execute('SELECT phonetic, source FROM words WHERE word=?', (word,)).fetchone() if source['grade'] < 7 else None
                    phonetic = match[0] if match and match[0] else ''
                    entries.append(dict(ordinal=len(entries) + 1, word=word, meaning=meaning,
                                        phonetic=phonetic, unit=unit, pdfPage=page,
                                        phoneticSource=match[1] if phonetic else ''))
            assert dict(Counter(e['unit'] for e in entries)) == source['expectedUnits'], source['id']
            assert list(dict.fromkeys(e['unit'] for e in entries)) == list(source['expectedUnits']), source['id']
            assert len({(e['unit'], e['word']) for e in entries}) == len(entries), source['id']
            output(ROOT / 'books' / (source['id'] + '.json'), dict(id=source['id'], entries=entries), args.check)
            notes = ('按此官方扫描PDF的 Words and expressions 主词表逐页人工转录核验，保持原书列顺序、Welcome/Starter 与 Unit 分组；包含非加粗词和词组。'
                     '另列的 Proper nouns 专名表、戏剧附录和字母序重复表不混入单元。括号词形保留在释义中，练习词采用主词形；未合并不同版次。')
            notes += ('小学原词表无音标，非空音标仅为本地词典精确词形补充，未匹配则留空。' if source['grade'] < 7 else
                      '扫描音标尚未逐条核准，phonetic 留空，不把OCR乱码或其他版次音标标为教材原音标。')
            books.append(dict(id=source['id'], title=f"外研版·孙有中 {'小学' if source['grade'] < 7 else '初中'}{source['grade']}年级{source['volume']}（2022课标）",
                              publisherId='fltrp', publisher='外语教学与研究出版社', edition=source['edition'],
                              grade=source['grade'], volume=source['volume'], units=list(source['expectedUnits']),
                              count=len(entries), source='国家中小学智慧教育平台·外研社官方教材PDF',
                              verification=dict(status='pdf-reviewed', unitGranularity='unit',
                                  evidence=[dict(url=source['url'], pageUrl=source['pageUrl'], sha256=source['sha256'], pages=source['pages'])], notes=notes),
                              url='books/' + source['id'] + '.json'))
    output(ROOT / 'catalog-new-fltrp.json', dict(schema=1, books=books), args.check)
    print(f"Sun Youzhong: {len(books)} books, {sum(b['count'] for b in books)} entries, {sum(len(b['units']) for b in books)} units")


if __name__ == '__main__':
    main()
