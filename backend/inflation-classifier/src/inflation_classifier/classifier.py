import time
from transformers import pipeline

def setup_model():
    print("loading model")
    # Your category labels
    categories = [
        "Housing",
        "Food and Beverages",
        "Transportation",
        "Medical Care",
        "Energy",
        "Household Furnishings and Operations",
        "Apparel",
        "Recreation, Education, and Communication",
    ]

    # Load the zero-shot pipeline
    # device=0 uses GPU if available, remove or set device="cpu" to force CPU
    classifier = pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli",
        device=0  # or "mps" on Apple Silicon, or "cpu"
    )
    print("model loaded")
    return classifier, categories

def run_inference(classifier, items, categories):
    print("starting inference")
    # Run inference
    # multi_label=False means it picks exactly one category (what you want)
    start_time = time.perf_counter()
    results = classifier(items, candidate_labels=categories, multi_label=False)
    end_time = time.perf_counter()
    print("finished inference")

    duration = end_time - start_time

    # Extract top prediction
    predictions = [r["labels"][0] for r in results]
    return predictions, duration
