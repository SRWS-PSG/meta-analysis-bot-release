#!/usr/bin/env python3
"""
subscript out of bounds エラーのデバッグと修正案
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def analyze_subscript_error():
    """subscript out of bounds エラーの原因を分析"""
    
    print("=== subscript out of bounds エラー分析 ===")
    
    # エラーが発生する可能性のある箇所を特定
    potential_issues = [
        {
            "location": "rows_list[[sg_name]] アクセス",
            "code": "max(rows_list[[sg_name]]) + 0.5",
            "issue": "sg_nameがrows_listに存在しない場合",
            "fix": "if (sg_name %in% names(rows_list) && length(rows_list[[sg_name]]) > 0)"
        },
        {
            "location": "subtotal_rows[sg_name] アクセス", 
            "code": "subtotal_row <- subtotal_rows[sg_name]",
            "issue": "sg_nameがsubtotal_rowsに存在しない場合",
            "fix": "if (sg_name %in% names(subtotal_rows))"
        },
        {
            "location": "res_by_subgroup配列アクセス",
            "code": "res_sg_obj <- res_by_subgroup_Region[[sg_name]]",
            "issue": "sg_nameが結果リストに存在しない場合",
            "fix": "if (sg_name %in% names(res_by_subgroup_Region))"
        },
        {
            "location": "filtered_indices配列アクセス",
            "code": "res_for_plot_filtered$yi[filtered_indices]",
            "issue": "filtered_indicesが元データより大きい値を含む場合",
            "fix": "filtered_indices <- filtered_indices[filtered_indices <= length(res_for_plot$yi)]"
        },
        {
            "location": "sg_level_names配列アクセス",
            "code": "for (i in 1:n_sg_levels) { sg_name <- sg_level_names[i]",
            "issue": "n_sg_levelsが0またはsg_level_namesが空の場合",
            "fix": "if (length(sg_level_names) > 0 && n_sg_levels > 0)"
        }
    ]
    
    print("\\n潜在的な問題箇所:")
    for i, issue in enumerate(potential_issues, 1):
        print(f"{i}. {issue['location']}")
        print(f"   問題: {issue['issue']}")
        print(f"   修正案: {issue['fix']}")
        print()
    
    # 修正パターンの提案
    print("=== 修正パターン ===")
    print("""
1. **配列アクセス前の存在チェック**:
   ```r
   if (sg_name %in% names(rows_list) && length(rows_list[[sg_name]]) > 0) {
       # 安全なアクセス
       max_row <- max(rows_list[[sg_name]])
   }
   ```

2. **ループ境界の安全な設定**:
   ```r
   if (length(sg_level_names) > 0) {
       for (i in seq_along(sg_level_names)) {
           sg_name <- sg_level_names[i]
           # 処理
       }
   }
   ```

3. **フィルタリングインデックスの範囲チェック**:
   ```r
   max_index <- length(res_for_plot$yi)
   filtered_indices <- filtered_indices[filtered_indices > 0 & filtered_indices <= max_index]
   ```

4. **NULL値ガード**:
   ```r
   if (!is.null(res_sg_obj) && !is.null(rows_list[[sg_name]])) {
       # 安全な処理
   }
   ```
""")
    
    print("=== 修正の優先順位 ===")
    priority_fixes = [
        "1. forループの境界チェック (最も重要)",
        "2. 配列アクセス前の存在確認",
        "3. NULL値ガードの追加", 
        "4. インデックス範囲の検証"
    ]
    
    for fix in priority_fixes:
        print(f"  {fix}")
        
    return potential_issues

if __name__ == "__main__":
    issues = analyze_subscript_error()
    print(f"\\n検出された潜在的問題: {len(issues)}件")