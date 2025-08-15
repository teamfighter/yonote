"""Interactive helpers using InquirerPy."""

from __future__ import annotations

from typing import Dict, List, Optional
import sys

try:
    from InquirerPy import inquirer
    HAVE_INQUIRER = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_INQUIRER = False


def _build_breadcrumbs(doc: dict, by_id: Dict[str, dict]) -> str:
    parts = [doc.get("title") or "(untitled)"]
    seen = set()
    cur = doc
    while True:
        pid = cur.get("parentDocumentId")
        if not pid or pid in seen:
            break
        seen.add(pid)
        p = by_id.get(pid)
        if not p:
            break
        parts.insert(0, p.get("title") or "(untitled)")
        cur = p
    return " / ".join(parts)


def interactive_select_documents(docs: List[dict], multiselect: bool = True) -> List[str]:
    if not HAVE_INQUIRER:
        print("Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy", file=sys.stderr)
        sys.exit(2)
    by_id = {d.get("id"): d for d in docs}
    choices = []
    for d in docs:
        bc = _build_breadcrumbs(d, by_id)
        label = f"{bc}  [{d.get('id')}]"
        choices.append({"name": label, "value": d.get("id")})
    choices.sort(key=lambda x: x["name"].lower())
    if multiselect:
        result = inquirer.checkbox(
            message="Выберите документы (Space — выбрать, Enter — подтвердить):",
            choices=choices,
            instruction="↑/↓, PgUp/PgDn, Search: /",
            transformer=lambda res: f"{len(res)} selected",
            height="90%",
            validate=lambda ans: (len(ans) > 0) or "Нужно выбрать хотя бы один документ",
        ).execute()
        return list(result or [])
    else:
        result = inquirer.select(
            message="Выберите документ:",
            choices=choices,
            instruction="↑/↓, Search: /",
            height="90%",
        ).execute()
        return [result] if result else []


def interactive_pick_parent(docs: List[dict], allow_none: bool = True) -> Optional[str]:
    if not HAVE_INQUIRER:
        print("Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy", file=sys.stderr)
        sys.exit(2)
    by_id = {d.get("id"): d for d in docs}
    choices = []
    if allow_none:
        choices.append({"name": "(no parent) — в корень коллекции", "value": None})
    for d in docs:
        bc = _build_breadcrumbs(d, by_id)
        label = f"{bc}  [{d.get('id')}]"
        choices.append({"name": label, "value": d.get("id")})
    choices.sort(key=lambda x: (x["name"] or "").lower())
    parent = inquirer.select(
        message="Куда импортировать (родительский документ)?",
        choices=choices,
        instruction="↑/↓, Search: /",
        height="90%",
    ).execute()
    return parent
