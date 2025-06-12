#!/usr/bin/env python3
"""
サブグループ除外機能のテスト
1研究のみのサブグループが正しく除外され、レポートに表示されるかテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_subgroup_exclusion_functionality():
    """サブグループ除外機能のテスト"""
    
    generator = RTemplateGenerator()
    
    # 1研究のみのサブグループを含むテストデータ
    test_analysis_params = {
        "measure": "OR",
        "model": "REML", 
        "subgroups": ["region", "age_group"],
        "data_columns": {
            "ai": "intervention_events", "bi": "intervention_non_events",
            "ci": "control_events", "di": "control_non_events",
            "n1i": "intervention_total", "n2i": "control_total",
            "study_label": "study_name"
        }
    }
    
    test_data_summary = {
        "columns": ["study_name", "intervention_events", "intervention_non_events", 
                   "control_events", "control_non_events", "intervention_total", 
                   "control_total", "region", "age_group"],
        "shape": [10, 9]  # 10研究、9列
    }
    
    test_output_paths = {
        "forest_plot_path": "/tmp/test_forest.png",
        "funnel_plot_path": "/tmp/test_funnel.png", 
        "rdata_path": "/tmp/test_result.RData",
        "json_summary_path": "/tmp/test_summary.json",
        "subgroup_plot_path_prefix": "/tmp/test_forest_plot_subgroup"
    }
    
    # Rスクリプト生成
    r_script = generator.generate_full_r_script(
        test_analysis_params, test_data_summary, test_output_paths, "/tmp/test.csv"
    )
    
    # 除外機能が含まれているかチェック
    checks = [
        "excluded_subgroups <- character(0)",
        "valid_sg_names <- character(0)", 
        "if (n_studies <= 1)",
        "excluded from forest plot: insufficient data",
        "subgroup_exclusions",
        "summary_list$subgroup_exclusions"
    ]
    
    print("=== サブグループ除外機能のテスト ===")
    for check in checks:
        if check in r_script:
            print(f"✅ {check}: 含まれています")
        else:
            print(f"❌ {check}: 含まれていません")
    
    # 生成されたコードの一部を確認
    print("\n=== 生成されたサブグループ除外コード（抜粋） ===")
    lines = r_script.split('\n')
    
    # 除外処理部分を抽出
    exclusion_section_start = -1
    for i, line in enumerate(lines):
        if "1研究のみの小さいサブグループを除外" in line:
            exclusion_section_start = i
            break
    
    if exclusion_section_start >= 0:
        for i in range(exclusion_section_start, min(exclusion_section_start + 25, len(lines))):
            print(f"{i+1:4}: {lines[i]}")
    else:
        print("除外処理コードが見つかりませんでした")
    
    print("\n=== JSON保存部分の確認 ===")
    json_section_start = -1
    for i, line in enumerate(lines):
        if "subgroup_exclusions" in line and "summary_list" in line:
            json_section_start = i
            break
    
    if json_section_start >= 0:
        for i in range(max(0, json_section_start - 2), min(json_section_start + 5, len(lines))):
            print(f"{i+1:4}: {lines[i]}")
    else:
        print("JSON保存コードが見つかりませんでした")

def test_slack_message_exclusion():
    """Slackメッセージに除外情報が含まれるかテスト"""
    
    from utils.slack_utils import create_analysis_result_message
    
    # 除外情報を含むテストサマリー
    test_summary = {
        "estimate": 1.45,
        "ci_lb": 1.12, 
        "ci_ub": 1.88,
        "I2": 45.2,
        "k": 8,  # 除外後の研究数
        "subgroup_moderation_test_region": {
            "QMp": 0.032,
            "k": 6
        },
        "subgroup_exclusions": {
            "region": {
                "excluded_subgroups": ["Asia", "Africa"],
                "reason": "insufficient_data_n_le_1",
                "included_subgroups": ["Europe", "North America"]
            },
            "age_group": {
                "excluded_subgroups": ["<30"],
                "reason": "insufficient_data_n_le_1", 
                "included_subgroups": ["30-50", ">50"]
            }
        }
    }
    
    print("\n=== デバッグ: summary内容 ===")
    print(f"subgroup_exclusions: {test_summary.get('subgroup_exclusions')}")
    
    message = create_analysis_result_message({"summary": test_summary})
    
    print("\n=== Slackメッセージ除外情報テスト ===")
    if "【サブグループ除外情報】" in message:
        print("✅ 除外情報セクションが含まれています")
    else:
        print("❌ 除外情報セクションが含まれていません")
    
    if "Asia, Africa" in message:
        print("✅ 除外されたサブグループ名が含まれています")
    else:
        print("❌ 除外されたサブグループ名が含まれていません")
    
    if "研究数不足" in message:
        print("✅ 除外理由が含まれています")
    else:
        print("❌ 除外理由が含まれていません")
    
    print("\n=== 生成されたメッセージ（全体） ===")
    print(message)
    
    print("\n=== 除外情報を含む行のみ ===")
    lines = message.split('\n')
    for i, line in enumerate(lines):
        if "除外" in line or "サブグループ" in line:
            print(f"Line {i+1}: {line}")

if __name__ == "__main__":
    test_subgroup_exclusion_functionality()
    test_slack_message_exclusion()
    print("\n✅ テスト完了")