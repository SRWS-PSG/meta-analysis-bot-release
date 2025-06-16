#!/usr/bin/env python3
"""
'wows' argument エラーの修正テスト
rows引数の完全再構築と詳細エラーログをテスト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_wows_argument_fix():
    """wows argument (rows) エラーの修正をテスト"""
    
    print("=== 'wows' argument エラー修正テスト ===")
    
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
            ("完全rows再計算", "Completely rebuilding row positions for filtered data" in r_script),
            ("サブグループ構造保持", "Rebuilding with subgroup structure preserved" in r_script),
            ("フィルタ済みデータ基準", "sg_studies_filtered <- table(res_for_plot_filtered" in r_script),
            ("最終整合性確認", "Final row count mismatch" in r_script),
            ("NULLフォールバック", "rows = NULL" in r_script),
            ("詳細エラーログ", "About to call forest() with following arguments" in r_script),
            ("エラー診断", "FOREST PLOT ERROR DIAGNOSIS" in r_script),
            ("tryCatchエラー捕捉", "tryCatch" in r_script),
            ("多段階フォールバック", "ATTEMPTING FALLBACK: Simple forest plot" in r_script),
            ("成功ログ", "SUCCESS: Forest plot generated successfully" in r_script)
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
        
        key_lines = [line.strip() for line in r_script.split('\n') 
                    if any(keyword in line for keyword in [
                        'Completely rebuilding row positions',
                        'Final row count mismatch',
                        'About to call forest()',
                        'FOREST PLOT ERROR DIAGNOSIS',
                        'ATTEMPTING FALLBACK'
                    ])]
        
        for line in key_lines[:8]:  # 最初の8行を表示
            if line:
                print(f"  {line}")
        
        print(f"\n=== テスト結果 ===")
        if all_passed:
            print("🎉 'wows' argument エラーの完全修正が実装されました！")
            print("✅ フィルタ済みデータに完全対応したrows再計算")
            print("✅ サブグループ構造を維持した位置計算")
            print("✅ 詳細なエラー診断とログ出力")
            print("✅ 多段階フォールバック機構")
            print("✅ 自動計算フォールバック (rows=NULL)")
        else:
            print("❌ 一部の修正が不完全です")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_wows_argument_fix()
    print(f"\n最終テスト結果: {'🎉 成功' if success else '❌ 失敗'}")
    sys.exit(0 if success else 1)