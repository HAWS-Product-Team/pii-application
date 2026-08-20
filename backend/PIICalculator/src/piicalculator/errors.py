import sys
import json
from datetime import datetime, timezone

class PIICalculatorError(Exception):
    """Base class for PII Calculator errors."""
    pass

def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def write_json(data, path):
    """Write data to a JSON file (local or S3)."""
    if path.startswith("s3://"):
        import s3fs
        fs = s3fs.S3FileSystem()
        with fs.open(path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

def get_error_data(message):
    """Generate error data structure."""
    return {
        "generatedAt": get_timestamp(),
        "message": message,
        "_links": {
            "self": {"href": "/pii-summary"},
            "spending-history": {"href": "/spending-history"},
            "welcome": {"href": "/"}
        }
    }

def report_error(message, output_path=None, exit_code=1):
    """Report error to stderr in human readable format and to stdout in JSON format."""
    print(message, file=sys.stderr)
    
    error_data = get_error_data(message)
    print(json.dumps(error_data))
    
    if output_path:
        try:
            write_json(error_data, output_path)
        except Exception as e:
            print(f"Error writing error JSON to {output_path}: {e}", file=sys.stderr)
            
    sys.exit(exit_code)
