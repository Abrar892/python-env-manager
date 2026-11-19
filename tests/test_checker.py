from envman.checker import check_against_template, diff_envs
from envman.manager import EnvFile


def _env(text):
    return EnvFile("unused", text=text)


def test_check_all_present_is_ok():
    result = check_against_template(
        _env("A=1\nB=2\n"), _env("A=\nB=\n")
    )
    assert result.ok
    assert result.missing == [] and result.empty == [] and result.extra == []


def test_check_reports_missing_and_empty():
    result = check_against_template(
        _env("A=1\nB=\nC=3\n"), _env("A=\nB=\nD=\n")
    )
    assert result.missing == ["D"]
    assert result.empty == ["B"]
    assert result.extra == ["C"]
    assert result.ok is False


def test_diff_added_removed_changed():
    result = diff_envs(_env("A=1\nB=2\nC=3\n"), _env("A=1\nB=20\nD=4\n"))
    assert result.added == {"D": "4"}
    assert result.removed == {"C": "3"}
    assert result.changed == {"B": ("2", "20")}
    assert result.empty is False


def test_diff_identical_is_empty():
    result = diff_envs(_env("A=1\n"), _env("A=1\n"))
    assert result.empty
