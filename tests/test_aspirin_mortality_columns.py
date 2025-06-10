#!/usr/bin/env python3
"""
Test case for aspirin mortality data column detection issue
問題: "number of patients with aspirin" などの列名が正しく検出されない
"""

import asyncio
import csv
import os
import sys
import tempfile
import json

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gemini_client import GeminiClient

# テスト用CSVデータ（実際の問題で使われている列名を再現）
TEST_CSV_CONTENT = """Study,number of mortality for aspirin,number of patients with aspirin,number of mortality for control,number of patients with control
Study 1,15,150,25,148
Study 2,8,120,15,125
Study 3,12,200,18,195
Study 4,5,80,10,85
Study 5,20,250,30,245
"""

async def test_column_detection():
    """Aspirin mortality data の列検出テスト"""
    print("=== Aspirin Mortality Column Detection Test ===")
    
    # テスト用CSVファイルを作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(TEST_CSV_CONTENT)
        csv_path = f.name
    
    try:
        # Gemini クライアントを初期化
        client = GeminiClient()
        
        # CSVファイルの内容を読み込む
        with open(csv_path, 'r') as f:
            csv_content = f.read()
        
        # CSV分析を実行
        print(f"\nAnalyzing CSV content...")
        print(f"CSV Preview:\n{csv_content[:200]}...")
        result = await client.analyze_csv(csv_content)
        
        # 結果を表示
        print("\n=== Analysis Result ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 検出された列を確認
        detected = result.get('detected_columns', {})
        
        print("\n=== Column Detection Summary ===")
        print(f"Binary intervention events: {detected.get('binary_intervention_events', [])}")
        print(f"Binary intervention total: {detected.get('binary_intervention_total', [])}")
        print(f"Binary control events: {detected.get('binary_control_events', [])}")
        print(f"Binary control total: {detected.get('binary_control_total', [])}")
        
        # 期待される検出結果
        expected_results = {
            'binary_intervention_events': ['number of mortality for aspirin'],
            'binary_intervention_total': ['number of patients with aspirin'],
            'binary_control_events': ['number of mortality for control'],
            'binary_control_total': ['number of patients with control']
        }
        
        # 検証
        print("\n=== Validation ===")
        all_correct = True
        for key, expected in expected_results.items():
            actual = detected.get(key, [])
            is_correct = expected == actual
            status = "✓" if is_correct else "✗"
            print(f"{status} {key}: expected {expected}, got {actual}")
            if not is_correct:
                all_correct = False
        
        if all_correct:
            print("\n✅ All columns detected correctly!")
        else:
            print("\n❌ Some columns were not detected correctly.")
            print("\nThis might be why the analysis is falling back to generic inverse method.")
        
    finally:
        # クリーンアップ
        if os.path.exists(csv_path):
            os.unlink(csv_path)

if __name__ == "__main__":
    asyncio.run(test_column_detection())