import subprocess
import os
import json
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yonote_cli"))
import yonote_cli.commands.admin as admin
import yonote_cli.commands.users as users
import yonote_cli.commands.groups as groups
import yonote_cli.commands.collections as collections_cmd

def test_cli_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    usage = result.stdout.splitlines()[0]
    assert "{auth,cache,export,import,users,groups,collections,admin}" in usage


def test_admin_users_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "admin", "users", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "update" in result.stdout
    assert "add" in result.stdout
    assert "promote" not in result.stdout

    upd_help = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "admin", "users", "update", "--help"
    ], capture_output=True, text=True)
    assert "--promote" in upd_help.stdout


def test_auth_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "auth", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Save base URL" in result.stdout


def test_auth_set(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "auth", "set",
        "--base-url", "https://example.com/api", "--token", "secret"
    ], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    cfg = json.loads((tmp_path / ".yonote.json").read_text())
    assert cfg["base_url"] == "https://example.com/api"
    assert cfg["token"] == "secret"


def test_admin_users_list_pagination(monkeypatch, capsys):
    captured = {}

    def fake_fetch_all(base, token, path, *, params=None, **_):
        captured["params"] = params
        return [
            {"id": "1", "email": "a@example.com", "name": "A", "isAdmin": False, "isSuspended": False}
        ]

    monkeypatch.setattr(admin, "fetch_all_concurrent", fake_fetch_all)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(query=None)
    admin.cmd_admin_users_list(args)
    out, _ = capsys.readouterr()
    assert "a@example.com" in out
    assert captured["params"] == {"filter": "all"}


def test_admin_users_list_query(monkeypatch):
    captured = {}

    def fake_fetch_all(base, token, path, *, params=None, **_):
        captured["params"] = params
        return []

    monkeypatch.setattr(admin, "fetch_all_concurrent", fake_fetch_all)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(query="smith")
    admin.cmd_admin_users_list(args)
    assert captured["params"] == {"filter": "all", "query": "smith"}


def test_admin_users_add(monkeypatch, capsys):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(emails=["a@example.com", "b@example.com"], role="member")
    admin.cmd_admin_users_add(args)
    out, _ = capsys.readouterr()
    assert "invited a@example.com" in out
    assert captured["url"] == "base/users.invite"
    assert captured["payload"] == {
        "invites": [
            {"email": "a@example.com", "name": "a", "role": "member"},
            {"email": "b@example.com", "name": "b", "role": "member"},
        ]
    }


def test_admin_users_update_promote(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {"data": {}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident, **_: ident + "_id")

    args = SimpleNamespace(users=["u1", "u2"], name=None, avatar_url=None,
                           promote=True, demote=False, suspend=False, activate=False)
    admin.cmd_admin_users_update(args)
    assert calls == [
        ("base/users.promote", {"id": "u1_id"}),
        ("base/users.promote", {"id": "u2_id"}),
    ]


def test_admin_users_update_name(monkeypatch):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"data": {}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident, **_: "uid")

    args = SimpleNamespace(users=["u"], name="New", avatar_url=None,
                           promote=False, demote=False, suspend=False, activate=False)
    admin.cmd_admin_users_update(args)
    assert captured["url"] == "base/users.update"
    assert captured["payload"] == {"id": "uid", "name": "New"}


def test_admin_groups_memberships_paginates(monkeypatch, capsys):
    offsets = []

    def fake_http_json(method, url, token, payload):
        offsets.append(payload["offset"])
        if payload["offset"] == 0:
            return {"data": {"users": [{"id": "1", "email": "u1@example.com", "name": "U1"}]}}
        elif payload["offset"] == 1:
            return {"data": {"users": [{"id": "2", "email": "u2@example.com", "name": "U2"}]}}
        else:
            return {"data": {"users": []}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: ident)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "API_MAX_LIMIT", 1)

    args = SimpleNamespace(group="g", query=None)
    admin.cmd_admin_groups_memberships(args)
    out, _ = capsys.readouterr()
    assert "u2@example.com" in out
    assert offsets[:2] == [0, 1]


def test_admin_groups_list(monkeypatch, capsys):
    captured = {}

    def fake_fetch(base, token, path, params, key):
        captured["params"] = params
        return [{"id": "g1", "name": "G1", "memberCount": 1}]

    monkeypatch.setattr(admin, "_fetch_memberships", fake_fetch)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(query="qq")
    admin.cmd_admin_groups_list(args)
    out, _ = capsys.readouterr()
    assert "G1" in out
    assert captured["params"] == {"query": "qq"}


