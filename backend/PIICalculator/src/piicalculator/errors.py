import sys
import json
from datetime import datetime, timezone

class PIICalculatorError(Exception):
    """Base class for PII Calculator errors."""
    pass

def get_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def report_error(message, exit_code=1):
    """Report error to stderr in human readable format and to stdout in JSON format."""
    print(message, file=sys.stderr)
    
    error_data = {
        "generatedAt": get_timestamp(),
        "message": message,
        "_links": {
            "self": {"href": "/pii-summary"},
            "spending-history": {"href": "/spending-history"},
            "welcome": {"href": "/"}
        }
    }
    print(json.dumps(error_data))
    sys.exit(exit_code)
