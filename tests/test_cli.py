import subprocess
import os
import json
from types import SimpleNamespace
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yonote_cli"))
import yonote_cli.commands.admin as admin

def test_cli_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    usage = result.stdout.splitlines()[0]
    assert "{auth,cache,export,import,admin}" in usage


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
    assert "--name" not in upd_help.stdout
    assert "--avatar-url" not in upd_help.stdout


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
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(emails=["a@example.com", "b@example.com"])
    admin.cmd_admin_users_add(args)
    out, _ = capsys.readouterr()
    assert "invited a@example.com" in out
    assert calls == [
        ("base/users.invite", {"emails": ["a@example.com"]}),
        ("base/users.invite", {"emails": ["b@example.com"]}),
    ]


def test_admin_users_add_continues_on_error(monkeypatch, capsys):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        if payload["emails"][0] == "b@example.com":
            raise SystemExit(2)
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(emails=["a@example.com", "b@example.com", "c@example.com"])
    admin.cmd_admin_users_add(args)
    out, err = capsys.readouterr()
    assert "invited a@example.com" in out
    assert "invited c@example.com" in out
    assert "failed b@example.com" in err
    assert calls == [
        ("base/users.invite", {"emails": ["a@example.com"]}),
        ("base/users.invite", {"emails": ["b@example.com"]}),
        ("base/users.invite", {"emails": ["c@example.com"]}),
    ]


def test_admin_users_delete_reports_all_missing(monkeypatch, capsys):
    calls = []

    def fake_resolve(base, token, ident):
        if ident == "good@example.com":
            return "uid1"
        print(f"User not found: {ident}", file=sys.stderr)
        raise SystemExit(1)

    def fake_http_json(method, url, token, payload):
        calls.append(payload["id"])

    monkeypatch.setattr(admin, "_resolve_user_id", fake_resolve)
    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(users=["good@example.com", "bad1@example.com", "bad2@example.com"])
    with pytest.raises(SystemExit):
        admin.cmd_admin_users_delete(args)
    _, err = capsys.readouterr()
    assert "User not found: bad1@example.com" in err
    assert "User not found: bad2@example.com" in err
    assert calls == ["uid1"]


def test_admin_users_update_promote(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {"data": {}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident: ident + "_id")

    args = SimpleNamespace(users=["u1", "u2"],
                           promote=True, demote=False, suspend=False, activate=False)
    admin.cmd_admin_users_update(args)
    assert calls == [
        ("base/users.promote", {"id": "u1_id"}),
        ("base/users.promote", {"id": "u2_id"}),
    ]


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


def test_admin_groups_list_handles_strings(monkeypatch, capsys):
    monkeypatch.setattr(
        admin,
        "fetch_all_concurrent",
        lambda base, token, path, params=None, desc=None: ["group1"],
    )
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    admin.cmd_admin_groups_list(SimpleNamespace())
    out, _ = capsys.readouterr()
    assert "group1" in out


def test_admin_groups_create_multiple(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {"data": {"id": "gid"}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(names=["g1", "g2"])
    admin.cmd_admin_groups_create(args)
    assert calls == [
        ("base/groups.create", {"name": "g1"}),
        ("base/groups.create", {"name": "g2"}),
    ]


def test_admin_collections_list(monkeypatch, capsys):
    monkeypatch.setattr(
        admin,
        "fetch_all_concurrent",
        lambda base, token, path, params=None, desc=None: [
            {"id": "c1", "name": "Col1", "private": False}
        ],
    )
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    admin.cmd_admin_collections_list(SimpleNamespace())
    out, _ = capsys.readouterr()
    assert "Col1" in out
