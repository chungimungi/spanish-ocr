"""
One-time rename: manifest order -> doc1, doc2, ...
- data/<name>.pdf -> data/docN.pdf
- ground-truth/<gt_file> -> ground-truth/docN_transcription.<ext>
- outputs/<name>/ and liquid-lm/<name>/ -> docN/

Run from repo root: python rename_corpus_to_doc_ids.py
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "outputs" / "manifest.json"
DATA = ROOT / "data"
GT = ROOT / "ground-truth"
OUT_DIRS = [ROOT / "outputs", ROOT / "liquid-lm"]


def normalize_doc_stem(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.lower()
    s = s.replace("&#x3a;", ":").replace("&#x3a", ":")
    s = re.sub(r":+", ".", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_gt_for_manifest_name(manifest_name: str) -> Path | None:
    mn = normalize_doc_stem(manifest_name)
    if not GT.exists():
        return None
    suf = "_transcription"
    for p in GT.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".txt", ".md", ".text", ".docx"}:
            continue
        stem = p.stem
        base = stem[: -len(suf)] if stem.lower().endswith(suf) else stem
        if normalize_doc_stem(base) == mn:
            return p
    return None


def replace_name_in_files(root: Path, old_name: str, new_name: str) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".txt", ".csv"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if old_name not in text:
            continue
        path.write_text(text.replace(old_name, new_name), encoding="utf-8")


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"Missing {MANIFEST}")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mapping: list[dict] = []

    for i, item in enumerate(manifest):
        old_name = item["name"]
        new_name = f"doc{i + 1}"
        mapping.append({"doc_id": new_name, "old_name": old_name})

        pdf_old = DATA / f"{old_name}.pdf"
        pdf_new = DATA / f"{new_name}.pdf"
        if pdf_old.exists() and pdf_old.resolve() != pdf_new.resolve():
            pdf_new.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_old), str(pdf_new))
            print(f"PDF: {pdf_old.name} -> {pdf_new.name}")

        gt = find_gt_for_manifest_name(old_name)
        if gt and gt.exists():
            ext = gt.suffix
            gt_new = GT / f"{new_name}_transcription{ext}"
            if gt.resolve() != gt_new.resolve():
                shutil.move(str(gt), str(gt_new))
                print(f"GT:  {gt.name} -> {gt_new.name}")
        elif GT.exists():
            print(f"WARN: no ground-truth file matched for manifest name: {old_name!r}")

        for base in OUT_DIRS:
            old_dir = base / old_name
            new_dir = base / new_name
            if old_dir.is_dir() and old_dir.resolve() != new_dir.resolve():
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                if new_dir.exists():
                    shutil.rmtree(new_dir)
                shutil.move(str(old_dir), str(new_dir))
                print(f"DIR: {old_dir} -> {new_dir}")
                replace_name_in_files(new_dir, old_name, new_name)

        for base in OUT_DIRS:
            replace_name_in_files(base, old_name, new_name)

    for i, item in enumerate(manifest):
        new_name = f"doc{i + 1}"
        old_name = item["name"]
        item["name"] = new_name
        item["pdf_path"] = str((DATA / f"{new_name}.pdf").resolve())
        item["work_dir"] = str((ROOT / "outputs" / new_name).resolve())
        for page in item.get("pages") or []:
            if "image_path" in page:
                page["image_path"] = page["image_path"].replace(old_name, new_name)
            for k in ("band_paths",):
                if k in page and isinstance(page[k], list):
                    page[k] = [x.replace(old_name, new_name) for x in page[k]]

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {MANIFEST}")

    lm = ROOT / "liquid-lm" / "manifest.json"
    if lm.exists():
        lm.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Updated {lm}")

    (ROOT / "document_id_map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote document_id_map.json ({len(mapping)} docs)")


if __name__ == "__main__":
    main()
