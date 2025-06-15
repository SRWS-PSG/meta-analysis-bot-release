#!/usr/bin/env python3
"""
サブグループフォレストプロット修正版のテストスクリプト
"""

import sys
import os
sys.path.append('/home/youkiti/meta-analysis-bot-release')

from templates.r_templates import RTemplateGenerator

def test_new_subgroup_template():
    """修正されたサブグループテンプレートをテスト"""
    
    print("🧪 サブグループフォレストプロット修正版テスト開始")
    print("=" * 60)
    
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
        
        print("✅ Rスクリプト生成成功")
        
        # サブグループフォレストプロット部分を抽出
        lines = script.split('\n')
        start_found = False
        subgroup_lines = []
        
        for line in lines:
            if "SUBGROUP FOREST PLOT START: region" in line:
                start_found = True
                print("✅ サブグループフォレストプロット部分を発見")
            
            if start_found:
                subgroup_lines.append(line)
                
            if start_found and "SUBGROUP FOREST PLOT END" in line:
                break
        
        if not subgroup_lines:
            print("❌ サブグループフォレストプロット部分が見つかりません")
            return False
        
        print(f"📊 サブグループプロットコード: {len(subgroup_lines)}行")
        
        # 修正版の特徴をチェック
        script_text = '\n'.join(subgroup_lines)
        
        checks = [
            ("前提条件チェック", "has_subgroup_results <-" in script_text),
            ("有効サブグループ取得", "valid_subgroups <- names(res_by_subgroup_" in script_text),
            ("データフィルタリング", "dat_sg_filtered <-" in script_text),
            ("安全なインデックス確認", "length(filter_indices) == 0" in script_text),
            ("シンプルな行位置計算", "current_row <- n_studies + (n_subgroups * 2) + 2" in script_text),
            ("エラーハンドリング", "tryCatch" in script_text),
            ("修正版コメント", "修正版" in script_text)
        ]
        
        print("\n🔍 修正版の特徴チェック:")
        all_passed = True
        for name, condition in checks:
            status = "✅" if condition else "❌"
            print(f"  {status} {name}")
            if not condition:
                all_passed = False
        
        # 削除された複雑な機能がないことを確認
        removed_features = [
            ("複雑なilab処理", "ilab_data_main" not in script_text),
            ("サブグループTotal行", "sg_total_row_y" not in script_text),
            ("全体サマリー追加", "overall_row <-" not in script_text),
            ("複雑なデバッグ出力", script_text.count("DEBUG:") < 10)  # 10未満であることを確認
        ]
        
        print("\n🗑️ 削除された複雑な機能:")
        for name, condition in removed_features:
            status = "✅" if condition else "⚠️"
            print(f"  {status} {name}")
            if not condition:
                print(f"      注意: {name}がまだ含まれています")
        
        # コードの簡潔性をチェック
        if len(subgroup_lines) < 100:
            print(f"✅ コードが簡潔です ({len(subgroup_lines)}行)")
        else:
            print(f"⚠️ コードがまだ長めです ({len(subgroup_lines)}行)")
        
        if all_passed:
            print("\n🎉 全ての修正が正しく適用されています！")
            return True
        else:
            print("\n⚠️ 一部の修正が適用されていない可能性があります")
            return False
            
    except Exception as e:
        print(f"❌ テスト中にエラーが発生: {e}")
        return False

def show_template_sample():
    """修正版テンプレートのサンプルを表示"""
    
    print("\n📝 修正版テンプレートのサンプル:")
    print("-" * 40)
    
    sample_lines = [
        "# 前提条件をシンプルに確認",
        "has_subgroup_results <- exists('res_by_subgroup_region') && length(res_by_subgroup_region) > 0",
        "",
        "# 有効なサブグループを取得", 
        "valid_subgroups <- names(res_by_subgroup_region)",
        "valid_subgroups <- valid_subgroups[!sapply(res_by_subgroup_region, is.null)]",
        "",
        "# データを有効なサブグループのみにフィルタ",
        "dat_sg_filtered <- dat[dat[['region']] %in% valid_subgroups, ]",
        "",
        "# シンプルな行位置計算",
        "current_row <- n_studies + (n_subgroups * 2) + 2",
        "",
        "# フォレストプロット描画",
        "forest(res_plot_sg, slab = plot_slab, rows = all_rows, ...)"
    ]
    
    for line in sample_lines:
        print(f"  {line}")

if __name__ == "__main__":
    success = test_new_subgroup_template()
    show_template_sample()
    
    if success:
        print("\n🚀 次のステップ:")
        print("1. Herokuデプロイ完了を確認")
        print("2. 実際のSlackボットでテスト実行")
        print("3. ユーザーに修正完了を報告")
    else:
        print("\n🔧 追加の修正が必要な可能性があります")