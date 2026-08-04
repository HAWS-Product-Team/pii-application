import pytest
from unittest.mock import patch, MagicMock
from inflation_classifier.classifier import setup_model, run_inference

def test_setup_model():
    with patch("inflation_classifier.classifier.pipeline") as mock_pipeline:
        mock_classifier = MagicMock()
        mock_pipeline.return_value = mock_classifier
        
        classifier, categories = setup_model()
        
        assert classifier == mock_classifier
        assert len(categories) == 8
        mock_pipeline.assert_called_once_with(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device="cpu"  # default
        )

def test_run_inference():
    mock_classifier = MagicMock()
    items = ["item1", "item2"]
    categories = ["cat1", "cat2"]
    
    mock_classifier.return_value = [
        {"labels": ["cat1", "cat2"], "scores": [0.9, 0.1]},
        {"labels": ["cat2", "cat1"], "scores": [0.8, 0.2]}
    ]
    
    predictions, duration = run_inference(mock_classifier, items, categories)
    
    assert predictions == ["cat1", "cat2"]
    assert isinstance(duration, float)
    mock_classifier.assert_called_once_with(items, candidate_labels=categories, multi_label=False)
