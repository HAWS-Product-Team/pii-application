"""Unit tests for the CSV merge step. Local filesystem only, no AWS needed."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import merge
from merge.cli import build_parser, main
from merge.merger import (
    HeaderMismatchError,
    MalformedRowError,
    MergeError,
    NoInputFilesError,
    RowCountMismatchError,
    merge_csv_files,
)
from merge.storage import LocalStorage

HEADER = ["date", "description", "amount"]


@pytest.fixture
def storage():
    return LocalStorage()


def write_csv(path: Path, rows, header=HEADER):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def read_csv(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.reader(handle))


def test_merges_all_files_without_source_column_by_default(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-02", "coffee", "4.50"]])
    write_csv(in_dir / "b.csv", [["2026-01-03", "milk", "3.25"],
                                 ["2026-01-04", "bread", "5.00"]])
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))

    assert result.total_rows == 3
    assert result.file_count == 2
    assert result.rows_per_file == {"a.csv": 1, "b.csv": 2}

    rows = read_csv(out)
    assert rows[0] == HEADER
    assert rows[1] == ["2026-01-02", "coffee", "4.50"]
    assert rows[3] == ["2026-01-04", "bread", "5.00"]


def test_merges_all_files_and_appends_source_column_when_specified(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-02", "coffee", "4.50"]])
    write_csv(in_dir / "b.csv", [["2026-01-03", "milk", "3.25"],
                                 ["2026-01-04", "bread", "5.00"]])
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out), source_column="source_file")

    assert result.total_rows == 3
    assert result.file_count == 2
    assert result.rows_per_file == {"a.csv": 1, "b.csv": 2}

    rows = read_csv(out)
    assert rows[0] == HEADER + ["source_file"]
    assert rows[1] == ["2026-01-02", "coffee", "4.50", "a.csv"]
    assert rows[3] == ["2026-01-04", "bread", "5.00", "b.csv"]


def test_header_written_exactly_once(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    for name in ("a.csv", "b.csv", "c.csv"):
        write_csv(in_dir / name, [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    merge_csv_files(storage, str(in_dir), str(out))

    rows = read_csv(out)
    assert len(rows) == 4  # 1 header + 3 data
    assert rows.count(HEADER) == 1


def test_preserves_commas_quotes_and_embedded_newlines(tmp_path, storage):
    """The reason this streams with the csv module and not `tail -n +2`."""
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    tricky = ["2026-01-05", 'Widget, "large"\nsecond line', "12.00"]
    write_csv(in_dir / "a.csv", [tricky])
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))

    assert result.total_rows == 1
    assert read_csv(out)[1] == tricky


def test_strips_bom_from_upstream_files(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    path = in_dir / "a.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerow(["2026-01-01", "x", "1.00"])
    out = tmp_path / "merged.csv"

    merge_csv_files(storage, str(in_dir), str(out))

    assert read_csv(out)[0] == HEADER


def test_tolerates_missing_trailing_newline(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.csv").write_text("date,description,amount\n2026-01-01,x,1.00")
    (in_dir / "b.csv").write_text("date,description,amount\n2026-01-02,y,2.00\n")
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))

    assert result.total_rows == 2


def test_rejects_mismatched_headers(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    write_csv(in_dir / "b.csv", [["2026-01-02", "2.00"]], header=["date", "amount"])
    out = tmp_path / "merged.csv"

    with pytest.raises(HeaderMismatchError) as exc:
        merge_csv_files(storage, str(in_dir), str(out))
    assert "b.csv" in str(exc.value)


def test_rejects_row_with_wrong_field_count(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.csv").write_text(
        "date,description,amount\n2026-01-01,x,1.00\n2026-01-02,y\n"
    )
    out = tmp_path / "merged.csv"

    with pytest.raises(MalformedRowError) as exc:
        merge_csv_files(storage, str(in_dir), str(out))
    assert "line 3" in str(exc.value)


def test_rejects_empty_input_directory(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()

    with pytest.raises(NoInputFilesError):
        merge_csv_files(storage, str(in_dir), str(tmp_path / "merged.csv"))


def test_rejects_empty_input_file(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.csv").write_text("")

    with pytest.raises(MergeError):
        merge_csv_files(storage, str(in_dir), str(tmp_path / "merged.csv"))


def test_rejects_source_column_already_present(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x"]], header=["date", "source_file"])

    with pytest.raises(MergeError):
        merge_csv_files(storage, str(in_dir), str(tmp_path / "merged.csv"), source_column="source_file")


def test_header_only_file_contributes_zero_rows(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [])
    write_csv(in_dir / "b.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))

    assert result.rows_per_file == {"a.csv": 0, "b.csv": 1}
    assert result.total_rows == 1


def test_files_merged_in_sorted_order(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "z.csv", [["2026-01-01", "z", "1.00"]])
    write_csv(in_dir / "a.csv", [["2026-01-01", "a", "1.00"]])
    out = tmp_path / "merged.csv"

    merge_csv_files(storage, str(in_dir), str(out), source_column="source_file")

    assert [row[-1] for row in read_csv(out)[1:]] == ["a.csv", "z.csv"]


def test_ignores_non_csv_files(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    (in_dir / "notes.txt").write_text("ignore me")
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))

    assert result.file_count == 1


def test_custom_source_column_name(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    merge_csv_files(storage, str(in_dir), str(out), source_column="origin_pdf")

    assert read_csv(out)[0][-1] == "origin_pdf"


def test_rejects_input_location_when_not_a_directory(tmp_path, storage):
    file_input = tmp_path / "input.csv"
    file_input.write_text("dummy")
    out = tmp_path / "merged.csv"

    with pytest.raises(MergeError) as exc:
        merge_csv_files(storage, str(file_input), str(out))
    assert "not a directory" in str(exc.value)


def test_rejects_output_path_when_directory(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    with pytest.raises(MergeError) as exc:
        merge_csv_files(storage, str(in_dir), str(out_dir))
    assert "directory" in str(exc.value)


def test_cli_returns_zero_on_success(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    code = main([str(in_dir), str(out)])

    assert code == 0
    assert out.exists()
    captured = capsys.readouterr().out
    assert "a.csv: 1 rows" not in captured
    assert "merged 1 files" in captured
    assert read_csv(out)[0] == HEADER


def test_cli_verbose_flag(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    code = main([str(in_dir), str(out), "--verbose"])

    assert code == 0
    assert out.exists()
    captured = capsys.readouterr().out
    assert "a.csv: 1 rows" in captured
    assert "merged 1 files" in captured
    assert read_csv(out)[0] == HEADER + ["source_file"]
    assert read_csv(out)[1][-1] == "a.csv"


def test_cli_returns_nonzero_on_merge_error(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()

    code = main([str(in_dir), str(tmp_path / "merged.csv")])

    assert code == 1
    assert "merge failed" in capsys.readouterr().err


def test_cli_parser_positional_arguments():
    parser = build_parser()
    args = parser.parse_args(["path/to/input_dir", "path/to/output.csv"])
    assert args.input == "path/to/input_dir"
    assert args.output == "path/to/output.csv"
    assert args.source_column == "source_file"
    assert not args.verbose


def test_cli_parser_help():
    parser = build_parser()
    help_text = parser.format_help()
    assert "must be a directory" in help_text
    assert "output" in help_text.lower()
    assert "--verbose" in help_text


def test_merge_csv_files_requires_output_path(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])

    with pytest.raises(ValueError, match="output_path is required"):
        merge_csv_files(storage, str(in_dir), output_path=None, output_location=None)


def test_merge_csv_files_with_output_location_alias(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), output_location=str(out))
    assert result.total_rows == 1
    assert result.output_path == str(out)


def test_skips_blank_lines_in_csv(tmp_path, storage):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.csv").write_text(
        "date,description,amount\n2026-01-01,x,1.00\n\n2026-01-02,y,2.00\n\n"
    )
    out = tmp_path / "merged.csv"

    result = merge_csv_files(storage, str(in_dir), str(out))
    assert result.total_rows == 2


def test_raises_row_count_mismatch(tmp_path, storage, monkeypatch):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    monkeypatch.setattr("merge.merger._count_data_rows", lambda _s, _p: 999)

    with pytest.raises(RowCountMismatchError, match="Merged file has 999 data rows"):
        merge_csv_files(storage, str(in_dir), str(out))


def test_cli_custom_source_column_with_verbose(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    code = main([str(in_dir), str(out), "--verbose", "--source-column", "origin_doc"])
    assert code == 0
    assert read_csv(out)[0][-1] == "origin_doc"


def test_cli_custom_source_column_without_verbose(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    code = main([str(in_dir), str(out), "--source-column", "origin_doc"])
    assert code == 0
    assert read_csv(out)[0] == HEADER
    captured = capsys.readouterr().out
    assert "a.csv: 1 rows" not in captured


def test_cli_module_execution(tmp_path, monkeypatch):
    import runpy
    import sys

    in_dir = tmp_path / "in"
    in_dir.mkdir()
    write_csv(in_dir / "a.csv", [["2026-01-01", "x", "1.00"]])
    out = tmp_path / "merged.csv"

    monkeypatch.setattr(sys, "argv", ["merge.cli", str(in_dir), str(out)])
    monkeypatch.delitem(sys.modules, "merge.cli", raising=False)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("merge.cli", run_name="__main__")
    assert exc.value.code == 0
    assert out.exists()


def test_package_main_entrypoint(capsys):
    merge.main()
    captured = capsys.readouterr().out
    assert "Hello from merge!" in captured
