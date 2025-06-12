#!/usr/bin/env python3
"""
Test script to verify R template fixes for continuous outcomes and other measures
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from templates.r_templates import RTemplateGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_template_generation():
    generator = RTemplateGenerator()
    
    # Test cases for different measure types
    test_cases = [
        {
            "name": "Continuous outcome (SMD)",
            "params": {
                "measure": "SMD",
                "model": "REML",
                "data_columns": {
                    "n1i": "n_treatment",
                    "n2i": "n_control",
                    "m1i": "mean_treatment",
                    "m2i": "mean_control",
                    "sd1i": "sd_treatment",
                    "sd2i": "sd_control"
                }
            }
        },
        {
            "name": "Proportion (PLO)",
            "params": {
                "measure": "PLO",
                "model": "REML",
                "data_columns": {
                    "proportion_events": "events",
                    "proportion_total": "total"
                }
            }
        },
        {
            "name": "Correlation (COR)",
            "params": {
                "measure": "COR",
                "model": "REML",
                "data_columns": {
                    "ri": "correlation",
                    "ni": "sample_size"
                }
            }
        },
        {
            "name": "Pre-calculated (PRE)",
            "params": {
                "measure": "PRE",
                "model": "REML",
                "data_columns": {
                    "yi": "effect_size",
                    "vi": "variance"
                }
            }
        }
    ]
    
    for test_case in test_cases:
        logger.info(f"\n=== Testing: {test_case['name']} ===")
        
        try:
            # Generate escalc code
            escalc_code = generator._generate_escalc_code(
                test_case['params'],
                {"columns": list(test_case['params']['data_columns'].values())}
            )
            
            logger.info(f"Generated R code:\n{escalc_code}")
            
            # Check if res <- rma() is present
            if "res <- rma(" in escalc_code:
                logger.info("✓ Found 'res <- rma()' - analysis should work correctly")
            else:
                logger.error("✗ Missing 'res <- rma()' - this would cause N/A values!")
                
            # Check if res_for_plot is set
            if "res_for_plot <- res" in escalc_code:
                logger.info("✓ Found 'res_for_plot <- res' - plots should work correctly")
            else:
                logger.warning("⚠ Missing 'res_for_plot <- res' - plots might fail")
                
        except Exception as e:
            logger.error(f"✗ Error generating template: {e}")

if __name__ == "__main__":
    test_template_generation()