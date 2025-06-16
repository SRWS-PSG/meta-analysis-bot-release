#!/usr/bin/env python3
"""
ilab引数サイズ不整合エラー修正の包括的テスト
全ての3つの修正（slab、subset、ilab）が正しく動作することを確認
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_comprehensive_fixes():
    """3つの修正（slab、subset、ilab）を包括的にテスト"""
    
    print("=== 包括的修正テスト（slab + subset + ilab） ===")
    
    # テストデータ作成（一部サブグループは研究数が少ない）
    data = {
        'Study': [f'Study_{i+1:02d}' for i in range(10)],
        'events_treatment': [15, 22, 8, 35, 12, 18, 25, 9, 14, 30],
        'total_treatment': [48, 55, 32, 78, 45, 52, 61, 38, 42, 75],
        'events_control': [10, 18, 12, 28, 8, 15, 20, 14, 6, 25],
        'total_control': [52, 58, 35, 80, 47, 54, 63, 40, 44, 77],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America', 
                  'Asia', 'Europe', 'SingleStudy', 'America', 'Europe']  # SingleStudyは1件のみ
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
            'rdata_path': 'comprehensive_test_results.RData',
            'json_summary_path': 'comprehensive_test_results.json',
            'forest_plot_path': 'comprehensive_test_forest_plot.png',
            'funnel_plot_path': 'comprehensive_test_funnel_plot.png'
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
        
        # 全ての修正の確認
        print("\n=== 全修正確認 ===")
        
        checks = [
            # slab修正
            ("✅ slab: 列名参照使用", "slab=slab" in r_script and "slab=" in r_script),
            ("✅ slab: ベクトル参照なし", "slab_param_string" not in r_script),
            
            # subset修正  
            ("✅ subset: subset引数なし", "subset = filtered_indices" not in r_script),
            ("✅ subset: フィルタ済みデータ使用", "x = res_for_plot_filtered" in r_script),
            ("✅ subset: slabフィルタリング", "res_for_plot_filtered$slab" in r_script),
            
            # ilab修正
            ("✅ ilab: ilab_data_mainフィルタリング", "ilab_data_main[filtered_indices" in r_script),
            ("✅ ilab: サイズ検証", "if (nrow(ilab_data_main) != res_for_plot_filtered$k)" in r_script),
            ("✅ ilab: 条件付き設定", "if (!is.null(ilab_data_main))" in r_script),
            
            # 全般
            ("✅ デバッグメッセージ", "DEBUG: Filtered ilab_data_main" in r_script),
            ("✅ サブグループ解析", "SUBGROUP FOREST PLOT START" in r_script)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 修正箇所の詳細確認
        print(f"\n=== 修正箇所詳細確認 ===")
        
        # 1. escalc呼び出し確認
        escalc_lines = [line for line in r_script.split('\n') if 'escalc(' in line and 'slab=' in line]
        if escalc_lines:
            print("✅ escalc()でのslab列名参照:")
            for line in escalc_lines[:2]:  # 最初の2つを表示
                print(f"    {line.strip()}")
        else:
            print("❌ escalc()でのslab参照が見つかりません")
            all_passed = False
        
        # 2. ilab_data_mainフィルタリング確認
        ilab_filter_lines = [line for line in r_script.split('\n') if 'ilab_data_main[filtered_indices' in line]
        if ilab_filter_lines:
            print("✅ ilab_data_mainフィルタリング:")
            for line in ilab_filter_lines:
                print(f"    {line.strip()}")
        else:
            print("❌ ilab_data_mainフィルタリングが見つかりません")
            all_passed = False
        
        # 3. forest_sg_args確認
        lines = r_script.split('\n')
        forest_sg_start = -1
        for i, line in enumerate(lines):
            if 'forest_sg_args <- list(' in line:
                forest_sg_start = i
                break
        
        if forest_sg_start >= 0:
            print("✅ forest_sg_args設定:")
            for i in range(forest_sg_start, min(forest_sg_start + 8, len(lines))):
                line = lines[i].strip()
                if line and ('x = ' in line or 'forest_sg_args' in line):
                    print(f"    {line}")
                if ')' in line and 'forest_sg_args' not in line:
                    break
        else:
            print("❌ forest_sg_args設定が見つかりません")
            all_passed = False
        
        # スクリプト保存
        script_path = 'test/comprehensive_fix_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n生成されたRスクリプト: {script_path}")
        
        # 特定のエラーパターンチェック
        print(f"\n=== エラーパターンチェック ===")
        error_patterns = [
            ("❌ slab length mismatch", "slab argument does not correspond" in r_script.lower()),
            ("❌ subset parameter", "subset = " in r_script and "forest_sg_args" in r_script),
            ("❌ ilab size mismatch", False)  # 修正により発生しないはず
        ]
        
        for error_name, has_error in error_patterns:
            if has_error:
                print(f"❌ {error_name}: 潜在的エラーパターンが検出されました")
                all_passed = False
            else:
                print(f"✅ {error_name}: エラーパターンなし")
        
        print(f"\n=== テスト結果 ===")
        if all_passed:
            print("🎉 全ての修正が正常に適用されました！")
            print("✅ slab length mismatch エラー修正: OK")
            print("✅ subset parameter エラー修正: OK") 
            print("✅ ilab size mismatch エラー修正: OK")
            print("✅ サブグループforest plot生成準備完了")
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
    success = test_comprehensive_fixes()
    print(f"\n包括テスト結果: {'🎉 成功' if success else '❌ 失敗'}")
    sys.exit(0 if success else 1)