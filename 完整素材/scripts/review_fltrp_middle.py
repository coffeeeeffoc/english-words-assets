"""Rebuild the six Chen Lin / Simon Greenall books from the exact reviewed PDFs.

python review_fltrp_middle.py --pdf-dir <directory containing fltrp-legacy-01..06.pdf>
python review_fltrp_middle.py --check

PDF layout is two columns, not alternating rows. Glossary page references are
resolved against actual body-page Unit headings; revision modules stay separate.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

MATERIALS = Path(__file__).resolve().parents[1]
OUT = MATERIALS / 'reviewed-units'
SOURCES = OUT / 'fltrp-middle-sources.json'
EXPECTED = {7: {'上册': 628, '下册': 441}, 8: {'上册': 320, '下册': 266}, 9: {'上册': 381, '下册': 125}}
# Matched against the PDFs' Pronunciation guide (e.g. seven-upper PDF page 141).
IPA = str.maketrans("!123467890*=%^;'#", "ɪʃəʒɑðʌθŋɔæɒʊɜˌˈˈ")
POS = re.compile(r'\b(?:n|v|adj|adv|pron|prep|conj|int|num|art)\s*[.（]')
PHONE = re.compile(r'/([^/\u3400-\u9fff]+)/')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # These reviewed payloads were published with CRLF; preserve their download hashes.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\r\n')


def normalise_word(word):
    return re.sub(r'\s+', ' ', word.replace('’', "'").replace('…', '...')).strip()


def dictionary_phones():
    phones = {}
    for path in sorted((MATERIALS / 'sources/kajweb/extracted').glob('WaiYanSheChuZhong_*/*.json')):
        for line in path.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            content = record['content']['word']['content']
            value = content.get('ukphone') or content.get('usphone')
            if value:
                phones[normalise_word(record['headWord']).lower()] = (value, 'kajweb')
    database = MATERIALS.parent / '精简词库/英语词库.sqlite'
    with sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True) as connection:
        for word, phone, source in connection.execute('SELECT word, phonetic, source FROM words WHERE phonetic != ""'):
            phones.setdefault(normalise_word(word).lower(), (phone, source))
    return phones


def split_entry(raw, use_dictionary, phones):
    match = PHONE.search(raw)
    chinese = re.search(r'[\u3400-\u9fff（［\[]', raw)
    pos = POS.search(raw)
    boundaries = [m.start() for m in [match, chinese, pos] if m]
    assert boundaries, raw
    stop = min(boundaries)
    head = raw[:stop].strip()
    # Parentheses describe spelling variants / plurals, not extra target letters.
    head = re.sub(r'\([^)]*\)', '', head).split('=')[0]
    head = normalise_word(head).rstrip(' ［[')
    head = re.sub(r'\s+\.{3,}$', '', head)
    # Slash inside sb./sth. and is/are is part of the expression.
    assert head and re.search('[A-Za-z]', head), raw
    meaning = raw[stop:]
    if match and match.start() == stop:
        meaning = raw[match.end():].lstrip('；; ')
        meaning = re.sub(r'^/[^/]+/\s*', '', meaning)
    meaning = PHONE.sub('', meaning)
    meaning = re.sub(r'\s+', ' ', meaning).strip('；; ')
    meaning = re.sub(r'(?<=[\u3400-\u9fff]) (?=[\u3400-\u9fff])', '', meaning)
    assert re.search(r'[\u3400-\u9fff]', meaning), (raw, meaning)
    phonetic = ''
    phonetic_source = None
    if match:
        if use_dictionary:
            value = phones.get(head.lower())
            if value:
                phonetic, phonetic_source = value
                phonetic = phonetic.replace('ә', 'ə').replace("'", 'ˈ').replace(':', 'ː')
                for old, new in [('əː', 'ɜː'), ('ei', 'eɪ'), ('ai', 'aɪ'), ('au', 'aʊ')]:
                    phonetic = phonetic.replace(old, new)
        else:
            phonetic = match.group(1).translate(IPA).strip().replace('；', '; ')
            phonetic_source = 'textbook-pdf'
    return head, meaning, phonetic, phonetic_source


def extract(book, pdf_path, transcript, phones):
    import pdfplumber
    import pypdfium2

    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == book['sha256'], f'Wrong PDF: {pdf_path}'
    pdf = pypdfium2.PdfDocument(pdf_path)
    text = [page.get_textpage().get_text_range() for page in pdf]
    entries, pending, module, start_page = [], '', '', None
    with pdfplumber.open(pdf_path) as layout:
        for page_number in book['wordListPages']:
            page = layout.pages[page_number - 1]
            columns = [transcript[str(page_number)]] if str(page_number) in transcript else [
                page.crop((0, 0, page.width / 2, page.height)).extract_text() or '',
                page.crop((page.width / 2, 0, page.width, page.height)).extract_text() or '',
            ]
            assert any(columns), f'Unreviewed scanned page {page_number}'
            for column in columns:
                for line in column.splitlines():
                    line = line.strip()
                    if (not line or line.isdigit() or line in ['Starter', 'expressions']
                        or line.startswith(('W ords', '注：', '；白体', '白体', '汇；白体'))):
                        continue
                    if re.fullmatch(r'(Module \d+|Revision module [AB])', line):
                        assert not pending, (page_number, pending, line)
                        module = line
                        continue
                    if not pending:
                        start_page = page_number
                    pending += ' ' + line
                    reference = re.search(r'\((S?\d+)\)$', pending)
                    if not reference:
                        continue
                    printed = reference.group(1)
                    raw = pending[:reference.start()].strip().lstrip('* ')
                    pending = ''
                    body_page = int(printed.lstrip('S')) + (5 if printed.startswith('S') else book['bodyOffset'])
                    unit_matches = re.findall(r'\bUnit\s+([123])\b', text[body_page - 1])
                    if module.startswith('Revision'):
                        assert any('Revision' in t for t in text[max(0, body_page - 6):body_page]), (body_page, module)
                        unit = module
                    else:
                        assert len(set(unit_matches)) == 1, (body_page, module, unit_matches)
                        unit = ('Starter · ' if printed.startswith('S') else '') + module + ' · Unit ' + unit_matches[0]
                    # Visually verified shared reference on eight-upper PDF p147.
                    raws = re.split(r' (?=side by side 并排地)', raw) if book['grade'] == 8 and book['volume'] == '上册' else [raw]
                    for item in raws:
                        head, meaning, phonetic, phonetic_source = split_entry(item, book['id'] == 'fltrp-legacy-02', phones)
                        entry = {'ordinal': len(entries) + 1, 'word': head, 'meaning': meaning,
                                 'phonetic': phonetic, 'unit': unit, 'sourcePage': printed,
                                 'sourcePdfPage': start_page, 'unitEvidencePdfPage': body_page}
                        if phonetic_source:
                            entry['phoneticSource'] = phonetic_source
                        entries.append(entry)
    assert not pending, pending
    assert len(entries) == EXPECTED[book['grade']][book['volume']], (book['id'], len(entries))
    return entries


def build(pdf_dir):
    metadata, phones = read_json(SOURCES), dictionary_phones()
    catalog = {'schema': 1, 'books': []}
    for source in metadata['books']:
        entries = extract(source, pdf_dir / (source['id'] + '.pdf'), metadata['transcribedPages'].get(source['id'], {}), phones)
        book_id = source['bookId']
        write_json(OUT / 'books' / (book_id + '.json'), {'id': book_id, 'entries': entries})
        notes = ['陈琳／Simon Greenall主编；前言明确依据2011年版课标修订。所据PDF未列版次及印次，不能推定为2022课标孙有新主编新版。',
                 '完整收录Words and expressions，按其首次出现页码定位正文Unit；Starter与Revision独立标识。未额外混入Proper names或字母序Vocabulary复本。',
                 '各Unit仅收录教材词表在该Unit首次出现的词；复习课没有新增词时不虚构空单元或重复分配。',
                 'sourcePdfPage为1起算词表PDF页；sourcePage为教材印刷页；unitEvidencePdfPage为核对Unit的正文PDF页（Revision延续页追溯本模块标题）。']
        if source['id'] == 'fltrp-legacy-01':
            notes.append('PDF122页（印刷89页）无文本层，45条词汇经渲染逐项人工转录。')
        if source['id'] == 'fltrp-legacy-02':
            notes.append('七下PDF音标字体提取会丢字，音标与仓库kajweb/ECDICT交叉核对；未找到可靠音标时留空。词形、释义、单元仍以PDF为准。')
        if source['grade'] == 8 and source['volume'] == '上册':
            notes.append('PDF147页side及side by side共用印刷页码64，已分别收录并核对正文64页。')
        catalog['books'].append({'id': book_id, 'title': f'外研版英语·{source["grade"]}年级{source["volume"]}（陈琳·2011课标）',
            'publisherId': 'fltrp', 'publisher': '外语教学与研究出版社', 'edition': '2011课标修订版·陈琳／Simon Greenall',
            'grade': source['grade'], 'volume': source['volume'], 'units': list(dict.fromkeys(e['unit'] for e in entries)),
            'count': len(entries), 'source': source['url'],
            'replaces': [f'WaiYanSheChuZhong_{(source["grade"] - 7) * 2 + (1 if source["volume"] == "上册" else 2)}'],
            'verification': {'status': 'pdf-reviewed',
            'evidence': [{'url': source['url'], 'path': source['path'], 'pages': source['wordListPages'], 'sha256': source['sha256']}],
            'notes': ' '.join(notes)}, 'url': 'books/' + book_id + '.json'})
    write_json(OUT / 'catalog-middle.json', catalog)


def check():
    catalog = read_json(OUT / 'catalog-middle.json')
    assert len(catalog['books']) == 6
    for book in catalog['books']:
        data = read_json(OUT / book['url'])
        assert data['id'] == book['id']
        assert len(data['entries']) == book['count'] == EXPECTED[book['grade']][book['volume']]
        assert book['units'] == list(dict.fromkeys(e['unit'] for e in data['entries']))
        evidence = book['verification']['evidence'][0]
        assert re.fullmatch('[a-f0-9]{64}', evidence['sha256']) and evidence['url'].startswith('https://') and evidence['pages']
        for i, entry in enumerate(data['entries'], 1):
            assert entry['ordinal'] == i and entry['word'].strip() and re.search('[A-Za-z]', entry['word'])
            assert re.search('[\u3400-\u9fff]', entry['meaning']) and entry['unit'] in book['units']
            assert re.fullmatch(r'S?\d+', entry['sourcePage']) and entry['sourcePdfPage'] in evidence['pages']
            assert entry['unitEvidencePdfPage'] > 0
            assert not re.search(r'[\ue000-\uf8ff0-9!#%=^*]', entry['phonetic']), entry
        print(f'{book["id"]}: {book["count"]} entries, {len(book["units"])} units, source/page/phonetic checks passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-dir', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        parser.error('--pdf-dir is required to rebuild') if not args.pdf_dir else build(args.pdf_dir)
    check()
