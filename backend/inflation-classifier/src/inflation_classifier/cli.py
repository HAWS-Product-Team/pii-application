import pandas as pd
from transformers import pipeline


def main():
    # Load your CSV
    df = pd.read_csv("../tests/data/small test set/synthetic_purchases_2024.csv")

    # Drop category/difficulty to simulate inference
    items = df["item_description"].tolist()
    ground_truth = df["category"].tolist()

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

    # Run inference
    # multi_label=False means it picks exactly one category (what you want)
    results = classifier(items, candidate_labels=categories, multi_label=False)

    # Extract top prediction
    predictions = [r["labels"][0] for r in results]

    # Evaluate
    df["predicted"] = predictions
    df["correct"] = df["predicted"] == df["category"]

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

if __name__ == "__main__":
    main()