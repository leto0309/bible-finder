"""Create a portable release ZIP without personal profiles or build caches."""
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = ROOT / "dist/bible-finder.exe"
    if not executable.is_file():
        raise FileNotFoundError("Run scripts/package.ps1 first")
    output = ROOT / "dist/BibleFinder-1.0.1-windows-x64.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(executable, "BibleFinder/bible-finder.exe")
        for relative in ["README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "docs/data-sources.md", "docs/verification.md", "docs/images/app.png"]:
            archive.write(ROOT / relative, "BibleFinder/" + relative)
        for path in sorted((ROOT / "licenses").glob("*")):
            archive.write(path, "BibleFinder/licenses/" + path.name)
        archive.write(ROOT / "src/appcore/data/sources.json", "BibleFinder/data-sources.json")
    hashes = ROOT / "dist/SHA256SUMS.txt"
    hashes.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (output, executable)), encoding="utf-8")
    shutil.copyfile(ROOT / "docs/release-notes.md", ROOT / "dist/RELEASE-NOTES.md")
    print(f"{output.name}: {output.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
