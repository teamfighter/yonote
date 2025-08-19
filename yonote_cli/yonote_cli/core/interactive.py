"""Interactive helpers using InquirerPy.

The functions below provide text based navigation for collections and
documents.  They are intentionally verbose and contain many inline comments
so that the behaviour is easy to follow and maintain.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import sys

from .cache import (
    list_collections,
    refresh_document_branch,
    load_cache,
)

try:
    from InquirerPy import inquirer
    from InquirerPy.prompts.list import ListPrompt
    HAVE_INQUIRER = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_INQUIRER = False


def _execute(prompt):
    """Execute a prompt and handle ``Ctrl-C`` gracefully."""
    try:
        return prompt.execute()
    except KeyboardInterrupt:
        print("\nОтменено пользователем", file=sys.stderr)
        sys.exit(1)


def _build_breadcrumbs(doc: dict, by_id: Dict[str, dict]) -> str:
    """Return a human readable path for ``doc`` using ``title`` fields."""

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
    """Interactively select documents and return their IDs.

    ``multiselect`` controls whether multiple documents can be chosen.
    ``InquirerPy`` is optional so we guard against it being missing.
    """

    if not HAVE_INQUIRER:
        print(
            "Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy",
            file=sys.stderr,
        )
        sys.exit(2)

    by_id = {d.get("id"): d for d in docs}
    choices = []
    for d in docs:
        bc = _build_breadcrumbs(d, by_id)
        label = f"{bc}  [{d.get('id')}]"
        choices.append({"name": label, "value": d.get("id")})
    choices.sort(key=lambda x: x["name"].lower())

    if multiselect:
        prompt = inquirer.checkbox(
            message="Выберите документы (Space — выбрать, Enter — подтвердить):",
            choices=choices,
            instruction="↑/↓, PgUp/PgDn, Space: выбрать, Ctrl+S поиск, Enter",
            transformer=lambda res: f"{len(res)} selected",
            height="90%",
            validate=lambda ans: (len(ans) > 0) or "Нужно выбрать хотя бы один документ",
            keybindings={
                "pageup": [{"key": "pageup"}],
                "pagedown": [{"key": "pagedown"}],
                "toggle": [{"key": "space"}],
                "search": [{"key": "c-s"}],
                "search-next": [{"key": "enter"}],
            },
        )
        result = _execute(prompt)
        return list(result or [])

    prompt = inquirer.select(
        message="Выберите документ:",
        choices=choices,
        instruction="↑/↓, Ctrl+S поиск, Enter",
        height="90%",
        keybindings={
            "search": [{"key": "c-s"}],
            "search-next": [{"key": "enter"}],
        },
    )
    result = _execute(prompt)
    return [result] if result else []


def interactive_pick_parent(docs: List[dict], allow_none: bool = True) -> Optional[str]:
    """Select a parent document from ``docs``.

    Used by non-interactive import mode where a simple list selection is
    sufficient.  ``allow_none`` adds an option to import into collection root.
    """

    if not HAVE_INQUIRER:
        print(
            "Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy",
            file=sys.stderr,
        )
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

    prompt = inquirer.select(
        message="Куда импортировать (родительский документ)?",
        choices=choices,
        instruction="↑/↓, Ctrl+S поиск, Enter",
        height="90%",
        keybindings={
            "search": [{"key": "c-s"}],
            "search-next": [{"key": "enter"}],
        },
    )
    parent = _execute(prompt)
    return parent


def interactive_browse_for_export(
    base: str,
    token: str,
    *,
    workers: int,
    refresh_cache: bool,
) -> tuple[List[str], List[str]]:
    """Return lists of selected document IDs and collection IDs.

    The user can browse collections and documents similar to a file manager
    and toggle items with the space bar.  Only the portions of the tree that
    are viewed are fetched from the API which keeps startup fast.
    """
    if not HAVE_INQUIRER:
        print(
            "Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy",
            file=sys.stderr,
        )
        sys.exit(2)
    print("Загрузка списка коллекций...", file=sys.stderr)
    collections = list_collections(
        base,
        token,
        use_cache=True,
        refresh_cache=refresh_cache,
        workers=workers,
        desc=None,
    )
    cols_by_id = {c.get("id"): c for c in collections}
    selected_docs: set[str] = set()
    selected_cols: set[str] = set()

    def browse_collection(coll: dict) -> Optional[str]:
        coll_id = coll.get("id")
        cache = load_cache()
        coll_key = f"collection:{coll_id}"
        docs = list(cache.get(coll_key, []))
        children: Dict[Optional[str], List[dict]] = {}
        for d in docs:
            children.setdefault(d.get("parentDocumentId"), []).append(d)

        def load_children(pid: Optional[str]) -> None:
            nonlocal docs, children
            docs = refresh_document_branch(
                base,
                token,
                coll_id,
                pid,
                workers=workers,
                desc=None,
            )
            children = {}
            for d in docs:
                children.setdefault(d.get("parentDocumentId"), []).append(d)

        if refresh_cache or not docs:
            load_children(None)

        def toggle_descendants(doc_id: str) -> None:
            stack = [doc_id]
            ids: set[str] = set()
            while stack:
                cur = stack.pop()
                ids.add(cur)
                for ch in children.get(cur, []):
                    stack.append(ch.get("id"))
            if doc_id in selected_docs:
                selected_docs.difference_update(ids)
            else:
                selected_docs.update(ids)

        def browse(parent_id: Optional[str], path: str, current: Optional[dict]) -> Optional[str]:
            search: Dict[str, Optional[object]] = {"query": None, "index": 0, "default": None}

            def build_choices() -> List[dict]:
                choices: List[dict] = [{"name": "..", "value": "__up"}]
                if current is None:
                    mark = "[x]" if coll_id in selected_cols else "[ ]"
                    choices.append(
                        {
                            "name": f"{mark} Экспортировать всю коллекцию",
                            "value": "__toggle_coll",
                        }
                    )
                # option for exporting the current document removed to avoid confusion
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
                return choices

            while True:
                choices = build_choices()
                default_val = search.pop("default", None)
                if search["query"]:
                    matches = [
                        c["value"]
                        for c in choices
                        if search["query"].lower() in c["name"].lower()
                    ]
                    if matches:
                        default_val = matches[search["index"] % len(matches)]
                prompt = ListPrompt(
                    message=path,
                    choices=choices,
                    default=default_val,
                    instruction="↑/↓, PgUp/PgDn, Space: выбрать, Ctrl+R обновить, Ctrl+S поиск, Enter",
                    height="90%",
                    keybindings={
                        "pageup": [{"key": "pageup"}],
                        "pagedown": [{"key": "pagedown"}],
                        "toggle-doc": [{"key": "space"}],
                        "refresh": [{"key": "c-r"}],
                        "search": [{"key": "c-s"}],
                    },
                )

                def _page(step: int) -> None:
                    cc = prompt.content_control
                    cc.selected_choice_index = max(
                        0,
                        min(cc.choice_count - 1, cc.selected_choice_index + step),
                    )

                def _page_up(event) -> None:
                    _page(-10)

                def _page_down(event) -> None:
                    _page(10)

                def _toggle_doc(event) -> None:
                    search["default"] = prompt.content_control.selection["value"]
                    val = prompt.content_control.selection["value"]
                    if isinstance(val, tuple) and val[0] == "doc":
                        did = val[1].get("id")
                        toggle_descendants(did)
                    event.app.exit(result="__refresh__")

                def _refresh(event) -> None:
                    nonlocal docs, children
                    search["default"] = prompt.content_control.selection["value"]
                    docs = refresh_document_branch(
                        base,
                        token,
                        coll_id,
                        parent_id,
                        workers=workers,
                        desc=None,
                    )
                    children = {}
                    for d in docs:
                        children.setdefault(d.get("parentDocumentId"), []).append(d)
                    event.app.exit(result="__refresh__")

                def _search(event) -> None:
                    search["default"] = prompt.content_control.selection["value"]
                    if search["query"]:
                        search["index"] += 1
                        event.app.exit(result="__refresh__")
                    else:
                        event.app.exit(result="__search__")

                prompt.kb_func_lookup.update(
                    {
                        "pageup": [{"func": _page_up}],
                        "pagedown": [{"func": _page_down}],
                        "toggle-doc": [{"func": _toggle_doc}],
                        "refresh": [{"func": _refresh}],
                        "search": [{"func": _search}],
                    }
                )

                choice = _execute(prompt)
                if choice == "__up":
                    return None
                if choice == "__done":
                    return "done"
                if choice == "__refresh__":
                    continue
                if choice == "__search__":
                    q = _execute(
                        inquirer.text(
                            message="Поиск:",
                            default=search["query"] or "",
                            keybindings={"answer": [{"key": "c-s"}]},
                        )
                    )
                    search["query"] = q or None
                    search["index"] = 0
                    continue
                if choice == "__toggle_coll":
                    if coll_id in selected_cols:
                        selected_cols.remove(coll_id)
                    else:
                        selected_cols.add(coll_id)
                    continue
                typ, doc = choice
                if typ == "doc":
                    title = doc.get("title") or "(без названия)"
                    did = doc.get("id")
                    load_children(did)
                    if did in children:
                        res = browse(did, f"{path}/{title}", doc)
                        if res == "done":
                            return "done"
                    else:
                        toggle_descendants(did)

        return browse(None, coll.get("name") or "(без названия)", None)

    search: Dict[str, Optional[object]] = {"query": None, "index": 0, "default": None}
    while True:
        choices = [
            {
                "name": f"{'[x]' if c.get('id') in selected_cols else '[ ]'} {c.get('name') or '(без названия)'}",
                "value": ("col", c),
            }
            for c in collections
        ]
        choices.append({"name": "<Экспортировать выбранное>", "value": "__done"})
        default_val = search.pop("default", None)
        if search["query"]:
            matches = [
                c["value"]
                for c in choices
                if search["query"].lower() in c["name"].lower()
            ]
            if matches:
                default_val = matches[search["index"] % len(matches)]
        prompt = ListPrompt(
            message="Коллекции",
            choices=choices,
            default=default_val,
            instruction="↑/↓, PgUp/PgDn, Ctrl+R обновить, Ctrl+S поиск, Enter",
            height="90%",
            keybindings={
                "pageup": [{"key": "pageup"}],
                "pagedown": [{"key": "pagedown"}],
                "refresh": [{"key": "c-r"}],
                "search": [{"key": "c-s"}],
            },
        )

        def _page(step: int) -> None:
            cc = prompt.content_control
            cc.selected_choice_index = max(
                0, min(cc.choice_count - 1, cc.selected_choice_index + step)
            )

        def _page_up(event) -> None:
            _page(-10)

        def _page_down(event) -> None:
            _page(10)

        def _refresh(event) -> None:
            nonlocal collections
            search["default"] = prompt.content_control.selection["value"]
            collections = list_collections(
                base,
                token,
                use_cache=True,
                refresh_cache=True,
                workers=workers,
                desc=None,
            )
            event.app.exit(result="__refresh__")

        def _search(event) -> None:
            search["default"] = prompt.content_control.selection["value"]
            if search["query"]:
                search["index"] += 1
                event.app.exit(result="__refresh__")
            else:
                event.app.exit(result="__search__")

        prompt.kb_func_lookup.update(
            {
                "pageup": [{"func": _page_up}],
                "pagedown": [{"func": _page_down}],
                "refresh": [{"func": _refresh}],
                "search": [{"func": _search}],
            }
        )

        choice = _execute(prompt)
        if choice == "__refresh__":
            continue
        if choice == "__search__":
            q = _execute(
                inquirer.text(
                    message="Поиск:",
                    default=search["query"] or "",
                    keybindings={"answer": [{"key": "c-s"}]},
                )
            )
            search["query"] = q or None
            search["index"] = 0
            continue
        if choice == "__done":
            break
        typ, coll = choice
        res = browse_collection(coll)
        if res == "done":
            break

    return list(selected_docs), list(selected_cols)


def interactive_pick_destination(
    base: str,
    token: str,
    *,
    workers: int,
    refresh_cache: bool,
) -> Tuple[str, Optional[str], str]:
    """Interactively pick collection and optional parent document for import."""

    if not HAVE_INQUIRER:
        print(
            "Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy",
            file=sys.stderr,
        )
        sys.exit(2)

    # Inform the user that API data is being fetched.  Without this the
    # terminal would appear frozen on slow connections.
    print("Загрузка списка коллекций...", file=sys.stderr)

    collections = list_collections(
        base,
        token,
        use_cache=True,
        refresh_cache=refresh_cache,
        workers=workers,
        desc=None,
    )

    def browse_collection(coll: dict) -> Tuple[str, Optional[str], str] | None:
        coll_id = coll.get("id")
        cache = load_cache()
        coll_key = f"collection:{coll_id}"
        docs = list(cache.get(coll_key, []))
        children: Dict[Optional[str], List[dict]] = {}
        for d in docs:
            children.setdefault(d.get("parentDocumentId"), []).append(d)

        def load_children(pid: Optional[str]) -> None:
            nonlocal docs, children
            docs = refresh_document_branch(
                base,
                token,
                coll_id,
                pid,
                workers=workers,
                desc=None,
            )
            children = {}
            for d in docs:
                children.setdefault(d.get("parentDocumentId"), []).append(d)

        if refresh_cache or not docs:
            load_children(None)

        selected: Optional[str] = None  # "__root" or document id
        selected_label: str = coll.get("name") or "(без названия)"
        def browse(parent_id: Optional[str], path: str, current: Optional[dict]) -> Tuple[str, Optional[str], str] | None:
            nonlocal selected, selected_label, docs, children
            search: Dict[str, Optional[object]] = {"query": None, "index": 0, "default": None}

            def build_choices() -> List[dict]:
                choices: List[dict] = [{"name": "..", "value": "__up"}]
                if current is None:
                    # Allow selecting the collection root as a destination.
                    mark = "[x]" if selected == "__root" else "[ ]"
                    choices.append(
                        {"name": f"{mark} Импортировать в корень коллекции", "value": "__sel_root"}
                    )
                for d in children.get(parent_id, []):
                    did = d.get("id")
                    has_children = did in children
                    mark = "[x]" if selected == did else "[ ]"
                    title = d.get("title") or "(без названия)"
                    suffix = "/" if has_children else ""
                    choices.append({"name": f"{mark} {title}{suffix}", "value": ("doc", d)})
                choices.append({"name": "<Готово>", "value": "__done"})
                return choices

            while True:
                choices = build_choices()
                default_val = search.pop("default", None)
                if search["query"]:
                    matches = [c["value"] for c in choices if search["query"].lower() in c["name"].lower()]
                    if matches:
                        default_val = matches[search["index"] % len(matches)]
                prompt = ListPrompt(
                    message=path,
                    choices=choices,
                    default=default_val,
                    instruction="↑/↓, PgUp/PgDn, Space выбрать, Ctrl+R обновить, Ctrl+S поиск, Enter",
                    height="90%",
                    keybindings={
                        "pageup": [{"key": "pageup"}],
                        "pagedown": [{"key": "pagedown"}],
                        "choose": [{"key": "space"}],
                        "refresh": [{"key": "c-r"}],
                        "search": [{"key": "c-s"}],
                    },
                )

                def _page(step: int) -> None:
                    cc = prompt.content_control
                    cc.selected_choice_index = max(
                        0, min(cc.choice_count - 1, cc.selected_choice_index + step)
                    )

                def _page_up(event) -> None:
                    _page(-10)

                def _page_down(event) -> None:
                    _page(10)
                def _choose(event) -> None:
                    nonlocal selected, selected_label
                    search["default"] = prompt.content_control.selection["value"]
                    val = prompt.content_control.selection["value"]
                    if val == "__sel_root":
                        target = "__root"
                        label = coll.get("name") or "(без названия)"
                    elif isinstance(val, tuple) and val[0] == "doc":
                        target = val[1].get("id")
                        label = f"{path}/{val[1].get('title') or '(без названия)'}"
                    else:
                        return
                    if selected == target:
                        selected = None
                    else:
                        selected = target
                        selected_label = label
                    event.app.exit(result="__refresh__")

                def _refresh(event) -> None:
                    nonlocal docs, children
                    search["default"] = prompt.content_control.selection["value"]
                    load_children(parent_id)
                    event.app.exit(result="__refresh__")

                def _search(event) -> None:
                    search["default"] = prompt.content_control.selection["value"]
                    if search["query"]:
                        search["index"] += 1
                        event.app.exit(result="__refresh__")
                    else:
                        event.app.exit(result="__search__")

                prompt.kb_func_lookup.update(
                    {
                        "pageup": [{"func": _page_up}],
                        "pagedown": [{"func": _page_down}],
                        "choose": [{"func": _choose}],
                        "refresh": [{"func": _refresh}],
                        "search": [{"func": _search}],
                    }
                )

                choice = _execute(prompt)
                if choice == "__up":
                    return None
                if choice == "__refresh__":
                    continue
                if choice == "__search__":
                    q = _execute(
                        inquirer.text(
                            message="Поиск:",
                            default=search["query"] or "",
                            keybindings={"answer": [{"key": "c-s"}]},
                        )
                    )
                    search["query"] = q or None
                    search["index"] = 0
                    continue
                if choice == "__done":
                    if selected is None:
                        continue
                    if selected == "__root":
                        return coll_id, None, coll.get("name") or "(без названия)"
                    return coll_id, selected, selected_label
                if choice == "__sel_root":
                    continue
                typ, doc = choice
                if typ == "doc":
                    did = doc.get("id")
                    title = doc.get("title") or "(без названия)"
                    load_children(did)
                    if did in children:
                        res = browse(did, f"{path}/{title}", doc)
                        if res:
                            return res
                    # if no children, do nothing

        return browse(None, coll.get("name") or "(без названия)", None)

    search: Dict[str, Optional[object]] = {"query": None, "index": 0, "default": None}
    while True:
        choices = [
            {"name": c.get("name") or "(без названия)", "value": c}
            for c in collections
        ]
        default_val = search.pop("default", None)
        if search["query"]:
            matches = [
                c["value"]
                for c in choices
                if search["query"].lower() in c["name"].lower()
            ]
            if matches:
                default_val = matches[search["index"] % len(matches)]
        prompt = ListPrompt(
            message="Коллекции",
            choices=choices,
            default=default_val,
            instruction="↑/↓, PgUp/PgDn, Ctrl+R обновить, Ctrl+S поиск, Enter",
            height="90%",
            keybindings={
                "pageup": [{"key": "pageup"}],
                "pagedown": [{"key": "pagedown"}],
                "refresh": [{"key": "c-r"}],
                "search": [{"key": "c-s"}],
            },
        )

        def _page(step: int) -> None:
            cc = prompt.content_control
            cc.selected_choice_index = max(
                0, min(cc.choice_count - 1, cc.selected_choice_index + step)
            )

        def _page_up(event) -> None:
            _page(-10)

        def _page_down(event) -> None:
            _page(10)
        def _refresh(event) -> None:
            nonlocal collections
            search["default"] = prompt.content_control.selection["value"]
            collections = list_collections(
                base,
                token,
                use_cache=True,
                refresh_cache=True,
                workers=workers,
                desc=None,
            )
            event.app.exit(result="__refresh__")

        def _search(event) -> None:
            search["default"] = prompt.content_control.selection["value"]
            if search["query"]:
                search["index"] += 1
                event.app.exit(result="__refresh__")
            else:
                event.app.exit(result="__search__")

        prompt.kb_func_lookup.update(
            {
                "pageup": [{"func": _page_up}],
                "pagedown": [{"func": _page_down}],
                "refresh": [{"func": _refresh}],
                "search": [{"func": _search}],
            }
        )

        coll = _execute(prompt)
        if coll == "__refresh__":
            continue
        if coll == "__search__":
            q = _execute(
                inquirer.text(
                    message="Поиск:",
                    default=search["query"] or "",
                    keybindings={"answer": [{"key": "c-s"}]},
                )
            )
            search["query"] = q or None
            search["index"] = 0
            continue
        if not coll:
            continue
        res = browse_collection(coll)
        if res:
            return res
