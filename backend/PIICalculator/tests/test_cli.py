import pytest
import sys
from piicalculator.cli import main
from unittest.mock import patch

def test_cli_no_args(capsys):
    with patch.object(sys, 'argv', ['pii-calculator']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2
    
    captured = capsys.readouterr()
    assert "usage: pii-calculator" in captured.err

def test_cli_missing_output_arg(capsys):
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 2
    
    captured = capsys.readouterr()
    assert "usage: pii-calculator" in captured.err
    assert "the following arguments are required: output_path" in captured.err

def test_cli_with_two_args(mocker):
    mock_calc = mocker.patch("piicalculator.cli.pii_calculator")
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv', 'out.json']):
        main()
    mock_calc.assert_called_once_with('test.csv', 'out.json')

def test_cli_unexpected_error(mocker, capsys, tmp_path):
    mocker.patch("piicalculator.cli.pii_calculator", side_effect=Exception("Boom"))
    output_file = tmp_path / "error.json"
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv', str(output_file)]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert "An unexpected error occurred: Boom" in captured.err
    assert output_file.exists()

def test_cli_calculator_error(mocker, capsys, tmp_path):
    from piicalculator.errors import PIICalculatorError
    mocker.patch("piicalculator.cli.pii_calculator", side_effect=PIICalculatorError("Data too small"))
    output_file = tmp_path / "error.json"
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv', str(output_file)]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert "Data too small" in captured.err
    assert output_file.exists()
    import json
    with open(output_file, 'r') as f:
        data = json.load(f)
    assert data["message"] == "Data too small"

def test_cli_system_exit(mocker):
    mocker.patch("piicalculator.cli.pii_calculator", side_effect=SystemExit(1))
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv', 'out.json']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
