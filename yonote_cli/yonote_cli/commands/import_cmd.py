"""Import Markdown files into Yonote."""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ..core import (
    get_base_and_token,
    http_multipart_post,
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
    with tqdm(total=len(files), unit="doc", desc="Importing") as bar:
        for path in files:
            try:
                content = path.read_bytes()
                fields = {
                    "file": (path.name, content, "text/markdown"),
                    "collectionId": coll_id,
                }
                if parent_id:
                    fields["parentDocumentId"] = parent_id
                http_multipart_post(f"{base}/documents.import", token, fields)
            except Exception as e:
                errors.append((str(path), ensure_text(str(e))))
            bar.update(1)

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

