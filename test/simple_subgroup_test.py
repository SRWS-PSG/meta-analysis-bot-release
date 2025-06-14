#!/usr/bin/env python3
"""
サブグループ解析の簡単なテスト
"""

import sys
import os
sys.path.append('/home/youkiti/meta-analysis-bot-release')

from templates.r_templates import RTemplateGenerator

def test_subgroup_template():
    """サブグループテンプレートの生成をテスト"""
    
    generator = RTemplateGenerator()
    
    # テスト用パラメータ
    analysis_params = {
        "effect_size": "OR",
        "measure": "OR", 
        "method": "REML",
        "subgroups": ["region"],
        "subgroup_columns": ["region"],
        "data_columns": {
            "ai": "events_treatment",
            "bi": "events_control", 
            "ci": "total_treatment",
            "di": "total_control"
        }
    }
    
    data_summary = {
        "columns": ["study_id", "events_treatment", "events_control", 
                   "total_treatment", "total_control", "region"]
    }
    
    output_paths = {
        "forest_plot_path": "forest_plot_overall.png",
        "forest_plot_subgroup_prefix": "forest_plot_subgroup",
        "funnel_plot_path": "funnel_plot.png",
        "rdata_path": "results.RData",
        "json_summary_path": "summary.json"
    }
    
    csv_path = "/tmp/test.csv"
    
    try:
        # スクリプト生成
        script = generator.generate_full_r_script(
            analysis_params, data_summary, output_paths, csv_path
        )
        
        # サブグループフォレストプロット部分を探す
        lines = script.split('\n')
        in_subgroup_section = False
        subgroup_lines = []
        
        for line in lines:
            if "サブグループ 'region' のフォレストプロット" in line:
                in_subgroup_section = True
                print("✅ サブグループフォレストプロット部分を発見")
            
            if in_subgroup_section:
                subgroup_lines.append(line)
                
            if in_subgroup_section and "dev.off()" in line:
                break
        
        if subgroup_lines:
            print(f"📝 サブグループフォレストプロット部分（{len(subgroup_lines)}行）:")
            for i, line in enumerate(subgroup_lines[:50]):  # 最初の50行のみ表示
                print(f"{i+1:3d}: {line}")
            
            if len(subgroup_lines) > 50:
                print(f"... ({len(subgroup_lines) - 50}行省略)")
        else:
            print("❌ サブグループフォレストプロット部分が見つかりません")
            
        # フィルタリング部分が含まれているか確認
        if "res_for_plot_filtered" in script:
            print("✅ res_for_plotフィルタリング処理が含まれています")
        else:
            print("❌ res_for_plotフィルタリング処理が見つかりません")
            
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    test_subgroup_template()