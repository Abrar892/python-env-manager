import os

import pytest

from envman.parser import Entry, ParseError, pairs, parse_env_text


def test_simple_pairs():
    entries = parse_env_text("A=1\nB=hello world\n")
    assert pairs(entries) == {"A": "1", "B": "hello world"}


def test_empty_value_and_missing_value():
    entries = parse_env_text("EMPTY=\n")
    assert pairs(entries) == {"EMPTY": ""}


def test_export_prefix_and_dotted_keys():
    entries = parse_env_text("export APP_ENV=prod\napp.debug=false\n")
    assert pairs(entries) == {"APP_ENV": "prod", "app.debug": "false"}
    assert entries[0].exported is True


def test_comments_and_blank_lines_preserved():
    text = "# header\n\nA=1\n# trailing\n"
    entries = parse_env_text(text)
    assert [e.kind for e in entries] == ["comment", "blank", "pair", "comment"]
    assert pairs(entries) == {"A": "1"}


def test_single_quotes_are_literal():
    entries = parse_env_text("A='a $B \\n literal'\n")
    assert pairs(entries) == {"A": "a $B \\n literal"}


def test_double_quotes_unescape_and_expand():
    entries = parse_env_text('A="line1\\nline2"\nB="see $A"\n')
    assert pairs(entries)["A"] == "line1\nline2"
    assert pairs(entries)["B"] == "see line1\nline2"


def test_escaped_backslash_before_n_is_not_a_newline():
    # \\n in the file means a literal backslash followed by n.
    entries = parse_env_text('A="C:\\\\new"\n')
    assert pairs(entries) == {"A": "C:\\new"}


def test_escaped_quote_inside_double_quotes():
    entries = parse_env_text('A="say \\"hi\\""\n')
    assert pairs(entries) == {"A": 'say "hi"'}


def test_multiline_double_quoted_value():
    text = 'KEY="line one\nline two"\nOTHER=1\n'
    entries = parse_env_text(text)
    assert pairs(entries) == {"KEY": "line one\nline two", "OTHER": "1"}


def test_unterminated_quote_raises():
    with pytest.raises(ParseError):
        parse_env_text('A="never closed\n')


def test_inline_comment_after_unquoted_value():
    entries = parse_env_text("A=1 # one\nB=2#not-a-comment\n")
    assert pairs(entries) == {"A": "1", "B": "2#not-a-comment"}


def test_hash_inside_quotes_is_not_a_comment():
    entries = parse_env_text('A="a#b"\nB=\'c#d\'\n')
    assert pairs(entries) == {"A": "a#b", "B": "c#d"}


def test_variable_expansion_uses_earlier_keys():
    entries = parse_env_text("HOST=example.com\nURL=https://${HOST}/api\n")
    assert pairs(entries)["URL"] == "https://example.com/api"


def test_variable_expansion_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("ENVMAN_TEST_HOME", "/home/tester")
    entries = parse_env_text("P=$ENVMAN_TEST_HOME/app\n")
    assert pairs(entries) == {"P": "/home/tester/app"}


def test_missing_variable_expands_to_empty():
    entries = parse_env_text("P=$DEFINITELY_NOT_SET_XYZ/more\n")
    assert pairs(entries) == {"P": "/more"}


def test_garbage_line_raises():
    with pytest.raises(ParseError):
        parse_env_text("this is not a pair\n")


def test_duplicate_keys_last_wins():
    entries = parse_env_text("A=first\nA=second\n")
    assert pairs(entries) == {"A": "second"}


def test_render_round_trip_keeps_comments_and_quotes():
    text = '# config\nA=1\nB="two words"\n\n# end\n'
    entries = parse_env_text(text)
    assert "\n".join(e.render() for e in entries) + "\n" == text


def test_entry_render_with_quotes():
    entry = Entry(kind="pair", key="K", value="a b", quoted='"')
    assert entry.render() == 'K="a b"'
    entry2 = Entry(kind="pair", key="K", value="x", quoted="", exported=True)
    assert entry2.render() == "export K=x"
