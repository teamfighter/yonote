import subprocess

def test_cli_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Yonote CLI" in result.stdout


def test_diag_help():
    result = subprocess.run([
        "python", "-m", "yonote_cli.yonote_cli", "diag", "--help"
    ], capture_output=True, text=True)
    assert result.returncode == 0
    assert "List collections" in result.stdout
    assert "List documents" in result.stdout
