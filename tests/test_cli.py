import json

import pytest

from envman.cli import main


@pytest.fixture
def env_path(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DEBUG=false\nAPI_KEY=supersecretvalue\nPORT=8000\n")
    return path


def test_cli_list(env_path, capsys):
    assert main(["list", str(env_path)]) == 0
    assert capsys.readouterr().out == "DEBUG=false\nAPI_KEY=supersecretvalue\nPORT=8000\n"


def test_cli_list_redacts_secrets(env_path, capsys):
    assert main(["list", str(env_path), "--redact"]) == 0
    out = capsys.readouterr().out
    assert "supersecretvalue" not in out
    assert "API_KEY=su************ue" in out


def test_cli_get_missing_returns_one(env_path, capsys):
    assert main(["get", str(env_path), "NOPE"]) == 1
    assert "not found" in capsys.readouterr().err


def test_cli_set_and_get_round_trip(env_path, capsys):
    assert main(["set", str(env_path), "DEBUG", "true"]) == 0
    assert main(["get", str(env_path), "DEBUG"]) == 0
    assert capsys.readouterr().out == "set DEBUG\ntrue\n"


def test_cli_unset_missing_returns_one(env_path):
    assert main(["unset", str(env_path), "NOPE"]) == 1


def test_cli_check_ok_and_failing(tmp_path, capsys):
    env_path = tmp_path / ".env"
    env_path.write_text("A=1\n")
    template = tmp_path / ".env.example"
    template.write_text("A=\nB=\n")
    assert main(["check", str(env_path), str(template)]) == 1
    assert "missing: B" in capsys.readouterr().out
    assert main(["set", str(env_path), "B", "2"]) == 0
    assert main(["check", str(env_path), str(template)]) == 0
    assert "ok: all required keys present" in capsys.readouterr().out


def test_cli_diff(tmp_path, capsys):
    old = tmp_path / "old.env"
    new = tmp_path / "new.env"
    old.write_text("A=1\nB=2\n")
    new.write_text("A=1\nB=3\nC=4\n")
    assert main(["diff", str(old), str(new)]) == 0
    out = capsys.readouterr().out
    assert "+ C=4" in out
    assert "~ B: 2 -> 3" in out


def test_cli_export_shell_and_json(env_path, capsys):
    assert main(["export", str(env_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == {"DEBUG": "false", "API_KEY": "supersecretvalue", "PORT": "8000"}
    assert main(["export", str(env_path)]) == 0
    out = capsys.readouterr().out
    assert "export DEBUG=false" in out
    assert "export PORT=8000" in out


def test_cli_parse_error_exits_two(tmp_path):
    bad = tmp_path / ".env"
    bad.write_text("not a pair\n")
    with pytest.raises(SystemExit) as exc:
        main(["list", str(bad)])
    assert exc.value.code == 2
