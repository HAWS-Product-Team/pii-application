import time
import pandas as pd
from transformers import pipeline


def setup_model():
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
    return classifier, categories


def run_inference(classifier, items, categories):
    # Run inference
    # multi_label=False means it picks exactly one category (what you want)
    start_time = time.perf_counter()
    results = classifier(items, candidate_labels=categories, multi_label=False)
    end_time = time.perf_counter()
    duration = end_time - start_time

    # Extract top prediction
    predictions = [r["labels"][0] for r in results]
    return predictions, duration


def report_results(df, csv_name, duration):
    # Evaluate
    df["correct"] = df["predicted"] == df["category"]

    print(f"File used: {csv_name}")
    print(f"Number of items: {len(df)}")
    print(f"Inference duration: {duration:.2f} seconds")
    print(f"Average inference time per item: {duration / len(df):.4f} seconds")

    # Overall accuracy
    overall = df["correct"].mean()
    print(f"Overall accuracy: {overall:.1%}")

    # Accuracy by difficulty
    print("\nBy difficulty:")
    print(df.groupby("difficulty")["correct"].mean().map("{:.1%}".format))

    # Accuracy by category
    print("\nBy category:")
    print(df.groupby("category")["correct"].mean().map("{:.1%}".format))

    # Spot check failures
    print("\nMisclassified hard examples:")
    failures = df[(df["difficulty"] == "hard") & (~df["correct"])]
    print(failures[["item_description", "category", "predicted"]].to_string())


def main():
    # Load your CSV
    csv_path = "../tests/data/small test set/synthetic_purchases_2024.csv"
    df = pd.read_csv(csv_path)

    # Drop category/difficulty to simulate inference
    items = df["item_description"].tolist()

    classifier, categories = setup_model()

    predictions, duration = run_inference(classifier, items, categories)
    df["predicted"] = predictions

    report_results(df, csv_path, duration)


if __name__ == "__main__":
    main()