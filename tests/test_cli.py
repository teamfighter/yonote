import subprocess
import os
import json

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
    assert "promote" in result.stdout


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
