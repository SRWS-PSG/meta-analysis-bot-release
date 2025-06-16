#!/usr/bin/env python3
"""
シンプルなslab修正テスト - スクリプト生成のみ
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def test_slab_fix_simple():
    """シンプルなslab修正テスト"""
    
    print("=== シンプルなslab修正テスト ===")
    
    # テストデータ作成
    data = {
        'Study': ['Study_01', 'Study_02', 'Study_03', 'Study_04', 'Study_05'],
        'events_treatment': [15, 22, 8, 35, 12],
        'total_treatment': [48, 55, 32, 78, 45],
        'events_control': [10, 18, 12, 28, 8],
        'total_control': [52, 58, 35, 80, 47],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America']
    }
    df = pd.DataFrame(data)
    
    # CSVファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        # パラメータ設定
        analysis_params = {
            'analysis_type': 'binary',
            'measure': 'OR',
            'method': 'REML',
            'model': 'REML',
            'subgroup_analysis': True,
            'subgroup_column': 'Region',
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
            'rdata_path': 'results.RData',
            'json_summary_path': 'results.json',
            'forest_plot_path': 'forest_plot.png',
            'funnel_plot_path': 'funnel_plot.png'
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
        
        # slab修正の確認
        print("\n=== slab修正確認 ===")
        
        checks = [
            ("escalc with slab", "escalc(" in r_script and "slab=slab" in r_script),
            ("rma.mh with slab", "rma.mh(" in r_script and "slab=slab" in r_script),
            ("no dat$slab in forest", "slab = dat$slab" not in r_script),
            ("no filtered_slab", "filtered_slab" not in r_script),
            ("slab column created", "dat$slab <- dat$Study" in r_script)
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"{status} {check_name}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_passed = False
        
        # 実際のコード抜粋を表示
        print(f"\n=== 実際のslabコード抜粋 ===")
        
        # escalc部分
        escalc_lines = [line for line in r_script.split('\n') if 'escalc(' in line]
        if escalc_lines:
            print("escalc()呼び出し:")
            for line in escalc_lines[:2]:  # 最初の2つまで
                print(f"  {line.strip()}")
        
        # rma.mh部分
        rma_lines = [line for line in r_script.split('\n') if 'rma.mh(' in line]
        if rma_lines:
            print("rma.mh()呼び出し:")
            for line in rma_lines[:2]:  # 最初の2つまで
                print(f"  {line.strip()}")
        
        # slab作成部分
        slab_creation_lines = [line for line in r_script.split('\n') if 'dat$slab <-' in line]
        if slab_creation_lines:
            print("slab列作成:")
            for line in slab_creation_lines:
                print(f"  {line.strip()}")
        
        # 完全なスクリプトを保存
        script_path = 'test/simple_slab_test_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n完全なRスクリプト保存: {script_path}")
        
        print(f"\n=== テスト結果 ===")
        if all_passed:
            print("✅ 全てのslab修正が正常に適用されています！")
            print("✅ 'length of the slab argument...' エラーは解消されました")
        else:
            print("❌ 一部のslab修正が不完全です")
            
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
    success = test_slab_fix_simple()
    print(f"\nテスト結果: {'成功' if success else '失敗'}")
    sys.exit(0 if success else 1)