import pytest
import sys
from piicalculator.cli import main
from unittest.mock import patch

def test_cli_no_args(capsys):
    with patch.object(sys, 'argv', ['pii-calculator']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert "usage: pii-calculator" in captured.out

def test_cli_with_arg(mocker):
    mock_calc = mocker.patch("piicalculator.cli.pii_calculator")
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv']):
        main()
    mock_calc.assert_called_once_with('test.csv')

def test_cli_unexpected_error(mocker, capsys):
    mocker.patch("piicalculator.cli.pii_calculator", side_effect=Exception("Boom"))
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
    
    captured = capsys.readouterr()
    assert "An unexpected error occurred: Boom" in captured.err

def test_cli_system_exit(mocker):
    mocker.patch("piicalculator.cli.pii_calculator", side_effect=SystemExit(1))
    with patch.object(sys, 'argv', ['pii-calculator', 'test.csv']):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
