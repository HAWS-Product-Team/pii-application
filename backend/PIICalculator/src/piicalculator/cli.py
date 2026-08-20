import argparse
from piicalculator.calculator import pii_calculator
from piicalculator.errors import report_error, PIICalculatorError

def main():
    parser = argparse.ArgumentParser(description="PII Calculator")
    parser.add_argument("csv_path", help="Path to the input CSV file (local or s3://)")
    parser.add_argument(
        "output_path",
        help="Path to the output JSON file (local or s3://)."
    )
    
    args = parser.parse_args()
    
    try:
        pii_calculator(args.csv_path, args.output_path)
    except PIICalculatorError as e:
        report_error(str(e))
    except SystemExit:
        # Already handled
        raise
    except Exception as e:
        report_error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
