import pytest
import os
import pandas as pd
import json
from piicalculator.calculator import get_max_file_size, pii_calculator, CATEGORIES

def create_sample_csv(path, rows):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)

def test_get_max_file_size_default():
    if "MAXCSVFILESIZE" in os.environ:
        del os.environ["MAXCSVFILESIZE"]
    assert get_max_file_size() == 20

def test_get_max_file_size_custom():
    os.environ["MAXCSVFILESIZE"] = "100"
    try:
        assert get_max_file_size() == 100
    finally:
        del os.environ["MAXCSVFILESIZE"]

def test_pii_calculator_file_not_found(capsys):
    with pytest.raises(SystemExit) as e:
        pii_calculator("non_existent.csv", "out.json")
    
    captured = capsys.readouterr()
    assert "Local file does not exist" in captured.err
    assert e.value.code == 1

def test_pii_calculator_file_too_large(tmp_path, capsys):
    csv_file = tmp_path / "large.csv"
    with open(csv_file, "wb") as f:
        f.write(b"a" * (1024 * 1024 + 1)) # 1MB + 1 byte
    
    os.environ["MAXCSVFILESIZE"] = "1"
    try:
        with pytest.raises(SystemExit) as e:
            pii_calculator(str(csv_file), "out.json")
        
        captured = capsys.readouterr()
        assert "File size exceeds the maximum allowed limit of 1MB" in captured.err
        assert e.value.code == 1
    finally:
        del os.environ["MAXCSVFILESIZE"]

def test_pii_calculator_missing_columns(tmp_path, capsys):
    csv_file = tmp_path / "missing_cols.csv"
    create_sample_csv(csv_file, [{"date": "2024-01-01", "total_price": 100}])
    
    with pytest.raises(SystemExit) as e:
        pii_calculator(str(csv_file), "out.json")
    
    captured = capsys.readouterr()
    assert "Missing required columns" in captured.err
    assert e.value.code == 1

