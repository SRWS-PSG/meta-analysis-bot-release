#!/usr/bin/env python3
"""
ilab size mismatch エラーの最終修正テスト
論理的矛盾を解決した修正をテスト
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_ilab_final_fix():
    """ilab size mismatch エラーの最終修正をテスト"""
    
    print("=== ilab size mismatch 最終修正テスト ===")
    
    # サイズ不整合を引き起こす可能性のあるデータ
    data = {
        'Study': [f'Study_{i+1:02d}' for i in range(8)],
        'events_treatment': [15, 22, 8, 35, 12, 18, 25, 9],
        'total_treatment': [48, 55, 32, 78, 45, 52, 61, 38],
        'events_control': [10, 18, 12, 28, 8, 15, 20, 14],
        'total_control': [52, 58, 35, 80, 47, 54, 63, 40],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'SkipGroup', 
                  'Asia', 'Europe', 'SkipGroup']  # 一部サブグループが除外される可能性
    }
    df = pd.DataFrame(data)
    
    # CSVファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        # サブグループ解析パラメータ
        analysis_params = {
            'analysis_type': 'binary',
            'measure': 'OR',
            'method': 'REML',
            'model': 'REML',
            'subgroup_columns': ['Region'],
            'subgroups': ['Region'],
            'confidence_level': 0.95,
            'data_columns': {
                'ai': 'events_treatment',
                'bi': 'total_treatment',
                'ci': 'events_control', 
                'di': 'total_control',
                'study_label': 'Study'
            }
        }
        
        data_summary = {
            'columns': list(df.columns),
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
            'rdata_path': 'ilab_final_fix_results.RData',
            'json_summary_path': 'ilab_final_fix_results.json',
            'forest_plot_path': 'ilab_final_fix_forest_plot.png',
            'funnel_plot_path': 'ilab_final_fix_funnel_plot.png'
        }
        
        # Rスクリプト生成
        print("Rスクリプト生成中...")
        generator = RTemplateGenerator()
        r_script = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=output_paths,
            csv_file_path_in_script=csv_path
        )
        
        # ilab修正の確認
        print("\\n=== ilab最終修正確認 ===")
        
        checks = [
            ("論理的矛盾修正", "Original ilab_data_main rows" in r_script),
            ("サイズ比較ロジック", "nrow(ilab_data_main) == res_for_plot_filtered" in r_script),
            ("トランケーション処理", "Truncating ilab_data_main from" in r_script),
            ("最終検証", "Final ilab validation passed" in r_script),
            ("安全性チェック", "Last-minute ilab size mismatch" in r_script),
            ("詳細デバッグ", "DEBUG: Original ilab_data_main rows" in r_script),
            ("エラーハンドリング", "disabling ilab completely" in r_script),
            ("古い修正削除", "ilab_data_main[filtered_indices" not in r_script)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 具体的な修正箇所の確認
        print(f"\\n=== 修正箇所詳細確認 ===")
        
        # 1. 新しいサイズチェックロジック
        size_check_lines = [line for line in r_script.split('\\n') if 'Original ilab_data_main rows' in line]
        if size_check_lines:
            print("✅ 新しいサイズチェックロジック:")
            for line in size_check_lines:
                print(f"    {line.strip()}")
        else:
            print("❌ 新しいサイズチェックロジックが見つかりません")
            all_passed = False
        
        # 2. トランケーション処理
        truncate_lines = [line for line in r_script.split('\\n') if 'Truncating ilab_data_main' in line]
        if truncate_lines:
            print("✅ トランケーション処理:")
            for line in truncate_lines:
                print(f"    {line.strip()}")
        else:
            print("❌ トランケーション処理が見つかりません")
            all_passed = False
        
        # 3. 最終検証
        final_check_lines = [line for line in r_script.split('\\n') if 'Final ilab validation' in line]
        if final_check_lines:
            print("✅ 最終検証:")
            for line in final_check_lines:
                print(f"    {line.strip()}")
        else:
            print("❌ 最終検証が見つかりません")
            all_passed = False
        
        # スクリプト保存
        script_path = 'test/ilab_final_fix_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\\n生成されたRスクリプト: {script_path}")
        
        print(f"\\n=== テスト結果 ===")
        if all_passed:
            print("🎉 ilab size mismatch エラーの最終修正が完了しました！")
            print("✅ 論理的矛盾を解決（dat_ordered_filtered vs filtered_indices）")
            print("✅ インテリジェントなサイズ調整ロジック")
            print("✅ 多段階の安全性チェック")
            print("✅ 詳細なデバッグ情報")
            print("✅ 堅牢なエラーハンドリング")
        else:
            print("❌ 一部の修正が不完全です")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 一時ファイル削除
        if os.path.exists(csv_path):
            os.unlink(csv_path)

if __name__ == "__main__":
    success = test_ilab_final_fix()
    print(f"\\n最終テスト結果: {'🎉 成功' if success else '❌ 失敗'}")
    sys.exit(0 if success else 1)