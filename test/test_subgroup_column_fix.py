#!/usr/bin/env python3
"""
サブグループ解析の列名処理の修正をテストするスクリプト

修正内容:
1. CSVの列名がクリーンアップされる（スペース→アンダースコア）
2. R変数名として安全な名前を生成（特殊文字を除去）
3. JSONキーには安全な変数名を使用し、実際のカラム名は値に保存
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
import json

def test_subgroup_analysis_with_special_chars():
    """特殊文字を含むサブグループ列名でのR script生成をテスト"""
    
    # テストケース1: スペースと括弧を含む列名
    analysis_params = {
        "measure": "OR",
        "model": "REML",
        "subgroup_columns": [
            "Setting_(ICU_/_non-ICU)",  # クリーンアップ済みの列名
            "ASA_timing_(Chronic_/_New)",
            "Country"
        ],
        "data_columns": {
            "ai": "Intervention_Events",
            "ci": "Control_Events", 
            "n1i": "Intervention_Total",
            "n2i": "Control_Total",
            "study_label": "Study"
        }
    }
    
    data_summary = {
        "columns": [
            "Study", 
            "Intervention_Events", 
            "Intervention_Total",
            "Control_Events",
            "Control_Total",
            "Setting_(ICU_/_non-ICU)",  # クリーンアップ済みの列名
            "ASA_timing_(Chronic_/_New)",
            "Country"
        ]
    }
    
    output_paths = {
        "forest_plot_path": "/tmp/forest_plot.png",
        "funnel_plot_path": "/tmp/funnel_plot.png",
        "rdata_path": "/tmp/results.RData",
        "json_summary_path": "/tmp/summary.json",
        "forest_plot_subgroup_prefix": "/tmp/forest_plot_subgroup"
    }
    
    generator = RTemplateGenerator()
    
    # R script生成
    r_script = generator.generate_full_r_script(
        analysis_params=analysis_params,
        data_summary=data_summary,
        output_paths=output_paths,
        csv_file_path_in_script="/tmp/test_data.csv"
    )
    
    # 検証ポイント
    print("=== R Script Analysis ===")
    
    # 1. 安全な変数名が使用されているか確認
    if "res_subgroup_test_Setting__ICU___non_ICU_" in r_script:
        print("✓ 安全な変数名が正しく生成されています")
    else:
        print("✗ 安全な変数名の生成に問題があります")
    
    # 2. データアクセスには元の列名が使用されているか確認  
    if 'dat[["Setting_(ICU_/_non-ICU)"]]' in r_script:
        print("✓ データアクセスには正しい列名が使用されています")
    else:
        print("✗ データアクセスの列名に問題があります")
    
    # 3. JSONに実際の列名が保存されるか確認
    if 'subgroup_column = "Setting_(ICU_/_non-ICU)"' in r_script:
        print("✓ JSONに実際の列名が保存されるようになっています")
    else:
        print("✗ JSONへの列名保存に問題があります")
    
    # 4. 生成されたRスクリプトの一部を表示
    print("\n=== Generated R Code Snippets ===")
    
    # サブグループ解析部分を抽出して表示
    import re
    subgroup_matches = re.findall(r'# Subgroup.*?(?=# Subgroup|# ---|\Z)', r_script, re.DOTALL)
    
    for i, match in enumerate(subgroup_matches[:2]):  # 最初の2つだけ表示
        print(f"\n--- Subgroup {i+1} ---")
        print(match[:500] + "..." if len(match) > 500 else match)
    
    # 5. R スクリプトをファイルに保存（デバッグ用）
    test_script_path = "/tmp/test_subgroup_fix.R"
    with open(test_script_path, "w") as f:
        f.write(r_script)
    print(f"\n完全なRスクリプトを保存しました: {test_script_path}")
    
    return r_script

def test_slack_display():
    """Slack表示用のサマリー処理をテスト"""
    from utils.slack_utils import create_analysis_result_message
    
    # R実行結果のモックデータ
    mock_summary = {
        "estimate": 1.45,
        "ci_lb": 1.12,
        "ci_ub": 1.88,
        "I2": 45.2,
        "k": 10,
        "subgroup_moderation_test_Setting__ICU___non_ICU_": {
            "subgroup_column": "Setting_(ICU_/_non-ICU)",
            "QM": 5.23,
            "QMp": 0.022
        },
        "subgroup_analyses_Setting__ICU___non_ICU_": {
            "ICU": {
                "k": 5,
                "estimate": 1.78,
                "ci_lb": 1.23,
                "ci_ub": 2.56
            },
            "non-ICU": {
                "k": 5,
                "estimate": 1.12,
                "ci_lb": 0.89,
                "ci_ub": 1.41
            }
        }
    }
    
    result = {"summary": mock_summary}
    message = create_analysis_result_message(result)
    
    print("\n=== Slack Message Preview ===")
    print(message)
    
    # 検証
    if "Setting_(ICU_/_non-ICU)別サブグループ解析" in message:
        print("\n✓ 実際の列名が正しく表示されています")
    else:
        print("\n✗ 列名の表示に問題があります")

if __name__ == "__main__":
    print("サブグループ列名処理の修正テスト")
    print("=" * 50)
    
    # Rスクリプト生成テスト
    test_subgroup_analysis_with_special_chars()
    
    # Slack表示テスト
    test_slack_display()