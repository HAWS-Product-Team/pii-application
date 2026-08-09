import os
import time
import sys
from transformers import pipeline

def setup_model():
    print("loading model", file=sys.stderr)
    # Your category labels
    categories = [
        "Housing",
        "Food and Beverages",
        "Transportation",
        "Medical Care",
        "Energy",
        "Household Furnishings and Operations",
        "Apparel",
        "Recreation Education and Communication",
    ]

    inf_device = os.environ.get("INFERENCE_DEVICE", "cpu")
    # Load the zero-shot pipeline
    # inf_device=0 uses GPU if available, -1 is cpu
    # also accepts strings: cpu, mps, cuda, cuda:0.
    classifier = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli",
        device=inf_device  # or "mps" on Apple Silicon, or "cpu"
    )
    print("model loaded", file=sys.stderr)
    return classifier, categories

def run_inference(classifier, items, categories):
    print("starting inference", file=sys.stderr)
    # Run inference
    # multi_label=False means it picks exactly one category (what you want)
    start_time = time.perf_counter()
    results = classifier(items, candidate_labels=categories, multi_label=False)
    end_time = time.perf_counter()
    print("finished inference", file=sys.stderr)

    duration = end_time - start_time

    # Extract top prediction
    predictions = [r["labels"][0] for r in results]
    return predictions, duration
