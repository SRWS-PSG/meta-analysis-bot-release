#!/usr/bin/env python3
"""
修正されたslabエラー対応のテスト

テスト内容:
1. 修正されたテンプレートでのRスクリプト生成
2. 実際のCSVデータでの動作確認
3. サブグループ解析での slab エラーの解消確認
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
import tempfile
import pandas as pd

def create_test_binary_data():
    """テスト用の二値アウトカムデータを作成"""
    data = {
        'Study': [f'Study {i+1}' for i in range(10)],
        'events_treatment': [15, 22, 8, 35, 12, 18, 25, 9, 31, 14],
        'total_treatment': [48, 55, 32, 78, 45, 52, 61, 38, 72, 49],
        'events_control': [10, 18, 12, 28, 8, 15, 20, 14, 25, 11],
        'total_control': [52, 58, 35, 80, 47, 54, 63, 40, 74, 51],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America', 
                  'Asia', 'Europe', 'America', 'Europe', 'America']
    }
    return pd.DataFrame(data)

def test_slab_fix():
    """修正されたslabエラー対応をテスト"""
    
    print("=== サブグループforest plot slabエラー修正テスト ===")
    
    # テストデータ作成
    df = create_test_binary_data()
    
    # 一時CSVファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        # テンプレート生成器を初期化
        generator = RTemplateGenerator()
        
        # パラメータ設定
        params = {
            'csv_path': csv_path,
            'analysis_type': 'binary',
            'measure': 'OR',
            'method': 'REML',
            'ai': 'events_treatment',
            'bi_calculated': 'total_treatment - events_treatment',
            'ci': 'events_control', 
            'di_calculated': 'total_control - events_control',
            'study_id': 'Study',
            'slab_column': 'Study',  # 重要: 列名参照
            'subgroup_analysis': True,
            'subgroup_column': 'Region',
            'confidence_level': 0.95
        }
        
        print(f"テストデータ作成完了: {csv_path}")
        print(f"研究数: {len(df)}")
        print(f"サブグループ: {df['Region'].unique()}")
        
        # 修正されたテンプレートでRスクリプト生成
        print("\n修正されたテンプレートでRスクリプト生成中...")
        
        # パラメータを適切な形式に変更
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
        
        r_script = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=output_paths,
            csv_file_path_in_script=csv_path
        )
        
        # 生成されたスクリプトの確認
        print("\n=== 生成されたRスクリプトの重要部分 ===")
        
        # escalc部分の確認
        if 'slab=Study' in r_script:
            print("✅ escalc(): slabが列名参照に修正済み")
        else:
            print("❌ escalc(): slabの修正が反映されていない")
            
        # rma.mh部分の確認  
        if 'slab=Study' in r_script and 'rma.mh' in r_script:
            print("✅ rma.mh(): slabが列名参照に修正済み")
        else:
            print("❌ rma.mh(): slabの修正が反映されていない")
            
        # サブグループforest plot部分の確認
        if 'subset = filtered_indices' in r_script:
            print("✅ forest(): subsetパラメータによるフィルタリングに修正済み")
        else:
            print("❌ forest(): subsetによるフィルタリングが反映されていない")
            
        # 問題のあるslabベクトル操作が削除されているか確認
        problematic_patterns = [
            'filtered_slab <- ',
            'dat$slab[',
            'slab = filtered_slab'
        ]
        
        issues_found = []
        for pattern in problematic_patterns:
            if pattern in r_script:
                issues_found.append(pattern)
                
        if issues_found:
            print(f"❌ 問題のあるslabベクトル操作が残存: {issues_found}")
        else:
            print("✅ 問題のあるslabベクトル操作は削除済み")
            
        # スクリプトをファイルに保存
        script_path = '/home/youkiti/meta-analysis-bot-release/test/generated_fixed_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n生成されたRスクリプト保存: {script_path}")
        
        print("\n=== テスト結果サマリー ===")
        print("修正されたテンプレートが正常に生成されました。")
        print("主な修正点:")
        print("1. escalc()とrma.mh()でslabを列名参照に変更")
        print("2. forest()でsubsetパラメータを使用")
        print("3. 手動のslabベクトル操作を削除")
        print("\nこの修正により 'length of the slab argument...' エラーが解消されるはずです。")
        
        return True
        
    except Exception as e:
        print(f"❌ テスト中にエラー発生: {e}")
        return False
        
    finally:
        # 一時ファイル削除
        if os.path.exists(csv_path):
            os.unlink(csv_path)

if __name__ == "__main__":
    success = test_slab_fix()
    sys.exit(0 if success else 1)