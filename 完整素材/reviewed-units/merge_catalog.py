"""Merge reviewed edition catalogs; validate every book before publishing the index."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
books = []
for path in sorted(root.glob('catalog-*.json')):
    books.extend(json.loads(path.read_text(encoding='utf-8'))['books'])
assert books and len({book['id'] for book in books}) == len(books)
for book in books:
    assert book['url'] == f"books/{book['id']}.json"
    data = json.loads((root / book['url']).read_text(encoding='utf-8'))
    assert data['id'] == book['id'] and len(data['entries']) == book['count']
    assert list(dict.fromkeys(entry['unit'] for entry in data['entries'])) == book['units']
    assert book['verification']['status'] == 'pdf-reviewed' and book['verification']['evidence']
books.sort(key=lambda book: (book['grade'], not book['id'].startswith('fltrp-sun-'), book['volume'] != '上册', book['id']))
(root / 'catalog.json').write_text(json.dumps(dict(schema=1, books=books), ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(f"Reviewed catalog: {len(books)} books, {sum(book['count'] for book in books)} entries, {sum(len(book['units']) for book in books)} units")
