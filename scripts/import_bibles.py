"""Build the bundled DB from GetBible v2 snapshots; never runs at app runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from appcore.engine import normalize_keyword  # noqa: E402


def build(source: Path, output: Path):
    catalog = json.loads((source / "translations.json").read_text(encoding="utf-8-sig"))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    manifest = {"provider": "GetBible v2 / CrossWire SWORD", "retrieved": "2026-10-21", "translations": {}}
    connection = sqlite3.connect(output)
    try:
        connection.execute("CREATE TABLE verses (version TEXT NOT NULL, book INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, text TEXT NOT NULL, search_text TEXT NOT NULL, PRIMARY KEY(version,book,chapter,verse)) WITHOUT ROWID")
        for version in ("cus", "cut", "web"):
            raw = (source / f"{version}.json").read_bytes()
            data = json.loads(raw)
            metadata = catalog[version]
            if metadata["distribution_license"] != "Public Domain":
                raise ValueError("Unexpected license; review before redistributing")
            if data["abbreviation"] != version or len(data["books"]) != 66:
                raise ValueError("Wrong or incomplete translation")
            rows, counts, empty = [], {}, []
            for book in data["books"]:
                number = int(book["nr"])
                chapters = book["chapters"]
                if [c["chapter"] for c in chapters] != list(range(1, len(chapters) + 1)):
                    raise ValueError("Non-contiguous chapters")
                counts[str(number)] = len(chapters)
                for chapter in chapters:
                    for verse in chapter["verses"]:
                        text = verse["text"].strip().lstrip("\ufeff")
                        text = "".join(text.split()) if version != "web" else " ".join(text.split())
                        if not text:
                            empty.append(f"{number}:{chapter['chapter']}:{verse['verse']}")
                        if verse["chapter"] != chapter["chapter"]:
                            raise ValueError("Chapter mismatch")
                        rows.append((version, number, chapter["chapter"], verse["verse"], text, normalize_keyword(text, version)))
            if set(counts) != {str(n) for n in range(1, 67)} or len(rows) < 30000:
                raise ValueError("Incomplete Bible data")
            connection.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?)", rows)
            manifest["translations"][version] = {"metadata": metadata, "sha256": hashlib.sha256(raw).hexdigest(), "verse_count": len(rows), "chapter_count": sum(counts.values()), "book_chapters": counts, "empty_verses": empty}
            print(f"{version}: {len(rows)} verses, {sum(counts.values())} chapters, {len(empty)} empty verses")
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database integrity check failed")
        connection.execute("VACUUM")
    finally:
        connection.close()
    manifest["database_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.parent / "sources.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / "work/sources")
    parser.add_argument("--output", type=Path, default=ROOT / "src/appcore/data/bible.sqlite3")
    args = parser.parse_args()
    build(args.source, args.output)
