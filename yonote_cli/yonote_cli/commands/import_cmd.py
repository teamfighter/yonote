"""Import Markdown files into Yonote."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Optional

from ..core import (
    get_base_and_token,
    http_json,
    interactive_pick_destination,
    ensure_text,
    tqdm,
)


def _iter_md_files(path: Path) -> List[Path]:
    return [p for p in path.rglob("*.md") if p.is_file()]


def cmd_import(args):
    base, token = get_base_and_token()
    src_dir = Path(args.src_dir).resolve()
    files = _iter_md_files(src_dir)
    if not files:
        print("Нет файлов *.md для импорта")
        return

    while True:
        coll_id, parent_id, label = interactive_pick_destination(
            base,
            token,
            workers=args.workers,
            refresh_cache=args.refresh_cache,
        )
        from InquirerPy import inquirer  # local import to avoid hard dep

        msg = f"Импортировать {len(files)} документов в раздел \"{label}\"?"
        if _execute(inquirer.confirm(message=msg, default=True)):
            break

    errors: List[Tuple[str, str]] = []

    def _create_doc(title: str, text: str, parent: Optional[str]) -> Optional[str]:
        payload = {
            "title": title,
            "text": text,
            "collectionId": coll_id,
            "publish": True,
        }
        if parent:
            payload["parentDocumentId"] = parent
        try:
            resp = http_json("POST", f"{base}/documents.create", token, payload)
            if isinstance(resp, dict):
                data = resp.get("data")
                if isinstance(data, dict):
                    return data.get("id")
            return None
        except Exception as e:
            errors.append((title, ensure_text(str(e))))
            return None

    def _import_dir(path: Path, parent: Optional[str]):
        for entry in sorted(path.iterdir()):
            if entry.is_dir():
                doc_id = _create_doc(entry.name, "", parent)
                if doc_id:
                    _import_dir(entry, doc_id)
            elif entry.is_file() and entry.suffix.lower() == ".md":
                try:
                    content = entry.read_text(encoding="utf-8")
                except Exception as e:
                    errors.append((str(entry), ensure_text(str(e))))
                    bar.update(1)
                    continue
                _create_doc(entry.stem, content, parent)
                bar.update(1)

    with tqdm(total=len(files), unit="doc", desc="Importing") as bar:
        _import_dir(src_dir, parent_id)

    print(f"Imported {len(files)-len(errors)}/{len(files)} documents from {src_dir}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for name, err in errors[:10]:
            print(f"  {name}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")


def _execute(prompt):
    try:
        return prompt.execute()
    except KeyboardInterrupt:
        print("\nОтменено пользователем")
        raise SystemExit(1)

