#!/usr/bin/env python3
"""
サブグループ解析生成テスト
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_subgroup_generation():
    """サブグループ解析生成をテスト"""
    
    print("=== サブグループ解析生成テスト ===")
    
    # テストデータ作成（サブグループを強調）
    data = {
        'Study': ['Study_01', 'Study_02', 'Study_03', 'Study_04', 'Study_05', 'Study_06'],
        'events_treatment': [15, 22, 8, 35, 12, 18],
        'total_treatment': [48, 55, 32, 78, 45, 52],
        'events_control': [10, 18, 12, 28, 8, 15],
        'total_control': [52, 58, 35, 80, 47, 54],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America', 'America']  # 3つのサブグループ
    }
    df = pd.DataFrame(data)
    print(f"テストデータ: {len(df)}研究")
    print(f"サブグループ別研究数: {dict(df['Region'].value_counts())}")
    
    # CSVファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        # パラメータ設定（サブグループ解析を明示的に有効化）
        analysis_params = {
            'analysis_type': 'binary',
            'measure': 'OR',
            'method': 'REML',
            'model': 'REML',
            'subgroup_columns': ['Region'],      # 重要：サブグループ列をリストで指定
            'subgroups': ['Region'],             # 代替パラメータも設定
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
                'subgroup_candidates': ['Region']  # サブグループ候補を明示
            }
        }
        
        output_paths = {
            'rdata_path': 'results.RData',
            'json_summary_path': 'results.json',
            'forest_plot_path': 'forest_plot.png',
            'funnel_plot_path': 'funnel_plot.png'
        }
        
        # Rスクリプト生成
        print("\nRスクリプト生成中...")
        generator = RTemplateGenerator()
        r_script = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=output_paths,
            csv_file_path_in_script=csv_path
        )
        
        # サブグループ解析の確認
        print("\n=== サブグループ解析確認 ===")
        
        subgroup_checks = [
            ("Subgroup analysis code", "Region" in r_script),
            ("Subgroup forest plot", "subgroup_forest_plot" in r_script or "SUBGROUP" in r_script),
            ("Subgroup variable creation", "subgroup_col" in r_script or "Region" in r_script),
            ("Multiple subgroups", r_script.count("Asia") > 0 or "Europe" in r_script),
            ("Slab in subgroup", "slab=" in r_script and "Region" in r_script)
        ]
        
        subgroup_found = False
        for check_name, passed in subgroup_checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if passed and "forest" in check_name.lower():
                subgroup_found = True
        
        # スクリプト内容の詳細確認
        print(f"\n=== スクリプト内容分析 ===")
        lines = r_script.split('\n')
        
        # サブグループ関連の行を検索
        subgroup_lines = [i for i, line in enumerate(lines) if 'Region' in line or 'subgroup' in line.lower()]
        
        if subgroup_lines:
            print(f"サブグループ関連コード（{len(subgroup_lines)}行）:")
            for line_num in subgroup_lines[:10]:  # 最初の10行まで
                print(f"  {line_num+1}: {lines[line_num].strip()}")
        else:
            print("❌ サブグループ関連コードが見つかりません")
            
            # デバッグ：パラメータがどう処理されているか確認
            print("\nデバッグ情報:")
            print(f"  subgroup_analysis: {analysis_params.get('subgroup_analysis')}")
            print(f"  subgroup_column: {analysis_params.get('subgroup_column')}")
            
            # テンプレート生成器の内部処理をチェック
            print("\nテンプレート生成処理の確認:")
            if hasattr(generator, '_generate_subgroup_code'):
                print("  _generate_subgroup_code メソッドが存在します")
            else:
                print("  _generate_subgroup_code メソッドが見つかりません")
        
        # スクリプトを保存
        script_path = 'test/subgroup_generation_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n完全なRスクリプト保存: {script_path}")
        
        # ファイルサイズで複雑さを確認
        script_size = len(r_script)
        print(f"生成されたスクリプトサイズ: {script_size:,} 文字")
        
        print(f"\n=== テスト結果 ===")
        if subgroup_found:
            print("✅ サブグループ解析が正常に生成されました！")
        else:
            print("❌ サブグループ解析が生成されていません")
            print("原因を調査する必要があります")
            
        return subgroup_found
        
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
    success = test_subgroup_generation()
    print(f"\nテスト結果: {'成功' if success else '失敗'}")
    sys.exit(0 if success else 1)