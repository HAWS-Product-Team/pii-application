import pytest
import pandas as pd
import io
import sys
from unittest.mock import patch, MagicMock
from inflation_classifier.cli import main

def test_cli_default_behavior(tmp_path):
    # Prepare input CSV
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    df = pd.DataFrame({
        "item_description": ["apple", "banana"],
        "other_col": [1, 2]
    })
    df.to_csv(input_csv, index=False)

    # Mock setup_model and run_inference
    with patch("inflation_classifier.cli.setup_model") as mock_setup, \
         patch("inflation_classifier.cli.run_inference") as mock_inference, \
         patch("sys.stdout", new=io.StringIO()) as mock_stdout, \
         patch("sys.argv", ["inflation-classifier", str(input_csv), str(output_csv)]):
        
        mock_setup.return_value = (MagicMock(), ["Food", "Other"])
        mock_inference.return_value = (["Food", "Food"], 0.1)

        main()

        # Stdout should not contain the CSV data (it goes to file)
        output = mock_stdout.getvalue()
        assert "item_description" not in output

        # Check output file
        assert output_csv.exists()
        output_df = pd.read_csv(output_csv)

        assert list(output_df.columns) == ["item_description", "other_col", "category"]
        assert len(output_df) == 2
        assert output_df["category"].tolist() == ["Food", "Food"]

def test_cli_evaluate_flag(tmp_path):
    # Prepare input CSV
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    df = pd.DataFrame({
        "item_description": ["apple"],
        "category": ["Food"],
        "difficulty": ["easy"]
    })
    df.to_csv(input_csv, index=False)

    # Mock setup_model and run_inference
    with patch("inflation_classifier.cli.setup_model") as mock_setup, \
         patch("inflation_classifier.cli.run_inference") as mock_inference, \
         patch("sys.stdout", new=io.StringIO()) as mock_stdout, \
         patch("sys.argv", ["inflation-classifier", "--evaluate", str(input_csv), str(output_csv)]):
        
        mock_setup.return_value = (MagicMock(), ["Food"])
        mock_inference.return_value = (["Food"], 0.1)

        main()

        # Check output file (should be saved even with --evaluate)
        assert output_csv.exists()
        output_df = pd.read_csv(output_csv)
        assert "predicted" in output_df.columns

        # Check stdout for report
        output = mock_stdout.getvalue()
        assert "Overall accuracy: 100.0%" in output
        assert "File used:" in output

def test_cli_missing_item_description(tmp_path):
    # Prepare input CSV missing item_description
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    df = pd.DataFrame({
        "wrong_column": ["apple"]
    })
    df.to_csv(input_csv, index=False)

    with patch("sys.stderr", new=io.StringIO()) as mock_stderr, \
         patch("sys.argv", ["inflation-classifier", str(input_csv), str(output_csv)]):
        
        with pytest.raises(SystemExit) as e:
            main()
        
        assert e.value.code != 0
        assert "missing 'item_description' column" in mock_stderr.getvalue().lower()

def test_cli_category_column_exists(tmp_path):
    # Prepare input CSV where last column is already 'category'
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    df = pd.DataFrame({
        "item_description": ["apple"],
        "category": ["Food"]
    })
    df.to_csv(input_csv, index=False)

    with patch("sys.stderr", new=io.StringIO()) as mock_stderr, \
         patch("sys.argv", ["inflation-classifier", str(input_csv), str(output_csv)]):
        
        with pytest.raises(SystemExit) as e:
            main()
        
        assert e.value.code != 0
        assert "already has a last column named 'category'" in mock_stderr.getvalue().lower()

def test_cli_missing_arguments():
    with patch("sys.stderr", new=io.StringIO()) as mock_stderr, \
         patch("sys.argv", ["inflation-classifier"]):
        
        with pytest.raises(SystemExit) as e:
            main()
        
        assert e.value.code != 0
        # argparse prints usage to stderr on error
        assert "the following arguments are required: input_csv, output_csv" in mock_stderr.getvalue()
