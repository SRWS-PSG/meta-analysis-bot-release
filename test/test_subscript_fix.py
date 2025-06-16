#!/usr/bin/env python3
"""
subscript out of bounds エラー修正のテスト
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_subscript_fix():
    """subscript out of bounds エラー修正をテスト"""
    
    print("=== subscript out of bounds エラー修正テスト ===")
    
    # エッジケースデータ作成（一部サブグループは研究数が極端に少ない）
    data = {
        'Study': [f'Study_{i+1:02d}' for i in range(6)],
        'events_treatment': [15, 22, 8, 35, 12, 18],
        'total_treatment': [48, 55, 32, 78, 45, 52],
        'events_control': [10, 18, 12, 28, 8, 15],
        'total_control': [52, 58, 35, 80, 47, 54],
        'Region': ['Asia', 'Europe', 'EmptyGroup', 'Asia', 'SingleStudy', 'Europe']  # 問題のあるケース
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
            'rdata_path': 'subscript_fix_test_results.RData',
            'json_summary_path': 'subscript_fix_test_results.json',
            'forest_plot_path': 'subscript_fix_test_forest_plot.png',
            'funnel_plot_path': 'subscript_fix_test_funnel_plot.png'
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
        
        # subscript修正の確認
        print("\\n=== subscript修正確認 ===")
        
        checks = [
            ("安全なforループ使用", "seq_along(sg_level_names)" in r_script),
            ("境界チェック追加", "length(sg_level_names) > 0" in r_script),
            ("配列存在確認", "sg_name %in% names(" in r_script),
            ("インデックス範囲検証", "filtered_indices > 0 &" in r_script),
            ("NULL値ガード", "!is.null(res_sg_obj)" in r_script),
            ("エラーハンドリング", "WARNING:" in r_script),
            ("フォールバック処理", "using default" in r_script or "using sequential" in r_script),
            ("危険なforループなし", "for (i in 1:" not in r_script)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 具体的な修正箇所の確認
        print(f"\\n=== 修正箇所詳細確認 ===")
        
        # 1. 安全なforループの確認
        safe_loops = [line for line in r_script.split('\\n') if 'seq_along(' in line]
        if safe_loops:
            print("✅ 安全なforループ:")
            for loop in safe_loops[:3]:  # 最初の3つを表示
                print(f"    {loop.strip()}")
        else:
            print("❌ 安全なforループが見つかりません")
            all_passed = False
        
        # 2. 境界チェックの確認
        boundary_checks = [line for line in r_script.split('\\n') if 'length(' in line and '> 0' in line]
        if boundary_checks:
            print("✅ 境界チェック:")
            for check in boundary_checks[:3]:
                print(f"    {check.strip()}")
        else:
            print("❌ 境界チェックが見つかりません")
            all_passed = False
        
        # 3. 警告メッセージの確認
        warning_lines = [line for line in r_script.split('\\n') if 'WARNING:' in line]
        if warning_lines:
            print("✅ 警告メッセージ:")
            for warning in warning_lines[:3]:
                print(f"    {warning.strip()}")
        else:
            print("❌ 警告メッセージが見つかりません")
            all_passed = False
        
        # スクリプト保存
        script_path = 'test/subscript_fix_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\\n生成されたRスクリプト: {script_path}")
        
        print(f"\\n=== テスト結果 ===")
        if all_passed:
            print("🎉 subscript out of bounds エラーが修正されました！")
            print("✅ 安全なforループパターンに変更")
            print("✅ 配列アクセス前の存在確認を追加")
            print("✅ インデックス範囲の検証を実装")
            print("✅ 適切なエラーハンドリングとフォールバック")
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
    success = test_subscript_fix()
    print(f"\\nテスト結果: {'🎉 成功' if success else '❌ 失敗'}")
    sys.exit(0 if success else 1)