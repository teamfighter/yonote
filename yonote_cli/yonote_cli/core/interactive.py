"""Interactive helpers using InquirerPy."""

from __future__ import annotations

from typing import Dict, List, Optional
import sys

from .cache import list_collections, list_documents_in_collection

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


def interactive_browse_for_export(
    base: str,
    token: str,
    *,
    workers: int,
    refresh_cache: bool,
) -> tuple[List[str], List[str]]:
    """Return lists of selected document IDs and collection IDs."""
    if not HAVE_INQUIRER:
        print(
            "Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy",
            file=sys.stderr,
        )
        sys.exit(2)

    collections = list_collections(
        base, token, use_cache=True, refresh_cache=refresh_cache, workers=workers
    )
    cols_by_id = {c.get("id"): c for c in collections}
    selected_docs: set[str] = set()
    selected_cols: set[str] = set()

    def browse_collection(coll: dict) -> Optional[str]:
        coll_id = coll.get("id")
        docs = list_documents_in_collection(
            base,
            token,
            coll_id,
            use_cache=True,
            refresh_cache=refresh_cache,
            workers=workers,
        )
        children: Dict[Optional[str], List[dict]] = {}
        for d in docs:
            children.setdefault(d.get("parentDocumentId"), []).append(d)

        def browse(parent_id: Optional[str], path: str, current: Optional[dict]) -> Optional[str]:
            while True:
                choices: List[dict] = []
                if parent_id is not None:
                    choices.append({"name": "..", "value": "__up"})
                if current is None:
                    mark = "[x]" if coll_id in selected_cols else "[ ]"
                    choices.append(
                        {
                            "name": f"{mark} Экспортировать всю коллекцию",
                            "value": "__toggle_coll",
                        }
                    )
                else:
                    mark = "[x]" if current.get("id") in selected_docs else "[ ]"
                    choices.append(
                        {
                            "name": f"{mark} Экспортировать этот документ",
                            "value": "__toggle_doc",
                        }
                    )
                for d in children.get(parent_id, []):
                    did = d.get("id")
                    has_children = did in children
                    mark = "[x]" if did in selected_docs else "[ ]"
                    title = d.get("title") or "(без названия)"
                    suffix = "/" if has_children else ""
                    choices.append(
                        {
                            "name": f"{mark} {title}{suffix}",
                            "value": ("doc", d),
                        }
                    )
                choices.append({"name": "<Готово>", "value": "__done"})
                choice = inquirer.select(
                    message=path,
                    choices=choices,
                    instruction="↑/↓, PgUp/PgDn, Enter",
                    height="90%",
                ).execute()
                if choice == "__up":
                    return None
                if choice == "__done":
                    return "done"
                if choice == "__toggle_coll":
                    if coll_id in selected_cols:
                        selected_cols.remove(coll_id)
                    else:
                        selected_cols.add(coll_id)
                    continue
                if choice == "__toggle_doc" and current is not None:
                    did = current.get("id")
                    if did in selected_docs:
                        selected_docs.remove(did)
                    else:
                        selected_docs.add(did)
                    continue
                typ, doc = choice
                title = doc.get("title") or "(без названия)"
                did = doc.get("id")
                if did in children:
                    res = browse(did, f"{path}/{title}", doc)
                    if res == "done":
                        return "done"
                else:
                    if did in selected_docs:
                        selected_docs.remove(did)
                    else:
                        selected_docs.add(did)

        return browse(None, coll.get("name") or "(без названия)", None)

    while True:
        choices = [
            {
                "name": f"{'[x]' if c.get('id') in selected_cols else '[ ]'} {c.get('name') or '(без названия)'}",
                "value": ("col", c),
            }
            for c in collections
        ]
        choices.append({"name": "<Экспортировать выбранное>", "value": "__done"})
        choice = inquirer.select(
            message="Коллекции",
            choices=choices,
            instruction="↑/↓, PgUp/PgDn, Enter",
            height="90%",
        ).execute()
        if choice == "__done":
            break
        typ, coll = choice
        res = browse_collection(coll)
        if res == "done":
            break

    return list(selected_docs), list(selected_cols)
