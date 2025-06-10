#!/usr/bin/env python3
"""
特定の問題を修正して詳細なRスクリプトを確認
"""

import os
import pandas as pd
from templates.r_templates import RTemplateGenerator

def test_hazard_ratio_fixed():
    """HRの問題を修正したテスト"""
    print("="*80)
    print("Fixed Hazard Ratio Test (HR)")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_hazard_ratio_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
    print(f"CSV columns: {list(df.columns)}")
    print(f"First few rows:")
    print(df.head(3))
    
    # HR with se -> variance conversion
    analysis_params = {
        "measure": "HR",
        "model": "REML", 
        "data_columns": {
            "yi": "log_hr",
            "vi": "se_log_hr",  # Need to square this to get variance
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    data_summary = {
        "columns": list(df.columns),
        "shape": list(df.shape)
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_hr_forest.png",
        "funnel_plot_path": "/tmp/test_hr_funnel.png",
        "rdata_path": "/tmp/test_hr_results.RData",
        "json_summary_path": "/tmp/test_hr_summary.json"
    }
    
    generator = RTemplateGenerator()
    r_script = generator.generate_full_r_script(
        analysis_params, data_summary, output_paths, csv_path
    )
    
    print("Generated R Script (first 1500 chars):")
    print("-" * 40)
    print(r_script[:1500])
    
    # Write full script to file for inspection
    with open("/tmp/hr_full_script.R", "w") as f:
        f.write(r_script)
    print(f"\nFull script saved to: /tmp/hr_full_script.R")
    
    return r_script

def test_complete_binary_outcome():
    """完全な二値アウトカムスクリプトの確認"""
    print("\n" + "="*80)
    print("Complete Binary Outcome Script")
    print("="*80)
    
    csv_path = "/home/youkiti/meta-analysis-bot-release/examples/example_binary_meta_dataset.csv"
    df = pd.read_csv(csv_path)
    
    analysis_params = {
        "measure": "OR",
        "model": "REML",
        "data_columns": {
            "ai": "events_treatment",
            "bi": None,
            "ci": "events_control", 
            "di": None,
            "n1i": "total_treatment",
            "n2i": "total_control",
            "study_label": "study_id"
        },
        "subgroup_columns": ["region"],
        "moderator_columns": []
    }
    
    data_summary = {
        "columns": list(df.columns),
        "shape": list(df.shape)
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
    
    # Write full script to file for inspection
    with open("/tmp/binary_full_script.R", "w") as f:
        f.write(r_script)
    print(f"Full binary outcome script saved to: /tmp/binary_full_script.R")
    
    return r_script

def analyze_generated_scripts():
    """生成されたスクリプトの分析"""
    print("\n" + "="*80)
    print("Generated Scripts Analysis")
    print("="*80)
    
    script_files = [
        ("/tmp/hr_full_script.R", "Hazard Ratio"),
        ("/tmp/binary_full_script.R", "Binary Outcome")
    ]
    
    for script_path, analysis_type in script_files:
        if os.path.exists(script_path):
            with open(script_path, "r") as f:
                content = f.read()
            
            print(f"\n{analysis_type} Script Analysis:")
            print("-" * 40)
            print(f"Total lines: {len(content.splitlines())}")
            print(f"Contains escalc: {'escalc(' in content}")
            print(f"Contains rma: {'rma(' in content}")
            print(f"Contains forest: {'forest(' in content}")
            print(f"Contains funnel: {'funnel(' in content}")
            
            # Check for specific patterns
            if analysis_type == "Hazard Ratio":
                print(f"Uses yi/vi directly: {'yi, vi' in content}")
                print(f"Handles log transformation: {'log_hr' in content}")
            elif analysis_type == "Binary Outcome":
                print(f"Calculates bi/di columns: {'n_minus_event' in content}")
                print(f"Uses OR measure: {'measure=\"OR\"' in content}")

if __name__ == "__main__":
    # Test HR with fixes
    test_hazard_ratio_fixed()
    
    # Test complete binary outcome
    test_complete_binary_outcome()
    
    # Analyze all generated scripts
    analyze_generated_scripts()