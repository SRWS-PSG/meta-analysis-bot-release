#!/usr/bin/env python3
"""
Analyze the R template generation to identify why version info is missing in subgroup analysis.
"""

import os
import sys
import re

# プロジェクトのルートディレクトリを Python パスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from templates.r_templates import RTemplateGenerator

def analyze_template_generation():
    """テンプレート生成の流れを分析"""
    
    # テスト用のパラメータ（サブグループ解析）
    analysis_params = {
        'measure': 'OR',
        'model': 'REML',
        'data_columns': {
            'ai': 'Intervention_Events',
            'ci': 'Control_Events',
            'n1i': 'Intervention_Total',
            'n2i': 'Control_Total',
            'study_label': 'Study'
        },
        'subgroup_columns': ['Region']
    }
    
    data_summary = {
        'columns': ['Study', 'Intervention_Events', 'Control_Events', 
                   'Intervention_Total', 'Control_Total', 'Region'],
        'shape': [10, 6]
    }
    
    output_paths = {
        'forest_plot_path': '/tmp/forest_plot.png',
        'funnel_plot_path': '/tmp/funnel_plot.png',
        'rdata_path': '/tmp/result.RData',
        'json_summary_path': '/tmp/summary.json',
        'forest_plot_subgroup_prefix': '/tmp/forest_plot_subgroup'
    }
    
    # テンプレート生成
    generator = RTemplateGenerator()
    
    # save_resultsセクションを生成
    save_code = generator._generate_save_code(analysis_params, output_paths, data_summary)
    
    # save_codeの内容を分析
    print("=== Analyzing save_results code ===\n")
    
    # tryCatchブロックの確認
    trycatch_blocks = re.findall(r'tryCatch\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', save_code, re.DOTALL)
    print(f"Number of tryCatch blocks found: {len(trycatch_blocks)}\n")
    
    # バージョン情報の追加位置を確認
    version_info_pattern = r'summary_list\$r_version\s*<-\s*R\.version\.string'
    version_match = re.search(version_info_pattern, save_code)
    
    if version_match:
        print("✅ Version information assignment found!")
        # バージョン情報の前後のコンテキストを表示
        start = max(0, version_match.start() - 200)
        end = min(len(save_code), version_match.end() + 200)
        context = save_code[start:end]
        print(f"\nContext around version info:\n{'-' * 50}")
        print(context)
        print('-' * 50)
        
        # バージョン情報がtryCatchブロック内にあるか確認
        for i, block in enumerate(trycatch_blocks):
            if 'summary_list$r_version' in block:
                print(f"\n✅ Version info is inside tryCatch block #{i+1}")
                # エラーハンドリング部分を確認
                error_handler = re.search(r'error\s*=\s*function\s*\([^)]+\)\s*\{([^}]+)\}', save_code[version_match.start():])
                if error_handler:
                    print(f"\nError handler found after version info:")
                    print(error_handler.group(1).strip())
                break
        else:
            print("\n❌ Version info is NOT inside any tryCatch block!")
    else:
        print("❌ Version information assignment NOT found!")
    
    # サブグループ関連のコードがバージョン情報の前にあるか確認
    print("\n=== Checking code order ===")
    subgroup_pattern = r'subgroup_json_update_code'
    subgroup_match = re.search(subgroup_pattern, save_code)
    
    if subgroup_match and version_match:
        if subgroup_match.start() < version_match.start():
            print("✅ Subgroup code is before version info (correct order)")
        else:
            print("❌ Subgroup code is after version info (incorrect order)")
    
    # プレースホルダーの確認
    placeholders = re.findall(r'\{(\w+)\}', save_code)
    print(f"\n=== Placeholders found: {set(placeholders)} ===")
    
    # 実際に生成される完全なコードを表示
    print("\n=== Full generated save_results code ===")
    print("(First 2000 characters)")
    print(save_code[:2000])
    print("\n... (truncated) ...\n")
    print("(Last 1000 characters)")
    print(save_code[-1000:])

if __name__ == "__main__":
    analyze_template_generation()