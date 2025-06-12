#!/usr/bin/env python3
"""
Debug script to trace JSON data flow from R output through Python processing
"""

import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Simulate R output JSON structure
r_output_json = {
    "r_version": "R version 4.3.1 (2023-06-16)",
    "metafor_version": "4.6-0",
    "analysis_environment": {
        "r_version_full": "R version 4.3.1 (2023-06-16)",
        "metafor_version": "4.6-0"
    },
    "overall_analysis": {
        "k": 10,
        "estimate": 1.45,
        "se": 0.15,
        "ci_lb": 1.12,
        "ci_ub": 1.88,
        "I2": 45.2,
        "method": "REML"
    },
    "zero_cells_summary": {
        "studies_with_zero_cells": 3,
        "double_zero_studies": 1,
        "intervention_zero_studies": 1,
        "control_zero_studies": 1
    },
    "generated_plots_paths": [
        {"label": "forest_plot", "path": "/tmp/forest_plot.png"}
    ]
}

logger.info("=== R Output JSON Structure ===")
logger.info(json.dumps(r_output_json, indent=2))

# Simulate analysis_handler.py processing (lines 162-193)
logger.info("\n=== Processing in analysis_handler.py ===")

# This simulates the code from analysis_handler.py
full_r_summary = r_output_json.copy()
r_summary_for_metadata = full_r_summary.copy()

# Log keys before processing
logger.info(f"Keys in full_r_summary: {list(full_r_summary.keys())}")

# Check for overall_analysis and update top level
if "overall_analysis" in full_r_summary:
    # Preserve version info
    version_info = {
        'r_version': full_r_summary.get('r_version'),
        'metafor_version': full_r_summary.get('metafor_version'),
        'analysis_environment': full_r_summary.get('analysis_environment')
    }
    
    logger.info(f"Preserving version info: r_version={version_info['r_version']}, metafor_version={version_info['metafor_version']}")
    
    # Update with overall_analysis fields
    r_summary_for_metadata.update(full_r_summary["overall_analysis"])
    
    # Restore version info
    r_summary_for_metadata['r_version'] = version_info['r_version']
    r_summary_for_metadata['metafor_version'] = version_info['metafor_version']
    if version_info['analysis_environment'] is not None:
        r_summary_for_metadata['analysis_environment'] = version_info['analysis_environment']
    
    logger.info(f"After restoration: r_version={r_summary_for_metadata.get('r_version')}, metafor_version={r_summary_for_metadata.get('metafor_version')}")

logger.info(f"\nKeys in r_summary_for_metadata after processing: {list(r_summary_for_metadata.keys())}")
logger.info(f"Sample values: estimate={r_summary_for_metadata.get('estimate')}, k={r_summary_for_metadata.get('k')}")

# Simulate passing to slack_utils.py
display_result_for_blocks = {
    "summary": r_summary_for_metadata,
    "r_log": "Sample R log output"
}

logger.info("\n=== Data passed to create_analysis_result_message ===")
logger.info(f"Keys in display_result_for_blocks: {list(display_result_for_blocks.keys())}")
logger.info(f"Keys in display_result_for_blocks['summary']: {list(display_result_for_blocks['summary'].keys())}")

# Simulate slack_utils.py processing
logger.info("\n=== Processing in slack_utils.py ===")
summary = display_result_for_blocks.get("summary", {})
logger.info(f"summary type: {type(summary)}")
logger.info(f"summary keys: {list(summary.keys())}")

# Extract values as done in create_analysis_result_message
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

# Check zero cells
zero_cells_summary = summary.get('zero_cells_summary')
logger.info(f"\nzero_cells_summary: {zero_cells_summary}")

# Check if values would show as N/A
logger.info("\n=== Analysis ===")
if pooled_effect == 'N/A':
    logger.error("pooled_effect is N/A - this would cause the issue!")
    logger.info("Checking if 'estimate' exists in summary...")
    if 'estimate' in summary:
        logger.info(f"  'estimate' exists with value: {summary['estimate']}")
    else:
        logger.error("  'estimate' NOT found in summary!")
        if 'overall_analysis' in summary:
            logger.info("  'overall_analysis' exists in summary")
            if isinstance(summary['overall_analysis'], dict) and 'estimate' in summary['overall_analysis']:
                logger.info(f"    'estimate' found in overall_analysis: {summary['overall_analysis']['estimate']}")
else:
    logger.info("✓ Values are being extracted correctly")