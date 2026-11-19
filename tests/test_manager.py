from pathlib import Path

import pytest

from envman.manager import EnvFile


@pytest.fixture
def env_file(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# app config\nDEBUG=false\nPORT=8000\n\n# secrets\nAPI_KEY=old\n")
    return EnvFile(path), path


def test_get_and_keys(env_file):
    env, _ = env_file
    assert env.get("DEBUG") == "false"
    assert env.get("MISSING") is None
    assert env.get("MISSING", "default") == "default"
    assert env.keys() == ["DEBUG", "PORT", "API_KEY"]


def test_set_updates_in_place_and_keeps_comments(env_file):
    env, path = env_file
    env.set("PORT", "9000")
    env.save()
    text = path.read_text()
    assert "PORT=9000" in text
    assert "# app config" in text
    assert "# secrets" in text
    assert text.index("DEBUG") < text.index("PORT") < text.index("API_KEY")


def test_set_appends_new_key_at_end(env_file):
    env, path = env_file
    env.set("NEW_KEY", "value")
    env.save()
    assert path.read_text().rstrip().endswith("NEW_KEY=value")


def test_set_quotes_value_when_requested(env_file):
    env, path = env_file
    env.set("GREETING", "hello world", quote='"')
    env.save()
    assert 'GREETING="hello world"' in path.read_text()


def test_unset_removes_key_and_reports(env_file):
    env, path = env_file
    assert env.unset("PORT") is True
    assert env.unset("PORT") is False
    env.save()
    assert "PORT" not in path.read_text()
    assert env.get("PORT") is None


def test_save_creates_missing_file(tmp_path):
    path = tmp_path / "nested" / ".env"
    env = EnvFile(path)
    env.set("A", "1")
    env.save()
    assert path.read_text() == "A=1\n"


def test_save_is_atomic_and_replaces_in_place(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\n")
    env = EnvFile(path)
    env.set("A", "2")
    env.save()
    assert path.read_text() == "A=2\n"
    leftovers = list(tmp_path.glob(".env.*.tmp"))
    assert leftovers == []


def test_empty_file_renders_empty(tmp_path):
    env = EnvFile(tmp_path / ".env")
    assert env.render() == ""
    assert env.to_dict() == {}
