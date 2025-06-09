#!/usr/bin/env python3
"""
Test script to verify that Gemini-generated reports do not contain "significant" terminology.
Tests the updated prompts in gemini_utils.py
"""

import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_legacy.gemini_utils import generate_academic_writing_suggestion, interpret_meta_analysis_results, interpret_meta_regression_results

def test_academic_writing_without_significant():
    """Test that academic writing suggestions don't use 'significant' terminology"""
    
    # Sample meta-analysis results
    sample_results = {
        "overall_analysis": {
            "k": 10,
            "estimate": -0.14,
            "ci_lb": -0.91,
            "ci_ub": 0.63,
            "pval": 0.72,
            "I2": 91.28,
            "tau2": 1.41,
            "Q": 89.60,
            "Q_df": 9,
            "Q_pval": 0.0001
        },
        "egger_test": {
            "z": -0.75,
            "pval": 0.45
        },
        "r_version": "R version 4.4.0 (2024-04-24 ucrt)",
        "metafor_version": "metafor version 4.0-0"
    }
    
    print("Testing generate_academic_writing_suggestion...")
    try:
        result = generate_academic_writing_suggestion(sample_results)
        if result:
            # Check for "significant" terminology
            forbidden_terms = ["significant", "significantly", "non-significant", "insignificant"]
            found_terms = []
            
            for term in forbidden_terms:
                if term.lower() in result.lower():
                    found_terms.append(term)
            
            if found_terms:
                print(f"❌ FAILED: Found forbidden terms: {found_terms}")
                print(f"Report excerpt:\n{result[:500]}...")
            else:
                print("✅ PASSED: No 'significant' terminology found in academic writing")
                print(f"Report excerpt:\n{result[:500]}...")
        else:
            print("⚠️  WARNING: No result returned from generate_academic_writing_suggestion")
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_meta_analysis_interpretation():
    """Test that meta-analysis interpretations don't use 'significant' terminology"""
    
    sample_summary = {
        "pooled_effect": 1.45,
        "ci_lower": 1.12,
        "ci_upper": 1.88,
        "p_value": 0.005,
        "i_squared": 45.2,
        "tau_squared": 0.15
    }
    
    print("\nTesting interpret_meta_analysis_results...")
    try:
        result = interpret_meta_analysis_results(sample_summary)
        if result:
            forbidden_terms = ["significant", "significantly", "non-significant", "insignificant"]
            found_terms = []
            
            for term in forbidden_terms:
                if term.lower() in result.lower():
                    found_terms.append(term)
            
            if found_terms:
                print(f"❌ FAILED: Found forbidden terms: {found_terms}")
                print(f"Interpretation excerpt:\n{result[:500]}...")
            else:
                print("✅ PASSED: No 'significant' terminology found in meta-analysis interpretation")
                print(f"Interpretation excerpt:\n{result[:500]}...")
        else:
            print("⚠️  WARNING: No result returned from interpret_meta_analysis_results")
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_meta_regression_interpretation():
    """Test that meta-regression interpretations don't use 'significant' terminology"""
    
    sample_summary = {
        "moderators": [
            {"name": "year", "estimate": 0.05, "se": 0.02, "ci_lb": 0.01, "ci_ub": 0.09, "pval": 0.015}
        ],
        "R2": 35.5,
        "residual_I2": 55.2,
        "residual_tau2": 0.08
    }
    
    print("\nTesting interpret_meta_regression_results...")
    try:
        result = interpret_meta_regression_results(sample_summary)
        if result:
            forbidden_terms = ["significant", "significantly", "non-significant", "insignificant"]
            found_terms = []
            
            for term in forbidden_terms:
                if term.lower() in result.lower():
                    found_terms.append(term)
            
            if found_terms:
                print(f"❌ FAILED: Found forbidden terms: {found_terms}")
                print(f"Interpretation excerpt:\n{result[:500]}...")
            else:
                print("✅ PASSED: No 'significant' terminology found in meta-regression interpretation")
                print(f"Interpretation excerpt:\n{result[:500]}...")
        else:
            print("⚠️  WARNING: No result returned from interpret_meta_regression_results")
    except Exception as e:
        print(f"❌ ERROR: {e}")

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Gemini prompts for 'significant' terminology removal")
    print("=" * 60)
    
    # Check if Gemini API key is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  WARNING: GEMINI_API_KEY not set. Tests will be skipped.")
        print("Set the environment variable to run actual API tests.")
        return
    
    test_academic_writing_without_significant()
    test_meta_analysis_interpretation()
    test_meta_regression_interpretation()
    
    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)

if __name__ == "__main__":
    main()