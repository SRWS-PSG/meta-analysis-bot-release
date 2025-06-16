#!/usr/bin/env python3
"""
修正版：サブグループforest plotテンプレート

問題の根本解決:
1. slabベクトルの手動操作を廃止
2. 列名参照による自動処理に統一
3. フィルタリング処理の簡素化
"""

def generate_fixed_subgroup_template():
    """
    修正されたサブグループforest plotテンプレート
    
    主な変更点:
    - slabベクトルの手動操作を削除
    - 列名参照 (slab={slab_column}) に統一
    - データフィルタリングの簡素化
    - metafor関数の内部データ処理に依存
    """
    
    return '''
# === 修正版: サブグループforest plotテンプレート ===

print("=== SUBGROUP FOREST PLOT START: {subgroup_col_name} ===")
print(paste("DEBUG: Starting subgroup forest plot for {subgroup_col_name}"))

# 前提条件チェック
if (exists("res_by_subgroup_{safe_var_name}") && length(res_by_subgroup_{safe_var_name}) > 0) {{
    
    print("DEBUG: All prerequisites met, starting subgroup forest plot generation")
    
    # --- プロットサイズパラメータ ---
    row_h_in_sg_val <- {row_h_in_placeholder}
    base_h_in_sg_val <- {base_h_in_placeholder}
    plot_width_in_sg_val <- {plot_width_in_placeholder}
    plot_dpi_sg_val <- {plot_dpi_placeholder}
    extra_rows_sg_val <- {extra_rows_subgroup_placeholder}

    # --- サブグループ情報の取得 ---
    sg_level_names <- names(res_by_subgroup_{safe_var_name})
    n_sg_levels <- length(sg_level_names)
    
    print(paste("DEBUG: sg_level_names in res_by_subgroup:", paste(sg_level_names, collapse=", ")))
    
    # データをサブグループでソート（元データを保持）
    dat_ordered <- dat[order(dat[['{subgroup_col_name}']]), ]
    
    # --- 修正: 有効なサブグループのみをフィルタ ---
    # res_by_subgroupに存在するサブグループのデータのみを使用
    valid_subgroups <- names(res_by_subgroup_{safe_var_name})
    dat_filtered <- dat_ordered[dat_ordered[['{subgroup_col_name}']] %in% valid_subgroups & 
                                !is.na(dat_ordered[['{subgroup_col_name}']]), ]
    
    print(paste("DEBUG: Original data rows:", nrow(dat)))
    print(paste("DEBUG: Ordered data rows:", nrow(dat_ordered)))
    print(paste("DEBUG: Filtered data rows:", nrow(dat_filtered)))
    print(paste("DEBUG: Valid subgroups:", paste(valid_subgroups, collapse=", ")))
    
    # --- 修正: プロット用解析を新規実行（フィルタ済みデータで） ---
    # 手動フィルタリングではなく、metaforに処理を委ねる
    print("DEBUG: Creating plot-specific analysis with filtered data")
    
    if ("{analysis_type}" == "binary") {{
        # 二値アウトカム：rma.mh()を使用、slabは列名参照
        res_for_plot_sg <- rma.mh(
            ai = {ai}, bi = {bi}, ci = {ci}, di = {di}, 
            data = dat_filtered,
            measure = "{measure}",
            add = 0, to = "none", drop00 = TRUE, correct = TRUE,
            slab = {slab_column}  # 列名参照で自動処理
        )
    }} else {{
        # その他：逆分散法を使用
        res_for_plot_sg <- rma(
            yi = yi, vi = vi, 
            data = dat_filtered,
            method = "{method}",
            slab = {slab_column}  # 列名参照で自動処理
        )
    }}
    
    print(paste("DEBUG: Plot analysis completed - studies:", res_for_plot_sg$k))
    
    # --- 行位置の計算（簡素化） ---
    total_studies <- res_for_plot_sg$k
    study_rows <- seq(1, total_studies)
    
    # サブグループごとの研究数
    sg_counts <- table(dat_filtered[['{subgroup_col_name}']])
    print(paste("DEBUG: Subgroup study counts:", paste(names(sg_counts), sg_counts, sep="=", collapse=", ")))
    
    # サブトータル行の位置計算
    subtotal_positions <- cumsum(sg_counts)
    subtotal_rows <- subtotal_positions + seq_along(subtotal_positions) * 0.5
    
    # プロット範囲の計算
    ylim_bottom <- min(subtotal_rows) - 3
    ylim_top <- max(study_rows) + 3
    
    print(paste("DEBUG: Plot range - bottom:", ylim_bottom, "top:", ylim_top))
    
    # --- PNG出力設定 ---
    plot_height_sg <- base_h_in_sg_val + total_studies * row_h_in_sg_val + extra_rows_sg_val
    png("subgroup_forest_plot_{safe_filename}.png", 
        width = plot_width_in_sg_val, height = plot_height_sg, res = plot_dpi_sg_val)
    
    # --- メインforest plot（修正版） ---
    print("DEBUG: Generating main forest plot")
    
    # forest()呼び出し（slabは自動処理される）
    forest(
        res_for_plot_sg,  # フィルタ済みデータで作成した解析結果
        rows = study_rows,
        ylim = c(ylim_bottom, ylim_top),
        atransf = if("{measure}" %in% c("OR", "RR", "HR")) exp else I,
        at = if("{measure}" %in% c("OR", "RR", "HR")) log(c(0.25, 1, 4)) else NULL,
        xlim = c(-16, 6),
        digits = 2,
        header = "Author(s) and Year",
        refline = if("{measure}" %in% c("OR", "RR", "HR")) 0 else 0,
        cex = 0.75,
        mlab = ""
    )
    
    # --- サブグループサマリーの追加 ---
    print("DEBUG: Adding subgroup summaries")
    
    current_row <- 1
    for (sg_level in valid_subgroups) {{
        sg_res <- res_by_subgroup_{safe_var_name}[[sg_level]]
        sg_count <- sg_counts[[sg_level]]
        
        # サブグループサマリー行の位置
        subtotal_row <- current_row + sg_count
        
        # サブグループタイトル
        text(x = -16, y = subtotal_row + 1, labels = paste("Subgroup:", sg_level), 
             font = 2, cex = 0.8, pos = 4)
        
        # サブグループサマリー統計
        if (!is.null(sg_res$b) && !is.na(sg_res$b)) {{
            effect_text <- if("{measure}" %in% c("OR", "RR", "HR")) {{
                sprintf("%.2f [%.2f, %.2f]", exp(sg_res$b), exp(sg_res$ci.lb), exp(sg_res$ci.ub))
            }} else {{
                sprintf("%.2f [%.2f, %.2f]", sg_res$b, sg_res$ci.lb, sg_res$ci.ub)
            }}
            
            text(x = 0, y = subtotal_row, labels = effect_text, cex = 0.8, font = 2)
        }}
        
        current_row <- current_row + sg_count + 2  # 次のサブグループまでの間隔
    }}
    
    # --- 統計的検定結果の追加 ---
    if (exists("subgroup_test_p_{safe_var_name}")) {{
        test_text <- paste("Test for subgroup differences: p =", 
                          round(subgroup_test_p_{safe_var_name}, 4))
        text(x = -16, y = ylim_bottom + 1, labels = test_text, cex = 0.8, pos = 4)
    }}
    
    dev.off()
    print("DEBUG: Subgroup forest plot saved")
    
}} else {{
    print("ERROR: Prerequisites not met for subgroup forest plot")
    if (!exists("res_by_subgroup_{safe_var_name}")) {{
        print("ERROR: res_by_subgroup_{safe_var_name} does not exist")
    }}
    if (exists("res_by_subgroup_{safe_var_name}") && length(res_by_subgroup_{safe_var_name}) == 0) {{
        print("ERROR: res_by_subgroup_{safe_var_name} is empty")
    }}
}}

print("=== SUBGROUP FOREST PLOT END ===")
'''

if __name__ == "__main__":
    print("=== 修正版サブグループforest plotテンプレート ===")
    print()
    print("主な修正点:")
    print("1. slabベクトルの手動操作を廃止")
    print("2. 列名参照 (slab={slab_column}) に統一") 
    print("3. フィルタリング処理の簡素化")
    print("4. metafor関数の内部データ処理に依存")
    print()
    print("修正されたテンプレート:")
    print(generate_fixed_subgroup_template())