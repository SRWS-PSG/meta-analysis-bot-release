#!/usr/bin/env python3
"""
実際のサブグループ解析でslabエラー修正をテスト

実際のSlackボット環境に近い条件でサブグループ解析を実行し、
slabエラーが解消されているかを確認
"""

import sys
import os
import tempfile
import pandas as pd
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator
from core.r_executor import RAnalysisExecutor

def create_subgroup_test_data():
    """サブグループ解析用テストデータ（一部にゼロセルを含む）"""
    data = {
        'Study': [f'Study_{i+1:02d}' for i in range(12)],
        'events_treatment': [15, 22, 0, 35, 12, 18, 25, 0, 31, 14, 8, 20],  # ゼロセルあり
        'total_treatment': [48, 55, 32, 78, 45, 52, 61, 38, 72, 49, 35, 58],
        'events_control': [10, 18, 5, 28, 8, 15, 20, 3, 25, 11, 12, 16],
        'total_control': [52, 58, 35, 80, 47, 54, 63, 40, 74, 51, 38, 60],
        'Region': ['Asia', 'Europe', 'Asia', 'Europe', 'America', 
                  'Asia', 'Europe', 'America', 'Europe', 'America',
                  'Asia', 'Europe']  # 複数サブグループ
    }
    return pd.DataFrame(data)

def test_subgroup_slab_fix():
    """実際のサブグループ解析でslabエラー修正をテスト"""
    
    print("=== 実際のサブグループ解析 slab修正テスト ===")
    
    # テストデータ作成
    df = create_subgroup_test_data()
    print(f"テストデータ: {len(df)}研究")
    print(f"サブグループ: {list(df['Region'].value_counts().index)}")
    print(f"各サブグループ研究数: {dict(df['Region'].value_counts())}")
    
    # CSVファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        # パラメータ設定（実際のボット使用に近い設定）
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
            'rdata_path': 'test_results.RData',
            'json_summary_path': 'test_results.json',
            'forest_plot_path': 'test_forest_plot.png',
            'funnel_plot_path': 'test_funnel_plot.png'
        }
        
        # Rスクリプト生成
        print("\n=== Rスクリプト生成 ===")
        generator = RTemplateGenerator()
        r_script = generator.generate_full_r_script(
            analysis_params=analysis_params,
            data_summary=data_summary,
            output_paths=output_paths,
            csv_file_path_in_script=csv_path
        )
        
        # 生成されたスクリプトの検証
        print("\n=== slab修正確認 ===")
        slab_checks = {
            'escalc_slab': 'escalc(measure="OR"' in r_script and 'slab=slab' in r_script,
            'rma_mh_slab': 'rma.mh(' in r_script and 'slab=slab' in r_script,
            'no_dat_slab': 'slab = dat$slab' not in r_script,
            'no_filtered_slab': 'filtered_slab' not in r_script
        }
        
        for check, passed in slab_checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}: {'PASS' if passed else 'FAIL'}")
        
        # スクリプトを保存
        script_path = 'test/test_subgroup_slab_script.R'
        with open(script_path, 'w') as f:
            f.write(r_script)
        print(f"\n生成されたRスクリプト: {script_path}")
        
        # 実際にRスクリプトを実行してエラーがないか確認  
        print("\n=== Rスクリプト実行テスト ===")
        
        try:
            # 一時ディレクトリで実行
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # CSVファイルを一時ディレクトリにコピー
                temp_csv = os.path.join(temp_dir, 'test_data.csv')
                df.to_csv(temp_csv, index=False)
                
                # スクリプト内のパスを更新
                updated_script = r_script.replace(csv_path, temp_csv)
                
                # 出力パスを一時ディレクトリに変更
                for old_path, new_path in [
                    ('test_results.RData', os.path.join(temp_dir, 'results.RData')),
                    ('test_results.json', os.path.join(temp_dir, 'results.json')),
                    ('test_forest_plot.png', os.path.join(temp_dir, 'forest.png')),
                    ('test_funnel_plot.png', os.path.join(temp_dir, 'funnel.png'))
                ]:
                    updated_script = updated_script.replace(old_path, new_path)
                
                # Rスクリプトをファイルに保存
                script_file = os.path.join(temp_dir, 'test_script.R')
                with open(script_file, 'w') as f:
                    f.write(updated_script)
                
                print("Rスクリプト実行中...")
                
                # subprocessでR実行
                import subprocess
                result = subprocess.run(
                    ['R', '--slave', '--no-restore', '--file=' + script_file],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                success = result.returncode == 0
                
                if success:
                    print("✅ Rスクリプト実行成功！slabエラーは解消されました")
                    
                    # 生成されたファイルを確認
                    output_files = os.listdir(temp_dir)
                    print(f"生成されたファイル: {output_files}")
                    
                    # JSONファイルの内容確認
                    json_path = os.path.join(temp_dir, 'results.json')
                    if os.path.exists(json_path):
                        import json
                        with open(json_path, 'r') as f:
                            results = json.load(f)
                        
                        if 'overall_analysis' in results:
                            overall = results['overall_analysis']
                            print(f"\n解析結果:")
                            print(f"  研究数: {overall.get('k', 'N/A')}")
                            print(f"  統合OR: {overall.get('estimate', 'N/A'):.3f}")
                            print(f"  95%CI: [{overall.get('ci_lb', 'N/A'):.3f}, {overall.get('ci_ub', 'N/A'):.3f}]")
                            print(f"  I²: {overall.get('I2', 'N/A'):.1f}%")
                            
                        if 'zero_cells_summary' in results:
                            zero_cells = results['zero_cells_summary']
                            print(f"\nゼロセル情報:")
                            print(f"  ゼロセルを含む研究: {zero_cells.get('studies_with_zero_cells', 'N/A')}件")
                    
                else:
                    print("❌ Rスクリプト実行失敗")
                    print(f"stdout: {result.stdout}")
                    print(f"stderr: {result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"❌ R実行テスト中にエラー: {e}")
            return False
        
        # 全チェック結果
        all_passed = all(slab_checks.values())
        print(f"\n=== 総合結果 ===")
        if all_passed:
            print("✅ 全てのslab修正が正常に適用されています")
            print("✅ Rスクリプトが正常に実行されました") 
            print("✅ 'length of the slab argument...' エラーは解消されました")
        else:
            print("❌ 一部のslab修正が不完全です")
            
        return all_passed
        
    except Exception as e:
        print(f"❌ テスト中にエラー発生: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 一時ファイル削除
        if os.path.exists(csv_path):
            os.unlink(csv_path)

if __name__ == "__main__":
    success = test_subgroup_slab_fix()
    print(f"\nテスト結果: {'成功' if success else '失敗'}")
    sys.exit(0 if success else 1)