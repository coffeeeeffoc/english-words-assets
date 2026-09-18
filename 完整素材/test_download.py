"""Run with .venv/Scripts/python.exe test_download.py (no network requests)."""
import tempfile
from pathlib import Path
import download as d


def book(stage, subject):
    return {"tag_list": [{"tag_dimension_id": "zxxxd", "tag_name": stage},
                         {"tag_dimension_id": "zxxxk", "tag_name": subject}]}


assert d.selected(book("小学", "英语"))
assert d.selected(book("初中（五•四学制）", "英语"))
assert not d.selected(book("高中", "英语"))
assert not d.selected(book("小学", "语文"))
assert d.source_item({"ti_items": [{"ti_format": "folder", "ti_is_source_file": True}]}) is None
mp3 = {"ti_format": "mp3", "ti_file_flag": "href"}
assert d.source_item({"ti_items": [mp3]}, audio=True) == mp3
with tempfile.TemporaryDirectory() as directory:
    d.ROOT = Path(directory)
    path = d.ROOT / "sample.pdf"
    path.write_bytes(b"%PDF-test")
    row = {"path": path.name, "size": path.stat().st_size, "md5": d.digest(path, "md5")}
    assert d.valid(row)
    path.write_bytes(b"%PDF-fail")
    assert not d.valid(row), "Same-size corruption must be detected"
print("Self-check passed")
