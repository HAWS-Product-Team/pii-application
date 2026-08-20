import logging
from piicalculator.calculator import pii_calculator
from piicalculator.errors import PIICalculatorError, get_error_data, write_json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def parse_s3_uri(uri):
    """Parse s3://bucket/key into (bucket, key)."""
    if not uri.startswith("s3://"):
        return None, None
    
    parts = uri[5:].split("/", 1)
    if len(parts) < 2:
        return parts[0], ""
    return parts[0], parts[1]

def extract_ticket(key):
    """Extract ticket number from S3 key. Ticket is the first part of the path."""
    if not key:
        return None
    parts = key.split("/")
    return parts[0]

def handler(event, context):
    logger.info(f"Received event: {event}")
    
    input_uri = event.get("input-s3-uri")
    output_uri = event.get("output-s3-uri")
    
    if not input_uri:
        raise ValueError("Missing 'input-s3-uri' in event")
    if not output_uri:
        raise ValueError("Missing 'output-s3-uri' in event")
    
    in_bucket, in_key = parse_s3_uri(input_uri)
    out_bucket, out_key = parse_s3_uri(output_uri)
    
    if not in_bucket or not in_key:
        raise ValueError(f"Invalid input-s3-uri: {input_uri}")
    if not out_bucket or not out_key:
        raise ValueError(f"Invalid output-s3-uri: {output_uri}")
    
    in_ticket = extract_ticket(in_key)
    out_ticket = extract_ticket(out_key)
    
    if not in_ticket:
        raise ValueError(f"Could not extract ticket number from input-s3-uri: {input_uri}")
    if not out_ticket:
        raise ValueError(f"Could not extract ticket number from output-s3-uri: {output_uri}")
    
    if in_ticket != out_ticket:
        raise ValueError(f"Ticket number mismatch: {in_ticket} vs {out_ticket}")
    
    try:
        pii_calculator(input_uri, output_uri)
    except PIICalculatorError as e:
        logger.error(f"PIICalculation failed: {e}")
        try:
            error_data = get_error_data(str(e))
            write_json(error_data, output_uri)
        except Exception as write_err:
            logger.error(f"Failed to write error report to {output_uri}: {write_err}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        try:
            error_data = get_error_data(f"An unexpected error occurred: {e}")
            write_json(error_data, output_uri)
        except Exception as write_err:
            logger.error(f"Failed to write error report to {output_uri}: {write_err}")
        raise
        
    return {
        "ticket": in_ticket,
        "status": "SUCCEEDED",
        "output-s3-uri": output_uri
    }
