import pytest
from unittest.mock import patch
from piicalculator.lambda_handler import handler
from piicalculator.errors import PIICalculatorError

def test_handler_missing_input_s3_uri():
    event = {"output-s3-uri": "s3://bucket/123/out.json"}
    with pytest.raises(ValueError, match="Missing 'input-s3-uri'"):
        handler(event, None)

def test_handler_missing_output_s3_uri():
    event = {"input-s3-uri": "s3://bucket/123/in.csv"}
    with pytest.raises(ValueError, match="Missing 'output-s3-uri'"):
        handler(event, None)

def test_handler_malformed_input_s3_uri():
    event = {
        "input-s3-uri": "not-s3://bucket/123/in.csv",
        "output-s3-uri": "s3://bucket/123/out.json"
    }
    with pytest.raises(ValueError, match="Invalid input-s3-uri"):
        handler(event, None)

def test_handler_malformed_output_s3_uri():
    event = {
        "input-s3-uri": "s3://bucket/123/in.csv",
        "output-s3-uri": "bucket/123/out.json"
    }
    with pytest.raises(ValueError, match="Invalid output-s3-uri"):
        handler(event, None)

def test_handler_ticket_mismatch():
    event = {
        "input-s3-uri": "s3://bucket/123/in.csv",
        "output-s3-uri": "s3://bucket/456/out.json"
    }
    with pytest.raises(ValueError, match="Ticket number mismatch"):
        handler(event, None)

def test_handler_success(mocker):
    mock_calc = mocker.patch("piicalculator.lambda_handler.pii_calculator")
    event = {
        "input-s3-uri": "s3://pii-input/123456789/classified.csv",
        "output-s3-uri": "s3://pii-output/123456789/pii-report.json"
    }
    
    result = handler(event, None)
    
    mock_calc.assert_called_once_with(
        "s3://pii-input/123456789/classified.csv",
        "s3://pii-output/123456789/pii-report.json"
    )
    
    assert result == {
        "ticket": "123456789",
        "status": "SUCCEEDED",
        "output-s3-uri": "s3://pii-output/123456789/pii-report.json"
    }

def test_handler_calculator_error(mocker):
    mocker.patch("piicalculator.lambda_handler.pii_calculator", 
                 side_effect=PIICalculatorError("Calc failed"))
    mock_write = mocker.patch("piicalculator.lambda_handler.write_json")
    
    event = {
        "input-s3-uri": "s3://pii-input/1234/classified.csv",
        "output-s3-uri": "s3://pii-output/1234/pii-report.json"
    }
    
    with pytest.raises(PIICalculatorError, match="Calc failed"):
        handler(event, None)
    
    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    assert args[0]["message"] == "Calc failed"
    assert args[1] == "s3://pii-output/1234/pii-report.json"

def test_handler_unexpected_error(mocker):
    mocker.patch("piicalculator.lambda_handler.pii_calculator", 
                 side_effect=Exception("Boom"))
    mock_write = mocker.patch("piicalculator.lambda_handler.write_json")
    
    event = {
        "input-s3-uri": "s3://pii-input/1234/classified.csv",
        "output-s3-uri": "s3://pii-output/1234/pii-report.json"
    }
    
    with pytest.raises(Exception, match="Boom"):
        handler(event, None)
        
    mock_write.assert_called_once()
    args, _ = mock_write.call_args
    assert "Boom" in args[0]["message"]
    assert args[1] == "s3://pii-output/1234/pii-report.json"
