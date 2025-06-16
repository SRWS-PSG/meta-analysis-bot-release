#!/usr/bin/env python3
"""
ilab (19) vs original dataset (20) 問題の分析
1カテゴリのみのサブグループ除外による不整合を解決
"""

print("=== ilab 19 vs 20 問題分析 ===")

print("""
問題の流れ:
1. 元データ: 20件の研究
2. サブグループ分析で1件の研究が除外（n=1のサブグループ）
3. dat_ordered_filtered: 19件（除外後）
4. ilab_data_main: dat_ordered_filteredから作成 → 19件
5. res_for_plot: 元の20件のデータ
6. forest plot: res_for_plotの20件を期待

解決策:
res_for_plotも同様に1カテゴリのサブグループを除外する必要がある

修正方針:
1. res_for_plotの作成時点で、n=1のサブグループを持つ研究を除外
2. またはforest plot生成時に、dat_ordered_filteredに存在する研究のみを使用
""")