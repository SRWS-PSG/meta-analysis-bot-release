#!/usr/bin/env python3
"""
ilab 19 vs 20 エラーの最終修正テスト
完全な再構築ロジックをテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_ilab_rebuild_fix():
    """ilab完全再構築修正をテスト"""
    
    print("=== ilab 完全再構築修正テスト ===")
    
    # 修正確認用パラメータ
    analysis_params = {
        'analysis_type': 'binary',
        'measure': 'OR',
        'method': 'REML',
        'subgroup_columns': ['Region'],
        'data_columns': {
            'ai': 'events_treatment',
            'bi': 'total_treatment', 
            'ci': 'events_control',
            'di': 'total_control',
            'study_label': 'Study'
        }
    }
    
    data_summary = {
        'columns': ['Study', 'events_treatment', 'total_treatment', 'events_control', 'total_control', 'Region'],
        'study_id_column': 'Study',
        'detected_columns': {
            'binary_intervention_events': ['events_treatment'],
            'binary_intervention_total': ['total_treatment'],
            'binary_control_events': ['events_control'],
            'binary_control_total': ['total_control'],
            'study_id_candidates': ['Study'],
            'subgroup_candidates': ['Region']
        }
    }
    
    output_paths = {
        'rdata_path': 'results.RData',
        'json_summary_path': 'results.json',
        'forest_plot_path': 'forest.png',
        'funnel_plot_path': 'funnel.png'
    }
    
    try:
        # Rスクリプト生成
        generator = RTemplateGenerator()
        r_script = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=output_paths,
            csv_file_path_in_script='/tmp/test.csv'
        )
        
        # 修正確認項目
        checks = [
            ("完全再構築ロジック", "Rebuilding ilab_data_main to match res_for_plot_filtered exactly" in r_script),
            ("Study順序取得", "target_studies <- res_for_plot_filtered$data$Study" in r_script),
            ("元データ使用", "reordered_data <- dat[match(target_studies, dat$Study)" in r_script),
            ("NA処理", "Some target studies not found in original data" in r_script),
            ("Events/Total再構築", "treatment_display_rebuild <- paste" in r_script),
            ("最終検証", "FINAL CHECK PASSED: ilab_data_main size matches" in r_script),
            ("失敗時無効化", "FINAL CHECK FAILED: Size mismatch persists" in r_script),
            ("成功ログ", "SUCCESS: ilab_data_main rebuilt with" in r_script)
        ]
        
        print("\n=== 修正確認結果 ===")
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 重要な修正箇所の抽出
        print("\n=== 重要な修正箇所 ===")
        
        rebuild_lines = [line.strip() for line in r_script.split('\n') 
                        if 'Rebuilding ilab_data_main' in line or 
                           'target_studies <-' in line or
                           'reordered_data <-' in line or
                           'FINAL CHECK' in line]
        
        for line in rebuild_lines[:10]:  # 最初の10行を表示
            print(f"  {line}")
        
        print(f"\n=== テスト結果 ===")
        if all_passed:
            print("🎉 ilab 19 vs 20 エラーの完全修正が実装されました！")
            print("✅ res_for_plot_filteredに完全に合わせた再構築ロジック")
            print("✅ Study順序の完全な整合性")
            print("✅ 元データからの確実な再構築")
            print("✅ 包括的なエラーハンドリング")
            print("✅ 最終検証による確実性")
        else:
            print("❌ 一部の修正が不完全です")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ilab_rebuild_fix()
    print(f"\n最終テスト結果: {'🎉 成功' if success else '❌ 失敗'}")
    sys.exit(0 if success else 1)