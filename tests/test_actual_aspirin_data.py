#!/usr/bin/env python3
"""
Test with actual aspirin mortality dataset
実際に問題が発生しているデータセットでテスト
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

# 実際のデータセット（最初の5行のみ）
ACTUAL_CSV_CONTENT = """Study ID,Title,First Author,Year,Country,total number of study,exluded number of study,total male,total female,total ,aspirin male,aspirin female,aspirin total ,control male,control female,control total ,Setting (ICU / non-ICU),ASA timing (Chronic / New),ASA dosage,ASA duration,Comparator (Placebo / Standard care),number of mortality for aspirin,number of patients with aspirin ,number of mortality for control,number of patients with control,"Mortality timepoint (e.g., 28, 90 days)",Sepsis-3 Criteria used
1,Aspirin reduces the mortality risk of sepsis-associated acute kidney injury: an observational study using the MIMIC IV database,Chen,2023,USA,22541,8203,4331,3363,7694,2174,1673,3847,2157,1690,3847,ICU,New,"81 mg for 4279 patients, >300 mg for1596 patients",not reported,standard care,1055,3847,1388,3847,90 days,yes
2,"Chronic aspirin use and survival following sepsis-A propensity-matched, observational cohort study",Lavie,2022,Israel,4393,2722,550,516,,279,254,533,271,262,533,non-ICU,Chronic,75 -100 mg/day ,at least 30 days prior to admission,standard care,124,533,156,533,90 days,yes
3,Acetylsalicylic acid use is associated with improved survival in bacteremic pneumococcal pneumonia: A long-term nationwide study,Rögnvaldsson,2022,Iceland,815,42,428,387,815,72,56,128,356,331,687,Mixed,Chronic,NA,ongoing use prior to ICU,standard care,23,128,124,683,90 days,no
4,Association Between Aspirin Use and Sepsis Outcomes: A National Cohort Study,Hsu,2022,Taiwan,"51,857",1125,30529,21328,51857,7419,5357,12776,23110,15971,39081,Mixed,Chronic,NA,aspirin within 30 days before hospitalization and a history of aspirin use during the prior 180 days,standard care,NA,NA,NA,NA,90 days,yes
5,Lower mortality rate in elderly patients with community-onset pneumonia on treatment with aspirin,Falcone,2015,Italy,"1,005",447,590,415,1005,215,175,390,375,240,615,non-ICU,Chronic,100 mg ,throughout hospitalization,standard care,19,390,144,615,30-day mortality,no"""

async def test_actual_data():
    """実際のaspirin mortality dataの列検出テスト"""
    print("=== Actual Aspirin Data Column Detection Test ===")
    
    # テスト用CSVファイルを作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(ACTUAL_CSV_CONTENT)
        csv_path = f.name
    
    try:
        # Gemini クライアントを初期化
        client = GeminiClient()
        
        # CSVファイルの内容を読み込む
        with open(csv_path, 'r') as f:
            csv_content = f.read()
        
        # CSV分析を実行
        print(f"\nAnalyzing CSV content...")
        
        # CSVの列名を確認
        lines = csv_content.strip().split('\n')
        headers = lines[0].split(',')
        print(f"\nTotal columns: {len(headers)}")
        print("\nRelevant columns:")
        for i, header in enumerate(headers):
            if 'mortality' in header.lower() or 'patient' in header.lower() or 'aspirin' in header.lower() or 'control' in header.lower():
                print(f"  [{i}] {header.strip()}")
        
        result = await client.analyze_csv(csv_content)
        
        # 結果を表示
        print("\n=== Analysis Result ===")
        print(f"Is suitable: {result.get('is_suitable')}")
        print(f"Reason: {result.get('reason')}")
        print(f"Number of studies: {result.get('num_studies')}")
        
        # 検出された列を確認
        detected = result.get('detected_columns', {})
        
        print("\n=== Column Detection Summary ===")
        print(f"Binary intervention events: {detected.get('binary_intervention_events', [])}")
        print(f"Binary intervention total: {detected.get('binary_intervention_total', [])}")
        print(f"Binary control events: {detected.get('binary_control_events', [])}")
        print(f"Binary control total: {detected.get('binary_control_total', [])}")
        print(f"Effect size candidates: {detected.get('effect_size_candidates', [])}")
        print(f"Variance candidates: {detected.get('variance_candidates', [])}")
        
        # 期待される検出結果
        expected_results = {
            'binary_intervention_events': ['number of mortality for aspirin'],
            'binary_intervention_total': ['number of patients with aspirin '],  # Note the trailing space
            'binary_control_events': ['number of mortality for control'],
            'binary_control_total': ['number of patients with control']
        }
        
        # 検証
        print("\n=== Validation ===")
        all_correct = True
        for key, expected in expected_results.items():
            actual = detected.get(key, [])
            is_correct = any(exp.strip() in [a.strip() for a in actual] for exp in expected)
            status = "✓" if is_correct else "✗"
            print(f"{status} {key}: expected {expected}, got {actual}")
            if not is_correct:
                all_correct = False
        
        if all_correct:
            print("\n✅ All columns detected correctly!")
        else:
            print("\n❌ Some columns were not detected correctly.")
            print("\nThis might be why the analysis is falling back to generic inverse method.")
        
        # 推奨される解析タイプ
        print(f"\n=== Suggested Analysis ===")
        suggested = result.get('suggested_analysis', {})
        print(f"Effect type: {suggested.get('effect_type_suggestion')}")
        print(f"Model type: {suggested.get('model_type_suggestion')}")
        
    finally:
        # クリーンアップ
        if os.path.exists(csv_path):
            os.unlink(csv_path)

if __name__ == "__main__":
    asyncio.run(test_actual_data())