#!/usr/bin/env python3
"""
subset引数エラー修正のテスト
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_subset_fix():
    """subset引数エラー修正をテスト"""
    
    print("=== subset引数エラー修正テスト ===")
    
    # テストデータ作成
    data = {
        'Study': [f'Study_{i+1:02d}' for i in range(8)],
        'events_treatment': [15, 22, 8, 35, 12, 18, 25, 9],
        'total_treatment': [48, 55, 32, 78, 45, 52, 61, 38],
        'events_control': [10, 18, 12, 28, 8, 15, 20, 14],
        'total_control': [52, 58, 35, 80, 47, 54, 63, 40],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America', 
                  'Asia', 'Europe', 'America']
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
            'rdata_path': 'subset_test_results.RData',
            'json_summary_path': 'subset_test_results.json',
            'forest_plot_path': 'subset_test_forest_plot.png',
            'funnel_plot_path': 'subset_test_funnel_plot.png'
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
        
        # subset修正の確認
        print("\n=== subset修正確認 ===")
        
        checks = [
            ("No subset parameter", "subset = filtered_indices" not in r_script),
            ("Uses filtered data", "x = res_for_plot_filtered" in r_script),
            ("Slab filtering", "res_for_plot_filtered$slab" in r_script),
            ("Debug message", "no subset parameter needed" in r_script),
            ("Has subgroup analysis", "SUBGROUP FOREST PLOT START" in r_script)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 具体的なforest()呼び出しを確認
        print(f"\n=== forest()呼び出し確認 ===")
        forest_calls = []
        lines = r_script.split('\n')
        for i, line in enumerate(lines):
            if 'forest_sg_args <- list(' in line:
                # 次の数行を取得して引数を確認
                args_section = []
                for j in range(i, min(i+10, len(lines))):
                    args_section.append(lines[j].strip())
                    if ')' in lines[j] and 'forest_sg_args' not in lines[j]:
                        break
                forest_calls.append('\n'.join(args_section))
        
        if forest_calls:
            print("forest()呼び出し:")
            for call in forest_calls:
                print(f"  {call}")
                
            # subset引数がないことを確認
            has_subset = any('subset =' in call for call in forest_calls)
            if has_subset:
                print("❌ まだsubset引数が残っています")
                all_passed = False
            else:
                print("✅ subset引数は削除されています")
        else:
            print("❌ forest()呼び出しが見つかりません")
            all_passed = False
        
        # スクリプト保存
        script_path = 'test/subset_fix_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n生成されたRスクリプト: {script_path}")
        
        print(f"\n=== テスト結果 ===")
        if all_passed:
            print("✅ subset引数エラーが修正されました！")
            print("✅ フィルタ済みデータを使用するように変更されました")
            print("✅ slabデータの整合性も確保されています")
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
    success = test_subset_fix()
    print(f"\nテスト結果: {'成功' if success else '失敗'}")
    sys.exit(0 if success else 1)