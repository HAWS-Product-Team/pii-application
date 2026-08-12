import io
import sys
import pytest
from unittest.mock import patch, MagicMock
from inflation_classifier.classifier import setup_model, run_inference

def test_setup_model():
    with patch("inflation_classifier.classifier.pipeline") as mock_pipeline, \
         patch("sys.stdout", new=io.StringIO()) as mock_stdout:
        mock_classifier = MagicMock()
        mock_pipeline.return_value = mock_classifier
        
        classifier, categories = setup_model()
        
        assert classifier == mock_classifier
        assert len(categories) == 8
        assert all("," not in c for c in categories)
        assert "Recreation Education and Communication" in categories
        mock_pipeline.assert_called_once_with(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device="cpu"  # default
        )
        
        # Verify logs go to stdout
        output = mock_stdout.getvalue()
        assert "loading model" in output
        assert "model loaded" in output

def test_run_inference():
    mock_classifier = MagicMock()
    items = ["item1", "item2"]
    categories = ["cat1", "cat2"]
    
    mock_classifier.return_value = [
        {"labels": ["cat1", "cat2"], "scores": [0.9, 0.1]},
        {"labels": ["cat2", "cat1"], "scores": [0.8, 0.2]}
    ]
    
    with patch("sys.stdout", new=io.StringIO()) as mock_stdout:
        predictions, duration = run_inference(mock_classifier, items, categories)
        
        assert predictions == ["cat1", "cat2"]
        assert isinstance(duration, float)
        mock_classifier.assert_called_once_with(items, candidate_labels=categories, multi_label=False)
        
        # Verify logs go to stdout
        output = mock_stdout.getvalue()
        assert "starting inference" in output
        assert "finished inference" in output