def test_admin_groups_create_multiple(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {"data": {"name": payload["name"]}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(names=["g1", "g2"])
    admin.cmd_admin_groups_create(args)
    assert calls == [
        ("base/groups.create", {"name": "g1"}),
        ("base/groups.create", {"name": "g2"}),
    ]


def test_admin_groups_delete_multiple(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: f"id-{ident}")
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(groups=["g1", "g2"])
    admin.cmd_admin_groups_delete(args)

    assert calls == [
        ("base/groups.delete", {"id": "id-g1"}),
        ("base/groups.delete", {"id": "id-g2"}),
    ]


def test_admin_groups_rename(monkeypatch, capsys):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"data": {"id": "gid", "name": "new"}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: "gid")
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(group="old", name="new")
    admin.cmd_admin_groups_rename(args)
    out, _ = capsys.readouterr()
    assert "\"name\": \"new\"" in out
    assert captured["payload"] == {"id": "gid", "name": "new"}


def test_resolve_group_id(monkeypatch):
    def fake_http_json(method, url, token, payload):
        if payload["offset"] == 0:
            return {"data": {"groups": [{"id": "gid", "name": "foo"}]}}
        return {"data": {"groups": []}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "API_MAX_LIMIT", 1)

    gid = admin._resolve_group_id("base", "token", "foo")
    assert gid == "gid"


def test_users_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "users", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "promote" in result.stdout


def test_users_list_query(monkeypatch):
    captured = {}

    def fake_fetch_all(base, token, path, *, params=None, **_):
        captured["params"] = params
        return []

    monkeypatch.setattr(admin, "fetch_all_concurrent", fake_fetch_all)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(query="smith")
    users.cmd_users_list(args)
    assert captured["params"] == {"filter": "all", "query": "smith"}


def test_users_promote(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident, **_: ident)
    args = SimpleNamespace(users=["u1", "u2"])
    users.cmd_users_promote(args)
    assert calls == [
        ("base/users.promote", {"id": "u1"}),
        ("base/users.promote", {"id": "u2"}),
    ]


def test_groups_add_del_user(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload, *, handle_error=True):
        calls.append((url, payload, handle_error))
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: ident)
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident, **_: ident)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args_add = SimpleNamespace(group="g", users=["u1", "u2"])
    groups.cmd_groups_add_user(args_add)
    args_del = SimpleNamespace(group="g", users=["u1", "u2"])
    groups.cmd_groups_del_user(args_del)

    assert calls == [
        ("base/groups.add_user", {"id": "g", "userId": "u1"}, False),
        ("base/groups.add_user", {"id": "g", "userId": "u2"}, False),
        ("base/groups.remove_user", {"id": "g", "userId": "u1"}, False),
        ("base/groups.remove_user", {"id": "g", "userId": "u2"}, False),
    ]


def test_admin_groups_add_user_skip_existing(monkeypatch, capsys):
    import io
    from urllib.error import HTTPError

    def fake_http_json(method, url, token, payload, *, handle_error=True):
        if payload["userId"] == "u2":
            fp = io.BytesIO(b'{"error":"already_member"}')
            raise HTTPError(url, 400, "Bad Request", None, fp)
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: "gid")
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident, **_: ident)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(group="g", users=["u1", "u2"])
    admin.cmd_admin_groups_add_user(args)
    out, _ = capsys.readouterr()
    assert "added u1 to g" in out
    assert "skipped u2: already_member" in out


def test_admin_groups_del_user_handles_missing(monkeypatch, capsys):
    import io
    from urllib.error import HTTPError

    def fake_http_json(method, url, token, payload, *, handle_error=True):
        if payload["userId"] == "u1":
            fp = io.BytesIO(b'{"error":"not_found"}')
            raise HTTPError(url, 404, "Not Found", None, fp)
        return {}

    def fake_resolve_user_id(base, token, ident, *, required=True):
        if ident == "u2":
            print(f"User not found: {ident}", file=sys.stderr)
            return None
        return ident

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: "gid")
    monkeypatch.setattr(admin, "_resolve_user_id", fake_resolve_user_id)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(group="g", users=["u1", "u2"])
    admin.cmd_admin_groups_del_user(args)
    out, err = capsys.readouterr()
    assert "skipped u1: not_found" in out
    assert "User not found: u2" in err


def test_groups_memberships_paginates(monkeypatch, capsys):
    offsets = []

    def fake_http_json(method, url, token, payload):
        offsets.append(payload["offset"])
        if payload["offset"] == 0:
            return {"data": {"users": [{"id": "1", "email": "u1@example.com", "name": "U1"}]}}
        elif payload["offset"] == 1:
            return {"data": {"users": [{"id": "2", "email": "u2@example.com", "name": "U2"}]}}
        else:
            return {"data": {"users": []}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "_resolve_group_id", lambda base, token, ident: ident)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "API_MAX_LIMIT", 1)

    args = SimpleNamespace(group="g", query=None)
    groups.cmd_groups_memberships(args)
    out, _ = capsys.readouterr()
    assert "u2@example.com" in out
    assert offsets[:2] == [0, 1]


def test_collections_memberships_params(monkeypatch):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured.update(payload)
        return {"data": {"users": []}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(collection="c", query="q", permission="read")
    collections_cmd.cmd_collections_memberships(args)
    assert captured["permission"] == "read"
    assert captured["query"] == "q"


def test_collections_group_memberships_params(monkeypatch):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured.update(payload)
        return {"data": {"groups": []}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(collection="c", query="gq", permission="maintainer")
    collections_cmd.cmd_collections_group_memberships(args)
    assert captured["permission"] == "maintainer"
    assert captured["query"] == "gq"


def test_admin_collections_list(monkeypatch, capsys):
    captured = {}

    def fake_fetch_all(base, token, path, *, params=None, **_):
        captured["params"] = params
        return [{"id": "c1", "name": "C1"}]

    monkeypatch.setattr(admin, "fetch_all_concurrent", fake_fetch_all)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(query="q")
    admin.cmd_admin_collections_list(args)
    out, _ = capsys.readouterr()
    assert "C1" in out
    assert captured["params"] == {"query": "q"}
