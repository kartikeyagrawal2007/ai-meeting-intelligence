# TODO: Implement JSON export
# 
# Export intelligence and analytics to structured JSON
# 
# Usage:
#   from output.export_json import export_to_json
#   export_to_json(intelligence, output_path)

import json
from utils.logger import get_logger

log = get_logger(__name__)

def export_to_json(data: dict, output_path: str):
    """Export intelligence data to JSON file."""
    log.info(f"Exporting to JSON: {output_path}")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    log.info("JSON export complete")
