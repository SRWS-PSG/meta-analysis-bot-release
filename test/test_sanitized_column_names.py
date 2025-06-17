#!/usr/bin/env python3
"""
特殊文字を含む列名（サブグループ、データ列）のテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
import tempfile
import json

def test_special_column_names():
    """特殊文字を含む列名でRスクリプトが正しく生成されるかテスト"""
    
    generator = RTemplateGenerator()
    
    # テストパラメータ（特殊文字を含む列名）
    analysis_params = {
        "measure": "OR",
        "model": "REML",
        "data_columns": {
            "ai": "Intervention_(Events)",
            "bi": "Intervention_(No_Events)", 
            "ci": "Control_(Events)",
            "di": "Control_(No_Events)",
            "n1i": "Intervention_Total",
            "n2i": "Control_Total",
            "study_label": "Study_ID"
        },
        "subgroup_columns": ["Setting_(ICU_/_non-ICU)", "Region_(Asia/Europe/Americas)"],
        "moderator_columns": ["Year_(2020-2024)", "Quality_Score_(0-10)"]
    }
    
    data_summary = {
        "columns": [
            "Study_ID", 
            "Intervention_(Events)", "Intervention_(No_Events)", "Intervention_Total",
            "Control_(Events)", "Control_(No_Events)", "Control_Total",
            "Setting_(ICU_/_non-ICU)", "Region_(Asia/Europe/Americas)",
            "Year_(2020-2024)", "Quality_Score_(0-10)"
        ],
        "shape": [20, 11]
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/test_forest.png",
        "forest_plot_subgroup_prefix": "/tmp/test_forest_subgroup",
        "funnel_plot_path": "/tmp/test_funnel.png",
        "rdata_path": "/tmp/test_result.RData",
        "json_summary_path": "/tmp/test_summary.json",
        "bubble_plot_path_prefix": "/tmp/test_bubble"
    }
    
    # Rスクリプト生成
    r_script = generator.generate_full_r_script(
        analysis_params, 
        data_summary, 
        output_paths, 
        "/tmp/test_data.csv"
    )
    
    # 生成されたスクリプトを保存
    with open("/tmp/test_r_script_sanitized.R", "w") as f:
        f.write(r_script)
    
    print("Rスクリプトが生成されました: /tmp/test_r_script_sanitized.R")
    
    # 重要な部分をチェック
    print("\n=== 列名サニタイズ処理の確認 ===")
    if "make.names" in r_script:
        print("✓ make.names() による列名サニタイズが含まれています")
    else:
        print("✗ make.names() が見つかりません")
    
    if "column_mapping" in r_script:
        print("✓ column_mapping が作成されています")
    else:
        print("✗ column_mapping が見つかりません")
    
    # サブグループ解析部分をチェック
    print("\n=== サブグループ解析の確認 ===")
    if "sanitized_subgroup_col" in r_script:
        print("✓ サブグループ列のサニタイズ処理が含まれています")
    else:
        print("✗ サブグループ列のサニタイズ処理が見つかりません")
    
    # モデレーター解析部分をチェック
    print("\n=== モデレーター解析の確認 ===")
    if "moderator_cols_sanitized" in r_script:
        print("✓ モデレーター列のサニタイズ処理が含まれています")
    else:
        print("✗ モデレーター列のサニタイズ処理が見つかりません")
    
    # 問題のある構文をチェック
    print("\n=== 潜在的な問題の確認 ===")
    if "mods = ~ factor(Setting_(ICU_/_non" in r_script:
        print("✗ 警告: サニタイズされていない列名が直接使用されている可能性があります")
    else:
        print("✓ 特殊文字を含む列名の直接使用は検出されませんでした")
    
    # スクリプトの一部を表示
    print("\n=== 生成されたRスクリプトの重要部分 ===")
    lines = r_script.split('\n')
    for i, line in enumerate(lines):
        if 'column_mapping' in line or 'sanitized_subgroup_col' in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print(f"\n行 {start+1}-{end}:")
            for j in range(start, end):
                print(f"{j+1}: {lines[j]}")
    
    return r_script

if __name__ == "__main__":
    test_special_column_names()