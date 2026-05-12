import sys
import pandas as pd
import argparse
from inflation_classifier.classifier import setup_model, run_inference
from inflation_classifier.io import read_input

def report_results(df, csv_name, duration, show_all_failures=False):
    # Evaluate
    df["correct"] = df["predicted"] == df["category"]

    print(f"File used: {csv_name}")
    print(f"Number of items: {len(df)}")
    print(f"Inference duration: {duration:.2f} seconds")
    print(f"Average inference time per item: {duration / len(df) * 1000:.2f} milliseconds")

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

    if show_all_failures:
        print("\nAll misclassified item descriptions:")
        all_failures = df[df["predicted"] != df["category"]]
        print(all_failures[["item_description", "category", "predicted"]].to_string())
        #for _, row in all_failures.iterrows():
        #    print(f"{row['item_description']} {row['category']} {row['predicted']}")

def main():
    parser = argparse.ArgumentParser(description="Classify item descriptions into inflation categories.")
    parser.add_argument(
        "csv_path",
        help="Path to the CSV file for classification. Supports local and S3 paths (e.g., s3://bucket/path/to/file.csv).",
    )
    parser.add_argument(
        "--list-wrong",
        action="store_true",
        help="Output the entire list of item descriptions the classifier got wrong.",
    )
    args = parser.parse_args()

    # Load your input (local or S3)
    csv_path = args.csv_path
    try:
        df = read_input(csv_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Drop category/difficulty to simulate inference
    items = df["item_description"].tolist()

    classifier, categories = setup_model()

    predictions, duration = run_inference(classifier, items, categories)
    df["predicted"] = predictions

    report_results(df, csv_path, duration, show_all_failures=args.list_wrong)


if __name__ == "__main__":
    main()