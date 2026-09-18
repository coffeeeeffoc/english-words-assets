"""Read two downloaded PDFs by columns; emit drafts for review, never publish them as verified.

Run using the bundled Python (pdfplumber is required). Source PDFs are unchanged.
"""
import csv
import json
from pathlib import Path
import re
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = '8096f798-4e9e-7d9e-2494-2aab025ce254'
MIDDLE = 'f7a7eb5e-12dc-4c96-a4b8-219ca3bcee19'


def main():
    manifest = json.loads((ROOT / 'metadata/manifest.json').read_text(encoding='utf-8'))
    report = []
    for book_id, start, end in [(PRIMARY, 73, 76), (MIDDLE, 106, 114)]:
        row = next(r for r in manifest if r['book_id'] == book_id and r['kind'] == 'textbook')
        target = ROOT / 'pdf-extraction' / book_id
        columns = []
        with pdfplumber.open(ROOT / row['path']) as doc:
            for page_number in range(start, end+1):
                page = doc.pages[page_number-1]
                for side in range(2):
                    x0, y0, _, _ = page.bbox
                    box = (x0+page.width*side/2, y0+page.height*.1,
                           x0+page.width*(side+1)/2, y0+page.height*.93)
                    text = page.crop(box).extract_text(x_tolerance=1, y_tolerance=3) or ''
                    columns.append({'page': page_number, 'column': side+1, 'text': text})
                # Retain page renders so every draft entry can be checked against its source.
                page.to_image(resolution=100).save(target / f'page-{page_number}.png')
        (target / 'columns.json').write_text(json.dumps(columns, ensure_ascii=False, indent=2), encoding='utf-8')
        entries, rejected = [], []
        unit = None
        if book_id == PRIMARY:
            for column in columns:
                for line in column['text'].splitlines():
                    if m := re.fullmatch(r'Unit\s+(\d+)', line.strip()):
                        unit = 'Unit '+m[1]
                        continue
                    if line.strip().startswith('附：'):
                        unit = '附录'
                        continue
                    match = re.match(r"^([A-Za-z][A-Za-z .’'*=\-]*?)\s+([\u4e00-\u9fff（…].*)$", line)
                    if match:
                        word = match[1].rstrip('*').strip()
                        entries.append({'word': word, 'meaning': match[2].strip(), 'unit': unit,
                                        'pdf_page': column['page'], 'column': column['column'],
                                        'extended': '*' in match[1], 'status': 'needs_review'})
                    elif entries and re.match(r'^[\u4e00-\u9fff]', line) and not line.startswith('词汇表'):
                        entries[-1]['meaning'] += line.strip()
                    elif line.strip():
                        rejected.append({'page': column['page'], 'column': column['column'], 'text': line})
            with (target / 'draft-wordlist.csv').open('w', encoding='utf-8-sig', newline='') as out:
                writer = csv.DictWriter(out, fieldnames=['word','meaning','unit','pdf_page','column','extended','status'])
                writer.writeheader(); writer.writerows(entries)
        report.append({'book_id': book_id, 'title': row['title'], 'source_pdf': row['path'],
                       'pdf_sha256': row.get('sha256'), 'pages': [start,end],
                       'text_layer': True, 'ocr_required_for_sample': False,
                       'draft_entries': len(entries), 'status': 'needs_review',
                       'notes': 'Column crops restore reading order; draft requires line-by-line verification. Not included in verified coverage.',
                       'unparsed_lines': rejected})
    (ROOT / 'reports/pdf-probe.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print([(r['book_id'],r['draft_entries']) for r in report])


if __name__ == '__main__':
    main()