def test_pii_calculator_too_little_data(tmp_path, capsys):
    csv_file = tmp_path / "little_data.csv"
    rows = [
        {"date": "2024-01-01", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-02-01", "item_description": "b", "total_price": 100, "category": "Housing"},
        {"date": "2024-03-01", "item_description": "c", "total_price": 100, "category": "Housing"},
    ]
    create_sample_csv(csv_file, rows)
    
    with pytest.raises(SystemExit) as e:
        pii_calculator(str(csv_file), "out.json")
    
    captured = capsys.readouterr()
    assert "There is too little data for computing inflation" in captured.err
    assert e.value.code == 1

def test_pii_calculator_valid_data(tmp_path, capsys):
    csv_file = tmp_path / "valid.csv"
    # We need at least 4 contiguous months.
    # We'll use 6 months so that we have 4 months in the period (excluding first and last).
    rows = []
    for month in range(1, 7):
        date = f"2024-{month:02d}-01"
        for cat in [
            "Housing", "Food and Beverages", "Transportation", "Medical Care",
            "Energy", "Household Furnishings and Operations", "Apparel",
            "Recreation, Education, and Communication"
        ]:
            # Simple linear growth for inflation: spend = 100 * (1 + 0.01 * month)
            # Log(spend) = log(100) + log(1 + 0.01 * month) approx log(100) + 0.01 * month
            # Slope = 0.01. Annualized = 0.01 * 12 * 100 = 12%
            rows.append({
                "date": date,
                "item_description": f"item_{month}_{cat}",
                "total_price": 100.0 * (1.1 ** month), # Exponential growth for constant log slope
                "category": cat
            })
    create_sample_csv(csv_file, rows)
    
    output_file = tmp_path / "result.json"
    pii_calculator(str(csv_file), str(output_file))
    
    with open(output_file, 'r') as f:
        result = json.load(f)
    
    assert result["schema_version"] == "1.0"
    assert "generatedAt" in result
    assert result["period"]["start"] == "2024-02"
    assert result["period"]["end"] == "2024-05"
    assert "pii" in result["summary"]
    # 1.1^month => ln(spend) = month * ln(1.1). Slope = ln(1.1).
    # Annualized = ln(1.1) * 12 * 100 = 0.09531 * 12 * 100 = 114.372%
    assert result["summary"]["pii"] > 0

def test_pii_calculator_not_contiguous(tmp_path, capsys):
    csv_file = tmp_path / "not_contiguous.csv"
    rows = [
        {"date": "2024-01-01", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-02-01", "item_description": "b", "total_price": 100, "category": "Housing"},
        {"date": "2024-03-01", "item_description": "c", "total_price": 100, "category": "Housing"},
        {"date": "2024-05-01", "item_description": "d", "total_price": 100, "category": "Housing"},
    ]
    create_sample_csv(csv_file, rows)
    
    with pytest.raises(SystemExit) as e:
        pii_calculator(str(csv_file), "out.json")
    
    captured = capsys.readouterr()
    assert "There is too little data for computing inflation" in captured.err
    assert e.value.code == 1

def test_pii_calculator_invalid_date(tmp_path, capsys):
    csv_file = tmp_path / "invalid_date.csv"
    rows = [
        {"date": "invalid", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-02-01", "item_description": "b", "total_price": 100, "category": "Housing"},
        {"date": "2024-03-01", "item_description": "c", "total_price": 100, "category": "Housing"},
        {"date": "2024-04-01", "item_description": "d", "total_price": 100, "category": "Housing"},
    ]
    create_sample_csv(csv_file, rows)
    
    with pytest.raises(SystemExit) as e:
        pii_calculator(str(csv_file), "out.json")
    
    captured = capsys.readouterr()
    assert "Error parsing dates" in captured.err

def test_pii_calculator_zero_total_spend(tmp_path, capsys):
    csv_file = tmp_path / "zero_spend.csv"
    rows = []
    for month in range(1, 6):
         rows.append({"date": f"2024-{month:02d}-01", "item_description": "a", "total_price": 0.0, "category": "Housing"})
    create_sample_csv(csv_file, rows)
    
    output_file = tmp_path / "result.json"
    pii_calculator(str(csv_file), str(output_file))
    with open(output_file, 'r') as f:
        result = json.load(f)
    assert result["summary"]["pii"] == 0.0

def test_pii_calculator_insufficient_data_for_regression(tmp_path, capsys):
    csv_file = tmp_path / "low_data_regression.csv"
    # Only 1 month has data for Housing, others have 0.
    rows = [
        {"date": "2024-01-01", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-02-01", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-03-01", "item_description": "a", "total_price": 0, "category": "Housing"},
        {"date": "2024-04-01", "item_description": "a", "total_price": 0, "category": "Housing"},
        {"date": "2024-05-01", "item_description": "a", "total_price": 0, "category": "Housing"},
    ]
    # Period will be 2024-02 to 2024-04.
    # In this period, only 2024-02 has spend > 0.
    create_sample_csv(csv_file, rows)
    
    output_file = tmp_path / "result.json"
    pii_calculator(str(csv_file), str(output_file))
    with open(output_file, 'r') as f:
        result = json.load(f)
    assert result["summary"]["pii"] == 0.0

def test_pii_calculator_s3_path(mocker, capsys, tmp_path):
    # Mock pandas read_csv to avoid real S3 call
    mock_read = mocker.patch("pandas.read_csv")
    df = pd.DataFrame([
        {"date": "2024-01-01", "item_description": "a", "total_price": 100, "category": "Housing"},
        {"date": "2024-02-01", "item_description": "b", "total_price": 100, "category": "Housing"},
        {"date": "2024-03-01", "item_description": "c", "total_price": 100, "category": "Housing"},
        {"date": "2024-04-01", "item_description": "d", "total_price": 100, "category": "Housing"},
    ])
    mock_read.return_value = df
    
    output_file = tmp_path / "out.json"
    # We just want to check if it passes the s3:// check and proceeds
    pii_calculator("s3://bucket/file.csv", str(output_file))
    
    mock_read.assert_called_once_with("s3://bucket/file.csv")
    assert output_file.exists()

def test_pii_calculator_read_csv_error(tmp_path, capsys):
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text("invalid csv content")
    # Actually, pandas might still read it, but let's try to trigger an error by passing a directory
    
    with pytest.raises(SystemExit) as e:
        pii_calculator(str(tmp_path), "out.json")
    
    captured = capsys.readouterr()
    assert "Error reading CSV" in captured.err

def test_error_json_format(tmp_path, capsys):
    # Trigger a "too little data" error
    csv_file = tmp_path / "too_little.csv"
    create_sample_csv(csv_file, [{"date": "2024-01-01", "item_description": "a", "total_price": 100, "category": "Housing"}])
    
    with pytest.raises(SystemExit):
        pii_calculator(str(csv_file), "out.json")
    
    captured = capsys.readouterr()
    # stdout may contain progress messages, but the last line should be the JSON error
    lines = captured.out.strip().split('\n')
    error_json = json.loads(lines[-1])
    
    assert "generatedAt" in error_json
    assert "message" in error_json
    assert "_links" in error_json
    assert error_json["_links"]["self"]["href"] == "/pii-summary"
    assert error_json["_links"]["spending-history"]["href"] == "/spending-history"
    assert error_json["_links"]["welcome"]["href"] == "/"

def test_row_order_independence(tmp_path, capsys):
    # Create data for 6 months
    rows = []
    for month in range(1, 7):
        for cat in CATEGORIES:
            rows.append({
                "date": f"2024-{month:02d}-01",
                "item_description": "item",
                "total_price": 100.0 * (1.05 ** month),
                "category": cat
            })
    
    csv_ordered = tmp_path / "ordered.csv"
    create_sample_csv(csv_ordered, rows)
    
    out_ordered = tmp_path / "ordered.json"
    pii_calculator(str(csv_ordered), str(out_ordered))
    with open(out_ordered, 'r') as f:
        res_ordered = json.load(f)
    
    # Shuffle rows
    import random
    random.seed(42)
    shuffled_rows = rows[:]
    random.shuffle(shuffled_rows)
    
    csv_shuffled = tmp_path / "shuffled.csv"
    create_sample_csv(csv_shuffled, shuffled_rows)
    
    out_shuffled = tmp_path / "shuffled.json"
    pii_calculator(str(csv_shuffled), str(out_shuffled))
    with open(out_shuffled, 'r') as f:
        res_shuffled = json.load(f)
    
    # pii should be the same
    assert res_ordered["summary"]["pii"] == res_shuffled["summary"]["pii"]
    assert res_ordered["period"] == res_shuffled["period"]

def test_missing_month_in_middle(tmp_path, capsys):
    # Months: Jan, Feb, Mar, Apr, May, Jul, Aug, Sep, Oct
    # 5 contiguous (Jan-May), then skip Jun, then 4 contiguous (Jul-Oct)
    rows = []
    for month in [1, 2, 3, 4, 5, 7, 8, 9, 10]:
        for cat in CATEGORIES:
            rows.append({
                "date": f"2024-{month:02d}-01",
                "item_description": "item",
                "total_price": 100.0,
                "category": cat
            })
    
    csv_file = tmp_path / "missing_month.csv"
    create_sample_csv(csv_file, rows)
    
    out_file = tmp_path / "result.json"
    pii_calculator(str(csv_file), str(out_file))
    with open(out_file, 'r') as f:
        result = json.load(f)
    
    # Period should be Feb to Sep
    assert result["period"]["start"] == "2024-02"
    assert result["period"]["end"] == "2024-09"
    # pii should be 0 since spend is constant (even with missing Jun, 
    # Jun is treated as 0 spend, so it might actually introduce a dip and then jump, 
    # but for OLS if most points are 100 and one is 0, the slope might not be 0.
    # Actually if Jun is 0, it is EXCLUDED from regression in current implementation:
    # 135: valid_indices = Y_raw > 0
    # So Jun will be skipped, and regression will see all other months (all 100).
    # Slope will be 0.
    assert result["summary"]["pii"] == 0.0

def test_all_categories_handled(tmp_path, capsys, mocker):
    # We want to verify that all 8 categories are considered even if not in CSV
    # We'll provide only Housing data
    rows = []
    for month in range(1, 7):
        rows.append({
            "date": f"2024-{month:02d}-01",
            "item_description": "item",
            "total_price": 100.0 * (1.05 ** month),
            "category": "Housing"
        })
    
    csv_file = tmp_path / "only_housing.csv"
    create_sample_csv(csv_file, rows)
    
    # Use a spy or mock to check internal weights if possible? 
    # Or just rely on the fact that it doesn't crash and pii is calculated.
    # The weight for Housing should be 1.0, others 0.0.
    # Inflation for Housing should be approx 12 * 100 * ln(1.05) = 1200 * 0.04879 = 58.548
    # Overall pii should be 58.548.
    
    out_file = tmp_path / "result.json"
    pii_calculator(str(csv_file), str(out_file))
    with open(out_file, 'r') as f:
        result = json.load(f)
    
    import numpy as np
    expected_slope = np.log(1.05)
    expected_pii = round(expected_slope * 12 * 100, 4)
    
    assert result["summary"]["pii"] == expected_pii

def test_pii_calculator_with_output_file(tmp_path, capsys):
    csv_file = tmp_path / "input.csv"
    rows = []
    for month in range(1, 7):
        rows.append({
            "date": f"2024-{month:02d}-01",
            "item_description": "a",
            "total_price": 100.0,
            "category": "Housing"
        })
    create_sample_csv(csv_file, rows)
    
    output_file = tmp_path / "output.json"
    
    pii_calculator(str(csv_file), str(output_file))
    
    # Check stdout for progress
    captured = capsys.readouterr()
    assert "Writing result to" in captured.out
    assert "Done." in captured.out
    # JSON should NOT be in stdout
    assert '"schema_version": "1.0"' not in captured.out
    
    # Check output file content
    assert output_file.exists()
    with open(output_file, 'r') as f:
        result = json.load(f)
    assert result["summary"]["pii"] == 0.0
