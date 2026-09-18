"""Download the current SmartEdu primary/middle-school English textbook catalog.

Uses tchMaterial-parser's network/authentication and filename handling.
Run with .venv/Scripts/python.exe download.py [--catalog-only | --check].
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

from tchmaterial_parser import config
from tchmaterial_parser.api import get_relative_dir
from tchmaterial_parser.network import session
from tchmaterial_parser.ui.download_panel import (
    download_failure_reason, request_download, sanitize_filename,
)

ROOT = Path(__file__).resolve().parent
META = ROOT / "metadata"
BASE = "https://s-file-1.ykt.cbern.com.cn/zxx"
sys.stdout.reconfigure(encoding="utf-8")


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def fetch(url, path, refresh=False, optional=False):
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(3):
        try:
            with session.get(url) as response:
                if optional and response.status_code == 404:
                    data = []
                else:
                    response.raise_for_status()
                    data = json.loads(response.content)
            save(path, data)
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def selected(book):
    tags = {t["tag_dimension_id"]: t["tag_name"] for t in book.get("tag_list", [])}
    return tags.get("zxxxd", "").startswith(("小学", "初中")) and tags.get("zxxxk") == "英语"


def source_item(data, audio=False):
    items = data.get("ti_items", [])
    if audio:
        mp3 = [i for i in items if i.get("ti_format") == "mp3" and i.get("ti_file_flag") in ("href", "source")]
        if mp3:
            return mp3[0]
    return next((i for i in items if i.get("ti_format") != "folder" and
                 (i.get("ti_is_source_file") or i.get("ti_file_flag") == "source")), None)


def resources(book):
    bid = book["id"]
    detail = fetch(f"{BASE}/ndrv2/resources/tch_material/details/{bid}.json", META / "details" / f"{bid}.json")
    audios = fetch(f"{BASE}/ndrs/resources/{bid}/relation_audios.json", META / "audios" / f"{bid}.json", optional=True)
    if not isinstance(audios, list):
        raise ValueError(f"Unexpected audio catalog: {bid}")
    directory = Path("materials", *(sanitize_filename(s) for s in get_relative_dir(book)),
                     sanitize_filename(book["title"])[:85] + "__" + bid[:8])
    result = []
    for index, data in enumerate([detail, *audios]):
        item = source_item(data, audio=index > 0)
        if not item:
            raise ValueError(f"No source file: {bid}, resource {data.get('id')}")
        title = data.get("global_title") or data.get("title") or data["id"]
        if isinstance(title, dict):
            title = title.get("zh-CN") or title.get("en") or data["id"]
        url = item.get("ti_storage", "").replace("cs_path:${ref-path}", "https://r1-ndr-private.ykt.cbern.com.cn")
        url = url or next(u for u in item.get("ti_storages", []) if u)
        ext = item["ti_format"].lower()
        name = f"{index:03d}_{sanitize_filename(title)[:85]}.{ext}" if index else f"教材.{ext}"
        result.append(dict(book_id=bid, resource_id=data["id"], title=title,
                           stage=get_relative_dir(book)[0], edition=get_relative_dir(book)[-1],
                           kind="audio" if index else "textbook", format=ext, url=url,
                           page_url=f"https://basic.smartedu.cn/tchMaterial/detail?contentType=assets_document&contentId={bid}",
                           path=(directory / name).as_posix(), size=item.get("ti_size", 0),
                           md5=item.get("ti_md5", ""), status="pending"))
    return result


def digest(path, algorithm):
    value = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def valid(row):
    path = ROOT / row["path"]
    if not path.is_file() or not path.stat().st_size:
        return False
    if row.get("size") and path.stat().st_size != row["size"]:
        return False
    expected = row.get("md5") or row.get("sha256")
    return bool(expected) and digest(path, "md5" if row.get("md5") else "sha256") == expected


def download(row):
    try:
        if valid(row):
            return {**row, "status": "complete", "error": None}
        path = ROOT / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".part")
        for attempt in range(3):
            try:
                if shutil.disk_usage(ROOT).free < max(row.get("size", 0), 0) + 512 * 1024 ** 2:
                    raise OSError("Insufficient disk space; keep 512 MiB free")
                response, urls = request_download(row["url"])
                with response:
                    if not response.ok:
                        raise RuntimeError(download_failure_reason(response, urls))
                    size = int(response.headers.get("Content-Length", 0))
                    with temp.open("wb") as output:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                actual = temp.stat().st_size
                if not actual or (size and actual != size) or (row.get("size") and actual != row["size"]):
                    raise ValueError("File size mismatch")
                if row.get("md5") and digest(temp, "md5") != row["md5"]:
                    raise ValueError("MD5 mismatch")
                if row["format"] == "pdf":
                    with temp.open("rb") as stream:
                        if stream.read(5) != b"%PDF-":
                            raise ValueError("Invalid PDF header")
                sha256 = digest(temp, "sha256")
                temp.replace(path)
                return {**row, "size": actual, "sha256": sha256, "status": "complete", "error": None}
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
    except Exception as error:
        return {**row, "status": "failed", "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    config.load_access_token(config.load_config())
    manifest = META / "manifest.json"
    if not manifest.exists():
        version = fetch(f"{BASE}/ndrs/resources/tch_material/version/data_version.json", META / "version.json", refresh=True)
        books = []
        for index, url in enumerate(version["urls"].split(",")):
            books.extend(fetch(url, META / f"part_{index}.json", refresh=True))
        books = list({b["id"]: b for b in books if selected(b)}.values())
        save(META / "books.json", books)
        rows, errors = [], []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(resources, b): b for b in books}
            for count, future in enumerate(as_completed(futures), 1):
                try:
                    rows.extend(future.result())
                except Exception as error:
                    errors.append({"book_id": futures[future]["id"], "error": str(error)})
                if count % 25 == 0 or count == len(books):
                    print(f"Catalog {count}/{len(books)}; files={len(rows)}, errors={len(errors)}", flush=True)
        save(META / "catalog-errors.json", errors)
        rows.sort(key=lambda r: r["path"])
        if errors:
            save(META / "partial-manifest.json", rows)
            raise SystemExit("Catalog incomplete; rerun to retry using cached metadata")
        assert len({r["path"].casefold() for r in rows}) == len(rows), "Duplicate paths"
        assert sum(r["kind"] == "textbook" for r in rows) == len(books)
        save(manifest, rows)
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    print(f"Files: {dict(Counter(r['kind'] for r in rows))}; total {sum(r['size'] for r in rows)/1024**3:.2f} GiB", flush=True)
    if args.catalog_only:
        return
    if args.check:
        failures = [r["path"] for r in rows if not valid(r)]
        save(META / "verification.json", {"total": len(rows), "valid": len(rows)-len(failures), "failures": failures})
        print(f"Verified {len(rows)-len(failures)}/{len(rows)}")
        raise SystemExit(bool(failures))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(download, r): index for index, r in enumerate(rows)}
        for count, future in enumerate(as_completed(futures), 1):
            result = future.result()
            rows[futures[future]] = result
            save(manifest, rows)
            print(f"{count}/{len(rows)} {result['status']}: {result['path']} {result.get('error') or ''}", flush=True)
    counts = Counter(r["status"] for r in rows)
    print(dict(counts))
    raise SystemExit(bool(counts.get("failed")))


if __name__ == "__main__":
    main()
