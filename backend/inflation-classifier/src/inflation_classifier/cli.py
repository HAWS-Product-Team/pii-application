import sys
import pandas as pd
import argparse
from inflation_classifier.classifier import setup_model, run_inference
from inflation_classifier.io import read_input

def report_results(df, csv_name, duration, show_all_failures=False):
    # Check if we have what we need for evaluation
    required_cols = ["category", "difficulty"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing columns for evaluation: {', '.join(missing_cols)}", file=sys.stderr)
        sys.exit(1)

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

def main():
    parser = argparse.ArgumentParser(
        description="""
Inflation-classifier categorizes spending data into 8 Consumer Price Index (CPI) categories:
Housing, Food and Beverages, Transportation, Medical Care, Energy,
Household Furnishings and Operations, Apparel, and Recreation Education and Communication.

The tool processes a CSV file, using the 'item_description' column to perform classification.
By default, it outputs the original CSV data plus a new 'category' column to stdout.

Inference runs on the CPU by default.  You chang change with the environment variable INFERENCE_DEVICE to
the following '0' uses GPU if available, '-1' is cpu, 'cpu', 'mps' Apple Silicon, 'cuda', 'cuda:0'.  
For example, use: $ INFERENCE_DEVICE=mps uv run inflation-classifier <input.csv>
to run the model on an Apple M1/M2 chip.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "csv_path",
        help="Path to the CSV file for classification. Supports local and S3 paths (e.g., s3://bucket/path/to/file.csv).",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Output evaluation summary instead of classifying each row.",
    )
    parser.add_argument(
        "--list-wrong",
        action="store_true",
        help="Output the entire list of item descriptions the classifier got wrong (requires --evaluate).",
    )
    args = parser.parse_args()

    # Load your input (local or S3)
    csv_path = args.csv_path
    try:
        df = read_input(csv_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validation
    if "item_description" not in df.columns:
        print("Error: Input CSV is missing 'item_description' column.", file=sys.stderr)
        sys.exit(1)

    if not args.evaluate:
        if df.columns[-1] == "category":
            print("Error: Input CSV already has a last column named 'category'.", file=sys.stderr)
            sys.exit(1)

    # Get items for inference
    items = df["item_description"].tolist()

    classifier, categories = setup_model()

    predictions, duration = run_inference(classifier, items, categories)
    
    if args.evaluate:
        df["predicted"] = predictions
        report_results(df, csv_path, duration, show_all_failures=args.list_wrong)
    else:
        df["category"] = predictions
        # Write valid CSV to stdout
        print(df.to_csv(index=False), end="")


if __name__ == "__main__":
    main()