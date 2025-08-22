import pathlib
import sys
import pytest
from io import BytesIO
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "yonote_cli"))
from yonote_cli.core.http import http_json


def test_http_json_forbidden(monkeypatch, capsys):
    def fake_urlopen(req, timeout=60):
        body = b'{"ok":false,"error":"Unauthorized"}'
        raise HTTPError(req.full_url, 403, "Forbidden", None, BytesIO(body))

    monkeypatch.setattr("yonote_cli.core.http.urlopen", fake_urlopen)
    with pytest.raises(SystemExit) as exc:
        http_json("GET", "https://example/api", "token")
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Forbidden" in err
    assert "administrator" in err
