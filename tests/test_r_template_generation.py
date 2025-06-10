#!/usr/bin/env python3
"""
各example CSVファイルに対するRTemplateGeneratorのテストスクリプト
"""

import os
import logging
import pandas as pd
from templates.r_templates import RTemplateGenerator

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_csv_and_analyze(csv_path):
    """CSVファイルを読み込んで基本分析を行う"""
    df = pd.read_csv(csv_path)
    data_summary = {
        "columns": list(df.columns),
        "shape": list(df.shape),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()}
    }
    return df, data_summary

def test_binary_outcome_csv():
    """1. Binary outcome CSV test (OR analysis)"""
    print("\n" + "="*80)
    print("Test 1: Binary Outcome Dataset (OR)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_binary_meta_dataset.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for binary outcome (OR)
    analysis_params = {
        "measure": "OR",
        "model": "REML",
        "data_columns": {
            "ai": "events_treatment",
            "bi": None,  # Will be calculated from total_treatment - events_treatment
            "ci": "events_control", 
            "di": None,  # Will be calculated from total_control - events_control
            "n1i": "total_treatment",
            "n2i": "total_control",
            "study_label": "study_id"
        },
        "subgroup_columns": ["region", "age"],
        "moderator_columns": []
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_binary_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/test_binary_subgroup",
        "funnel_plot_path": "/tmp/test_binary_funnel.png",
        "rdata_path": "/tmp/test_binary_results.RData",
        "json_summary_path": "/tmp/test_binary_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def test_continuous_outcome_csv():
    """2. Continuous outcome CSV test (SMD analysis)"""
    print("\n" + "="*80)
    print("Test 2: Continuous Outcome Dataset (SMD)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_continuous_meta_dataset.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for continuous outcome (SMD)
    analysis_params = {
        "measure": "SMD",
        "model": "REML",
        "data_columns": {
            "n1i": "n_treatment",
            "n2i": "n_control",
            "m1i": "mean_treatment",
            "m2i": "mean_control",
            "sd1i": "sd_treatment",
            "sd2i": "sd_control",
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_continuous_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/test_continuous_subgroup",
        "funnel_plot_path": "/tmp/test_continuous_funnel.png",
        "rdata_path": "/tmp/test_continuous_results.RData",
        "json_summary_path": "/tmp/test_continuous_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def test_hazard_ratio_csv():
    """3. Hazard ratio CSV test (HR analysis)"""
    print("\n" + "="*80)
    print("Test 3: Hazard Ratio Dataset (HR)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_hazard_ratio_meta_dataset.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for hazard ratio (HR with log-transformed data)
    analysis_params = {
        "measure": "HR",
        "model": "REML", 
        "data_columns": {
            "yi": "log_hr",
            "vi": "se_log_hr",  # Note: se will be converted to variance in escalc
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_hr_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/test_hr_subgroup",
        "funnel_plot_path": "/tmp/test_hr_funnel.png",
        "rdata_path": "/tmp/test_hr_results.RData",
        "json_summary_path": "/tmp/test_hr_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def test_proportion_csv():
    """4. Proportion CSV test (PLO analysis)"""
    print("\n" + "="*80)
    print("Test 4: Proportion Dataset (PLO)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_proportion_meta_dataset.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for proportion (PLO)
    analysis_params = {
        "measure": "PLO",
        "model": "REML",
        "data_columns": {
            "proportion_events": "events",
            "proportion_total": "total",
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_proportion_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/test_proportion_subgroup",
        "funnel_plot_path": "/tmp/test_proportion_funnel.png",
        "rdata_path": "/tmp/test_proportion_results.RData",
        "json_summary_path": "/tmp/test_proportion_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def test_precalculated_csv():
    """5. Pre-calculated effect size CSV test (PRE analysis)"""
    print("\n" + "="*80)
    print("Test 5: Pre-calculated Effect Size Dataset (PRE)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_meta_data.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for pre-calculated effect sizes
    analysis_params = {
        "measure": "PRE",
        "model": "REML",
        "data_columns": {
            "yi": "yi",
            "vi": "vi",
            "study_label": "study"
        },
        "subgroup_columns": [],
        "moderator_columns": []
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_precalc_forest.png",
        "funnel_plot_path": "/tmp/test_precalc_funnel.png",
        "rdata_path": "/tmp/test_precalc_results.RData",
        "json_summary_path": "/tmp/test_precalc_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def test_meta_regression_csv():
    """6. Meta-regression CSV test (with moderators)"""
    print("\n" + "="*80)
    print("Test 6: Meta-regression Dataset (with moderators)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_meta_regression_data.csv"
    df, data_summary = load_csv_and_analyze(csv_path)
    
    print(f"CSV columns: {data_summary['columns']}")
    print(f"Shape: {data_summary['shape']}")
    
    # Analysis parameters for meta-regression
    analysis_params = {
        "measure": "PRE",
        "model": "REML",
        "data_columns": {
            "yi": "yi",
            "vi": "vi",
            "study_label": "study"
        },
        "subgroup_columns": [],
        "moderator_columns": ["year", "quality_score", "duration"]
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_regression_forest.png",
        "funnel_plot_path": "/tmp/test_regression_funnel.png",
        "bubble_plot_path_prefix": "/tmp/test_regression_bubble",
        "rdata_path": "/tmp/test_regression_results.RData",
        "json_summary_path": "/tmp/test_regression_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("\nGenerated R Script:")
    print("-" * 40)
    print(r_script[:2000] + "\n... (truncated)")
    
    return r_script

def main():
    """Run all tests"""
    print("Testing RTemplateGenerator with example CSV files")
    print("=" * 80)
    
    try:
        # Test 1: Binary outcome
        test_binary_outcome_csv()
        
        # Test 2: Continuous outcome  
        test_continuous_outcome_csv()
        
        # Test 3: Hazard ratio
        test_hazard_ratio_csv()
        
        # Test 4: Proportion
        test_proportion_csv()
        
        # Test 5: Pre-calculated effect sizes
        test_precalculated_csv()
        
        # Test 6: Meta-regression
        test_meta_regression_csv()
        
        print("\n" + "="*80)
        print("All tests completed successfully!")
        print("="*80)
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise

if __name__ == "__main__":
    main()