#!/usr/bin/env python3
"""
サブグループフォレストプロットの修正を適用するスクリプト
"""

import sys
import os
sys.path.append('/home/youkiti/meta-analysis-bot-release')

def apply_subgroup_fix():
    """サブグループフォレストプロットテンプレートを修正版に置き換える"""
    
    # 修正されたテンプレート
    new_template = '''            "subgroup_forest_plot_template": """
# サブグループ '{subgroup_col_name}' のフォレストプロット (修正版)

print("=== SUBGROUP FOREST PLOT START: {subgroup_col_name} ===")

# 前提条件をシンプルに確認
has_subgroup_results <- exists("res_by_subgroup_{safe_var_name}") && 
                       length(res_by_subgroup_{safe_var_name}) > 0 &&
                       !is.null(res_by_subgroup_{safe_var_name})

has_plot_model <- exists("{res_for_plot_model_name}") && 
                 !is.null({res_for_plot_model_name})

if (!has_subgroup_results) {{
    print("WARNING: No subgroup results found for {subgroup_col_name}")
    next
}}

if (!has_plot_model) {{
    print("WARNING: Plot model {res_for_plot_model_name} not found")
    next  
}}

print("DEBUG: Prerequisites met, starting plot generation")

# 有効なサブグループを取得
valid_subgroups <- names(res_by_subgroup_{safe_var_name})
valid_subgroups <- valid_subgroups[!sapply(res_by_subgroup_{safe_var_name}, is.null)]

if (length(valid_subgroups) == 0) {{
    print("WARNING: No valid subgroups found")
    next
}}

print(paste("DEBUG: Valid subgroups:", paste(valid_subgroups, collapse=", ")))

# 除外されたサブグループ情報を記録
all_subgroups_in_data <- unique(dat[['{subgroup_col_name}']])
excluded_subgroups <- setdiff(all_subgroups_in_data, valid_subgroups)

if (length(excluded_subgroups) > 0) {{
    excluded_info <- list(
        excluded_subgroups = excluded_subgroups,
        reason = "insufficient_data_n_le_1",
        included_subgroups = valid_subgroups
    )
    
    # summary_listに直接追加
    if (!exists("summary_list")) {{
        summary_list <- list()
    }}
    if (is.null(summary_list$subgroup_exclusions)) {{
        summary_list$subgroup_exclusions <- list()
    }}
    summary_list$subgroup_exclusions[['{subgroup_col_name}']] <- excluded_info
    
    print(paste("DEBUG: Excluded subgroups:", paste(excluded_subgroups, collapse=", ")))
}}

# データを有効なサブグループのみにフィルタ
dat_sg_filtered <- dat[dat[['{subgroup_col_name}']] %in% valid_subgroups, ]
dat_sg_filtered <- dat_sg_filtered[order(dat_sg_filtered[['{subgroup_col_name}']]), ]

if (nrow(dat_sg_filtered) == 0) {{
    print("WARNING: No data remaining after subgroup filtering")
    next
}}

print(paste("DEBUG: Filtered data rows:", nrow(dat_sg_filtered), "from original:", nrow(dat)))

# res_for_plotをフィルタリング
tryCatch({{
    # Study列で照合を試みる
    if ("Study" %in% names({res_for_plot_model_name}$data) && "Study" %in% names(dat_sg_filtered)) {{
        filter_indices <- which({res_for_plot_model_name}$data$Study %in% dat_sg_filtered$Study)
    }} else {{
        # Study列がない場合は行名で照合
        original_rownames <- rownames(dat)
        filtered_rownames <- rownames(dat_sg_filtered)
        filter_indices <- which(original_rownames %in% filtered_rownames)
    }}
    
    # インデックスが空でないことを確認
    if (length(filter_indices) == 0) {{
        print("ERROR: No matching indices found for filtering")
        next
    }}
    
    print(paste("DEBUG: Filter indices found:", length(filter_indices)))
    
    # res_for_plotを安全にフィルタ
    res_plot_sg <- {res_for_plot_model_name}
    res_plot_sg$yi <- {res_for_plot_model_name}$yi[filter_indices]
    res_plot_sg$vi <- {res_for_plot_model_name}$vi[filter_indices]
    res_plot_sg$se <- {res_for_plot_model_name}$se[filter_indices]
    res_plot_sg$k <- length(filter_indices)
    res_plot_sg$data <- {res_for_plot_model_name}$data[filter_indices, ]
    
    # データサイズの整合性確認
    if (nrow(res_plot_sg$data) != nrow(dat_sg_filtered)) {{
        print(paste("WARNING: Size mismatch - res_plot_sg:", nrow(res_plot_sg$data), 
                   "dat_sg_filtered:", nrow(dat_sg_filtered)))
        # より安全なslabの取得
        if ("slab" %in% names(res_plot_sg$data)) {{
            plot_slab <- res_plot_sg$data$slab
        }} else if ("slab" %in% names(dat_sg_filtered)) {{
            plot_slab <- dat_sg_filtered$slab
        }} else {{
            plot_slab <- paste("Study", seq_len(nrow(res_plot_sg$data)))
        }}
    }} else {{
        plot_slab <- dat_sg_filtered$slab
    }}
    
    print(paste("DEBUG: Using slab length:", length(plot_slab)))
    
    # シンプルな行位置計算
    n_studies <- length(plot_slab)
    n_subgroups <- length(valid_subgroups)
    
    # 各サブグループの研究数
    sg_counts <- table(dat_sg_filtered[['{subgroup_col_name}']]) 
    
    # 行位置を上から下へ計算（より予測可能）
    current_row <- n_studies + (n_subgroups * 2) + 2
    all_rows <- c()
    subtotal_rows <- c()
    
    for (sg_name in valid_subgroups) {{
        sg_count <- sg_counts[sg_name]
        
        # この サブグループの研究行
        study_rows <- seq(current_row - sg_count + 1, current_row)
        all_rows <- c(all_rows, study_rows)
        
        # サブグループサマリー行
        subtotal_row <- current_row - sg_count - 1
        subtotal_rows <- c(subtotal_rows, subtotal_row)
        names(subtotal_rows)[length(subtotal_rows)] <- sg_name
        
        current_row <- current_row - sg_count - 2
    }}
    
    # プロット設定
    ylim_range <- c(min(subtotal_rows) - 2, max(all_rows) + 2)
    
    # PNG出力開始
    png('{subgroup_forest_plot_path}', width=10, height=8, units="in", res=300)
    
    # フォレストプロット描画
    forest(res_plot_sg,
           slab = plot_slab,
           rows = all_rows,
           ylim = ylim_range,
           atransf = if("{measure_for_plot}" %in% c("OR", "RR", "HR")) exp else I,
           main = "Subgroup Analysis by {subgroup_col_name}",
           xlab = if("{measure_for_plot}" %in% c("OR", "RR", "HR")) "{measure_for_plot} (log scale)" else "Effect Size",
           cex = 0.8)
    
    # サブグループサマリーを追加
    for (sg_name in valid_subgroups) {{
        if (!is.null(res_by_subgroup_{safe_var_name}[[sg_name]])) {{
            sg_result <- res_by_subgroup_{safe_var_name}[[sg_name]]
            n_studies_sg <- sg_counts[sg_name]
            
            addpoly(sg_result, 
                   row = subtotal_rows[sg_name],
                   mlab = paste(sg_name, " (k=", n_studies_sg, ")", sep=""),
                   cex = 0.8)
        }}
    }}
    
    print("DEBUG: Subgroup forest plot completed successfully")
    dev.off()
    
}}, error = function(e) {{
    print(paste("ERROR in subgroup forest plot:", e$message))
    # エラー時もPNGファイルを作成（空でも）
    png('{subgroup_forest_plot_path}', width=10, height=8, units="in", res=300)
    plot(1, type="n", main="Subgroup Forest Plot - Error", xlab="", ylab="")
    text(1, 1, paste("Error generating plot:", e$message), col="red", cex=0.8)
    dev.off()
}})

print("=== SUBGROUP FOREST PLOT END ===")
""",'''
    
    # ファイルを読み込む
    template_file = "/home/youkiti/meta-analysis-bot-release/templates/r_templates.py"
    
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 古いテンプレートの開始と終了を見つける
    start_marker = '"subgroup_forest_plot_template": """'
    end_marker = '""",\n            "funnel_plot"'
    
    start_pos = content.find(start_marker)
    end_pos = content.find(end_marker)
    
    if start_pos == -1 or end_pos == -1:
        print("❌ テンプレートマーカーが見つかりません")
        return False
    
    # 新しいコンテンツを作成
    new_content = (
        content[:start_pos] + 
        new_template + 
        content[end_pos:]
    )
    
    # バックアップを作成
    backup_file = template_file + ".backup"
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ バックアップ作成: {backup_file}")
    
    # 新しいコンテンツを書き込み
    with open(template_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ サブグループフォレストプロットテンプレートを修正版に置き換えました")
    print("🔧 主な改善点:")
    print("  - 前提条件チェックの簡素化")
    print("  - より安全なデータフィルタリング")
    print("  - シンプルな行位置計算")
    print("  - エラーハンドリングの改善")
    print("  - デバッグ出力の最適化")
    
    return True

if __name__ == "__main__":
    success = apply_subgroup_fix()
    if success:
        print("\n🚀 修正完了！次のステップ:")
        print("1. git add templates/r_templates.py")
        print("2. git commit -m 'fix: simplify subgroup forest plot template'")
        print("3. git push heroku main")
        print("4. テストを実行して動作確認")
    else:
        print("\n❌ 修正に失敗しました")