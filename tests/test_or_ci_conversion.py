#!/usr/bin/env python3
"""
Test script for OR/CI to lnOR/SE conversion functionality
"""

import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
from mcp_legacy.gemini_utils import map_csv_columns_to_meta_analysis_roles

def test_or_ci_detection():
    """Test Gemini's ability to detect OR + CI columns"""
    
    # Sample data matching our example CSV
    csv_columns = ["Study", "Author", "Year", "OR", "CI_Lower", "CI_Upper", "Region", "Quality"]
    csv_sample_data = [
        {
            "Study": "Study_1",
            "Author": "Smith et al.",
            "Year": 2020,
            "OR": 1.45,
            "CI_Lower": 1.02,
            "CI_Upper": 2.07,
            "Region": "North America",
            "Quality": "High"
        },
        {
            "Study": "Study_2", 
            "Author": "Johnson et al.",
            "Year": 2021,
            "OR": 2.12,
            "CI_Lower": 1.68,
            "CI_Upper": 2.67,
            "Region": "Europe",
            "Quality": "High"
        }
    ]
    
    target_roles = ["or", "ci_lower", "ci_upper", "study_label"]
    
    print("Testing OR + CI column detection...")
    try:
        result = map_csv_columns_to_meta_analysis_roles(
            csv_columns, csv_sample_data, target_roles
        )
        
        if result and "mapped_columns" in result:
            mapped_data = result["mapped_columns"]
            print("✅ Gemini mapping result:")
            print(json.dumps(mapped_data, indent=2, ensure_ascii=False))
            
            # Check if OR + CI format was detected
            data_format = mapped_data.get("data_format")
            detected_effect_size = mapped_data.get("detected_effect_size")
            detected_columns = mapped_data.get("detected_columns", {})
            
            if data_format == "or_ci" and detected_effect_size == "OR":
                print("✅ PASSED: OR + CI format correctly detected")
                return True, mapped_data
            else:
                print(f"❌ FAILED: Expected or_ci format, got {data_format}")
                print(f"Expected OR effect size, got {detected_effect_size}")
                return False, mapped_data
        else:
            print("❌ FAILED: No mapping result returned")
            return False, {}
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, {}

def test_r_template_generation():
    """Test R template generation for OR + CI conversion"""
    
    print("\nTesting R template generation...")
    
    # Sample analysis parameters that would be created after Gemini detection
    analysis_params = {
        "measure": "OR",
        "data_format": "or_ci",
        "detected_columns": {
            "or": "OR",
            "ci_lower": "CI_Lower", 
            "ci_upper": "CI_Upper"
        },
        "data_columns": {
            "study_label": "Study"
        }
    }
    
    data_summary = {"columns": ["Study", "OR", "CI_Lower", "CI_Upper"]}
    
    try:
        generator = RTemplateGenerator()
        escalc_code = generator._generate_escalc_code(analysis_params, data_summary)
        
        print("Generated R code:")
        print("-" * 50)
        print(escalc_code)
        print("-" * 50)
        
        # Check if the conversion code is present
        if "log(dat$OR)" in escalc_code and "log(dat$CI_Upper)" in escalc_code:
            print("✅ PASSED: OR to lnOR conversion code generated")
            return True
        else:
            print("❌ FAILED: OR to lnOR conversion code not found")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_rr_ci_detection():
    """Test RR + CI detection"""
    
    print("\nTesting RR + CI column detection...")
    
    csv_columns = ["Study", "Author", "Year", "RR", "Lower_CI", "Upper_CI", "Treatment_Type"]
    csv_sample_data = [
        {
            "Study": "RCT_001",
            "Author": "Thompson et al.",
            "Year": 2020,
            "RR": 0.85,
            "Lower_CI": 0.72,
            "Upper_CI": 1.01,
            "Treatment_Type": "Drug A"
        }
    ]
    
    target_roles = ["rr", "ci_lower", "ci_upper", "study_label"]
    
    try:
        result = map_csv_columns_to_meta_analysis_roles(
            csv_columns, csv_sample_data, target_roles
        )
        
        if result and "mapped_columns" in result:
            mapped_data = result["mapped_columns"]
            data_format = mapped_data.get("data_format")
            detected_effect_size = mapped_data.get("detected_effect_size")
            
            if data_format == "rr_ci" and detected_effect_size == "RR":
                print("✅ PASSED: RR + CI format correctly detected")
                return True
            else:
                print(f"❌ FAILED: Expected rr_ci format, got {data_format}")
                return False
        else:
            print("❌ FAILED: No mapping result returned")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing OR/RR + CI conversion functionality")
    print("=" * 60)
    
    # Check if Gemini API key is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  WARNING: GEMINI_API_KEY not set. Gemini tests will be skipped.")
        print("Set the environment variable to run full tests.")
        
        # Run template generation test only
        template_success = test_r_template_generation()
        if template_success:
            print("\n✅ Template generation test passed")
        else:
            print("\n❌ Template generation test failed")
        return
    
    # Run all tests
    or_detection_success, mapped_data = test_or_ci_detection()
    template_success = test_r_template_generation()
    rr_detection_success = test_rr_ci_detection()
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    print(f"OR + CI Detection: {'✅ PASSED' if or_detection_success else '❌ FAILED'}")
    print(f"Template Generation: {'✅ PASSED' if template_success else '❌ FAILED'}")
    print(f"RR + CI Detection: {'✅ PASSED' if rr_detection_success else '❌ FAILED'}")
    
    if all([or_detection_success, template_success, rr_detection_success]):
        print("\n🎉 All tests passed! OR/CI conversion functionality is working.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()