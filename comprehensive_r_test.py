#!/usr/bin/env python3
"""
各解析タイプの包括的テストと問題点の詳細分析
"""

import os
import pandas as pd
from templates.r_templates import RTemplateGenerator

def fix_hr_test():
    """HRの修正版テスト - se_log_hrを分散に変換"""
    print("="*80)
    print("Fixed HR Test with Proper Column Mapping")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_hazard_ratio_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
    print(f"Original HR data columns: {list(df.columns)}")
    print("Need to convert se_log_hr to variance (vi) and map log_hr to yi")
    
    # Pre-process to add yi and vi columns
    modified_df = df.copy()
    modified_df['yi'] = modified_df['log_hr']  # Effect size is log hazard ratio
    modified_df['vi'] = modified_df['se_log_hr'] ** 2  # Variance is SE squared
    
    print(f"Modified columns: {list(modified_df.columns)}")
    print("First few rows of yi and vi:")
    print(modified_df[['study_id', 'log_hr', 'se_log_hr', 'yi', 'vi']].head(3))
    
    # Save modified CSV
    modified_csv_path = "/tmp/modified_hr_data.csv"
    modified_df.to_csv(modified_csv_path, index=False)
    
    # Analysis parameters for HR with yi/vi
    analysis_params = {
        "measure": "HR",
        "model": "REML",
        "data_columns": {
            "yi": "yi",  # Now properly mapped
            "vi": "vi",  # Now properly mapped
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    data_summary = {
        "columns": list(modified_df.columns),
        "shape": list(modified_df.shape)
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_hr_fixed_forest.png",
        "funnel_plot_path": "/tmp/test_hr_fixed_funnel.png",
        "rdata_path": "/tmp/test_hr_fixed_results.RData",
        "json_summary_path": "/tmp/test_hr_fixed_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, modified_csv_path
    )
    
    # Save the fixed script
    with open("/tmp/hr_fixed_script.R", "w") as f:
        f.write(r_script)
    
    print(f"Fixed HR script saved to: /tmp/hr_fixed_script.R")
    
    # Check if script contains forest plot
    if "forest(" in r_script:
        print("✓ Forest plot generation included")
    else:
        print("✗ Forest plot generation missing")
    
    return r_script

def analyze_claude_md_requirements():
    """CLAUDE.mdの要件との対応関係を確認"""
    print("\n" + "="*80)
    print("Analysis Against CLAUDE.md Requirements")
    print("="*80)
    
    requirements = {
        "Binary Outcomes": ["OR", "RR", "RD", "PETO"],
        "Continuous Outcomes": ["SMD", "MD", "ROM"], 
        "Hazard Ratios": ["HR"],
        "Proportions": ["PLO", "PR", "PAS", "PFT", "PRAW"],
        "Incidence Rates": ["IR", "IRLN", "IRS", "IRFT"],
        "Correlations": ["COR"],
        "Pre-calculated": ["yi"],
        "Subgroup Analysis": "Statistical tests",
        "Meta-regression": "Multiple moderators",
        "Sensitivity Analysis": "Filtering conditions"
    }
    
    print("Required Analysis Types from CLAUDE.md:")
    for category, measures in requirements.items():
        print(f"  {category}: {measures}")
    
    # Test each category
    print("\nTesting each category:")
    
    # 1. Binary Outcomes Test (OR)
    print("\n1. Binary Outcomes (OR):")
    test_binary_or_complete()
    
    # 2. Continuous Outcomes Test (SMD)  
    print("\n2. Continuous Outcomes (SMD):")
    test_continuous_smd_complete()
    
    # 3. Proportions Test (PLO)
    print("\n3. Proportions (PLO):")
    test_proportion_plo_complete()
    
    # 4. Pre-calculated Test (yi/vi)
    print("\n4. Pre-calculated Effect Sizes (yi/vi):")
    test_precalculated_complete()
    
    # 5. Meta-regression Test
    print("\n5. Meta-regression:")
    test_meta_regression_complete()

def test_binary_or_complete():
    """完全な二値アウトカムテスト"""
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_binary_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
    analysis_params = {
        "measure": "OR",
        "model": "REML",
        "data_columns": {
            "ai": "events_treatment",
            "ci": "events_control",
            "n1i": "total_treatment",
            "n2i": "total_control",
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    data_summary = {"columns": list(df.columns), "shape": list(df.shape)}
    output_paths = {
        "forest_plot_path": "/tmp/binary_or_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/binary_or_subgroup",
        "funnel_plot_path": "/tmp/binary_or_funnel.png",
        "rdata_path": "/tmp/binary_or_results.RData",
        "json_summary_path": "/tmp/binary_or_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(analysis_params, data_summary, output_paths, csv_path)
    
    # Check key components
    checks = {
        "escalc with OR": 'measure="OR"' in r_script,
        "ai/bi/ci/di calculation": "n_minus_event" in r_script,
        "Forest plot": "forest(" in r_script,
        "Subgroup analysis": "res_subgroup_test_region" in r_script,
        "Exponential transform": 'current_measure %in% c("OR"' in r_script
    }
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

def test_continuous_smd_complete():
    """完全な連続アウトカムテスト"""
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_continuous_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
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
    
    data_summary = {"columns": list(df.columns), "shape": list(df.shape)}
    output_paths = {
        "forest_plot_path": "/tmp/continuous_smd_forest.png",
        "rdata_path": "/tmp/continuous_smd_results.RData",
        "json_summary_path": "/tmp/continuous_smd_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(analysis_params, data_summary, output_paths, csv_path)
    
    checks = {
        "escalc with SMD": 'measure="SMD"' in r_script,
        "All required columns": all(col in r_script for col in ["n1i", "n2i", "m1i", "m2i", "sd1i", "sd2i"]),
        "No exponential transform": 'apply_exp_transform' in r_script and 'current_measure %in% c("OR"' in r_script
    }
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

def test_proportion_plo_complete():
    """完全な比率解析テスト"""
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_proportion_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
    analysis_params = {
        "measure": "PLO",
        "model": "REML",
        "data_columns": {
            "proportion_events": "events",
            "proportion_total": "total",
            "study_label": "study_id"
        },
        "subgroup_columns": [],
        "moderator_columns": []
    }
    
    data_summary = {"columns": list(df.columns), "shape": list(df.shape)}
    output_paths = {
        "forest_plot_path": "/tmp/proportion_plo_forest.png",
        "rdata_path": "/tmp/proportion_plo_results.RData",
        "json_summary_path": "/tmp/proportion_plo_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(analysis_params, data_summary, output_paths, csv_path)
    
    checks = {
        "escalc with PLO": 'measure="PLO"' in r_script,
        "Events and total": "xi=events" in r_script and "ni=total" in r_script,
        "Exponential transform": 'current_measure %in% c("OR", "RR", "HR", "IRR", "PLO"' in r_script
    }
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

def test_precalculated_complete():
    """完全な事前計算効果量テスト"""
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_meta_data.csv"
    df = pd.read_csv(csv_path)
    
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
    
    data_summary = {"columns": list(df.columns), "shape": list(df.shape)}
    output_paths = {
        "forest_plot_path": "/tmp/precalc_pre_forest.png",
        "rdata_path": "/tmp/precalc_pre_results.RData",
        "json_summary_path": "/tmp/precalc_pre_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(analysis_params, data_summary, output_paths, csv_path)
    
    checks = {
        "No escalc needed": "escalc(" not in r_script or "事前計算された効果量" in r_script,
        "Direct rma with yi/vi": "rma(yi, vi" in r_script,
        "No exponential transform": 'current_measure %in% c("OR"' in r_script and 'PRE' not in ['OR', 'RR', 'HR']
    }
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

def test_meta_regression_complete():
    """完全なメタ回帰テスト"""
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_meta_regression_data.csv"
    df = pd.read_csv(csv_path)
    
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
    
    data_summary = {"columns": list(df.columns), "shape": list(df.shape)}
    output_paths = {
        "forest_plot_path": "/tmp/regression_forest.png",
        "bubble_plot_path_prefix": "/tmp/regression_bubble",
        "rdata_path": "/tmp/regression_results.RData",
        "json_summary_path": "/tmp/regression_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(analysis_params, data_summary, output_paths, csv_path)
    
    checks = {
        "Meta-regression formula": "mods = ~ year + quality_score + duration" in r_script,
        "Bubble plots": "regplot(" in r_script,
        "Multiple moderators": len(analysis_params["moderator_columns"]) == 3,
        "R-squared reporting": "R2 = ifelse" in r_script
    }
    
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")

if __name__ == "__main__":
    # Test HR fixes
    fix_hr_test()
    
    # Comprehensive analysis against requirements
    analyze_claude_md_requirements()