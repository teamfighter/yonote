import subprocess
import os
import json
from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "yonote_cli"))
import yonote_cli.commands.admin as admin
import yonote_cli.commands.users as users

def test_cli_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Yonote CLI" in result.stdout


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


def test_users_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "users", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "list" in result.stdout


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


def test_users_add(monkeypatch, capsys):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(users, "http_json", fake_http_json)
    monkeypatch.setattr(users, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(emails=["a@example.com", "b@example.com"])
    users.cmd_users_add(args)
    out, _ = capsys.readouterr()
    assert "invited a@example.com" in out
    assert captured["url"] == "base/users.invite"
    assert captured["payload"] == {"emails": ["a@example.com", "b@example.com"]}


def test_admin_users_add(monkeypatch, capsys):
    captured = {}

    def fake_http_json(method, url, token, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))

    args = SimpleNamespace(emails=["a@example.com", "b@example.com"])
    admin.cmd_admin_users_add(args)
    out, _ = capsys.readouterr()
    assert "invited a@example.com" in out
    assert captured["url"] == "base/users.invite"
    assert captured["payload"] == {"emails": ["a@example.com", "b@example.com"]}


def test_admin_users_update_promote(monkeypatch):
    calls = []

    def fake_http_json(method, url, token, payload):
        calls.append((url, payload))
        return {"data": {}}

    monkeypatch.setattr(admin, "http_json", fake_http_json)
    monkeypatch.setattr(admin, "get_base_and_token", lambda: ("base", "token"))
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident: ident + "_id")

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
    monkeypatch.setattr(admin, "_resolve_user_id", lambda base, token, ident: "uid")

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
