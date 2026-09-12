from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

from .validate_daisy import validate_daisy


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate, ZIP and checksum a DAISY 3 book.")
    parser.add_argument("--input", default="build/daisy")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--name", default="Tam_ly_hoc_ve_tien_DAISY3")
    args = parser.parse_args()

    root = Path(args.input)
    errors, warnings = validate_daisy(root)
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("Refusing to package an invalid DAISY folder.")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{args.name}.zip"
    checksum_path = output_dir / f"{args.name}_sha256sums.txt"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            zf.write(path, path.relative_to(root))

    checksum = sha256(zip_path)
    checksum_path.write_text(f"{checksum}  {zip_path.name}\n", encoding="utf-8")
    print(f"Wrote {zip_path}")
    print(f"Wrote {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
