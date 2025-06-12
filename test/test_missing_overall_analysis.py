#!/usr/bin/env python3
"""
Test case for when R script fails to create overall_analysis section
"""

import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Simulate R output JSON when there's an error (no overall_analysis)
r_output_json_with_error = {
    "r_version": "R version 4.3.1 (2023-06-16)",
    "metafor_version": "4.6-0",
    "analysis_environment": {
        "r_version_full": "R version 4.3.1 (2023-06-16)",
        "metafor_version": "4.6-0"
    },
    "error_in_summary_generation": "Error creating parts of summary: object 'res' not found",
    "generated_plots_paths": []
}

logger.info("=== R Output JSON with Error (no overall_analysis) ===")
logger.info(json.dumps(r_output_json_with_error, indent=2))

# Simulate analysis_handler.py processing
logger.info("\n=== Processing in analysis_handler.py ===")
full_r_summary = r_output_json_with_error.copy()
r_summary_for_metadata = full_r_summary.copy()

if "overall_analysis" in full_r_summary:
    logger.info("overall_analysis found, updating top level")
    # ... update logic ...
else:
    logger.warning("overall_analysis NOT found in R output!")

# Simulate slack_utils.py processing
display_result_for_blocks = {
    "summary": r_summary_for_metadata,
    "r_log": "Sample R log with errors"
}

summary = display_result_for_blocks.get("summary", {})
logger.info(f"\nsummary keys: {list(summary.keys())}")

# Extract values
pooled_effect = summary.get('estimate', 'N/A')
ci_lower = summary.get('ci_lb', 'N/A')
ci_upper = summary.get('ci_ub', 'N/A')
i2_value = summary.get('I2', 'N/A')
num_studies = summary.get('k', 'N/A')

logger.info(f"\nExtracted values:")
logger.info(f"  pooled_effect: {pooled_effect}")
logger.info(f"  ci_lower: {ci_lower}")
logger.info(f"  ci_upper: {ci_upper}")
logger.info(f"  i2_value: {i2_value}")
logger.info(f"  num_studies: {num_studies}")

logger.info("\n=== Result ===")
if pooled_effect == 'N/A':
    logger.error("❌ This scenario would cause N/A values to be displayed!")
    logger.info("Error message in R output: " + r_output_json_with_error.get("error_in_summary_generation", "None"))
else:
    logger.info("✓ Values extracted successfully")