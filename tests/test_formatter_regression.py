from pathlib import Path

from epl.formatter import diff_format, format_directory, format_source


def test_formatter_is_idempotent_for_nested_blocks():
    source = "\n".join([
        "if x then",
        "print 1",
        "while y",
        "print 2",
        "end",
        "end",
    ])

    once = format_source(source)
    twice = format_source(once)

    assert once == twice


def test_diff_format_is_empty_after_formatting():
    formatted = format_source('Print "hello"')
    assert diff_format(formatted) == ""


def test_format_directory_reports_changed_files(tmp_path: Path):
    (tmp_path / "a.epl").write_text('print "hello"\n', encoding="utf-8")
    (tmp_path / "b.epl").write_text('Print "ok"\n', encoding="utf-8")

    results = format_directory(str(tmp_path))

    changed = {Path(entry["file"]).name: entry["changed"] for entry in results}
    assert changed["a.epl"] is True
    assert changed["b.epl"] is False
