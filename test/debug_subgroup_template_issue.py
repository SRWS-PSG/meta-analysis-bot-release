#!/usr/bin/env python3
"""
サブグループテンプレートの前提条件チェック問題を調査
"""

# サブグループフォレストプロットの前提条件チェックが複雑すぎる問題
# 簡略化したバージョンを提案

simplified_template = """
# サブグループ '{subgroup_col_name}' のフォレストプロット（簡略化版）

print("=== SUBGROUP FOREST PLOT START ===")
print("DEBUG: Starting subgroup forest plot for {subgroup_col_name}")

# より単純な前提条件チェック
if (exists("res_by_subgroup_{safe_var_name}") && length(res_by_subgroup_{safe_var_name}) > 0) {{
    
    print("DEBUG: Valid subgroup results found, proceeding with plot")
    
    # データの準備（より直接的なアプローチ）
    sg_names <- names(res_by_subgroup_{safe_var_name})
    print(paste("DEBUG: Subgroup names:", paste(sg_names, collapse=", ")))
    
    # 有効なサブグループのみでデータをフィルタ
    dat_for_plot <- dat[dat[['{subgroup_col_name}']] %in% sg_names, ]
    dat_for_plot <- dat_for_plot[order(dat_for_plot[['{subgroup_col_name}']]), ]
    
    print(paste("DEBUG: Original data rows:", nrow(dat)))
    print(paste("DEBUG: Filtered data rows:", nrow(dat_for_plot)))
    
    # res_for_plotを同様にフィルタ
    if (exists("res_for_plot") && !is.null(res_for_plot)) {{
        
        # フィルタ済みデータのインデックスを取得
        if ("Study" %in% names(res_for_plot$data) && "Study" %in% names(dat_for_plot)) {{
            filtered_indices <- which(res_for_plot$data$Study %in% dat_for_plot$Study)
        }} else {{
            # Study列がない場合は行番号で照合
            original_row_names <- rownames(dat)
            filtered_row_names <- rownames(dat_for_plot)
            filtered_indices <- which(original_row_names %in% filtered_row_names)
        }}
        
        print(paste("DEBUG: Filtered indices count:", length(filtered_indices)))
        
        if (length(filtered_indices) > 0) {{
            
            # res_for_plotをフィルタリング
            res_for_plot_sg <- res_for_plot
            res_for_plot_sg$yi <- res_for_plot$yi[filtered_indices]
            res_for_plot_sg$vi <- res_for_plot$vi[filtered_indices]
            res_for_plot_sg$se <- res_for_plot$se[filtered_indices]
            res_for_plot_sg$k <- length(filtered_indices)
            res_for_plot_sg$data <- res_for_plot$data[filtered_indices, ]
            
            # プロット実行
            png('{subgroup_forest_plot_path}', width=10, height=8, units="in", res=300)
            
            tryCatch({{
                # 各サブグループの行位置を計算
                sg_table <- table(dat_for_plot[['{subgroup_col_name}']])
                n_sg <- length(sg_table)
                total_studies <- nrow(dat_for_plot)
                
                # 簡単な行位置計算
                current_row <- total_studies + (n_sg * 2) + 2
                all_rows <- c()
                subtotal_rows <- c()
                
                for (i in 1:n_sg) {{
                    sg_name <- names(sg_table)[i]
                    n_studies <- sg_table[sg_name]
                    
                    rows <- seq(current_row - n_studies + 1, current_row)
                    all_rows <- c(all_rows, rows)
                    
                    subtotal_row <- current_row - n_studies - 1
                    subtotal_rows <- c(subtotal_rows, subtotal_row)
                    names(subtotal_rows)[length(subtotal_rows)] <- sg_name
                    
                    current_row <- current_row - n_studies - 2
                }}
                
                # フォレストプロット
                ylim_range <- c(min(subtotal_rows) - 2, max(all_rows) + 2)
                
                forest(res_for_plot_sg,
                       slab = dat_for_plot$slab,
                       rows = all_rows,
                       ylim = ylim_range,
                       atransf = if("{measure_for_plot}" %in% c("OR", "RR", "HR")) exp else I,
                       main = "Subgroup Analysis by {subgroup_col_name}")
                
                # サブグループサマリーを追加
                for (sg_name in names(sg_table)) {{
                    if (!is.null(res_by_subgroup_{safe_var_name}[[sg_name]])) {{
                        addpoly(res_by_subgroup_{safe_var_name}[[sg_name]], 
                                row = subtotal_rows[sg_name],
                                mlab = paste(sg_name, " (k=", sg_table[sg_name], ")", sep=""))
                    }}
                }}
                
                print("DEBUG: Subgroup forest plot completed successfully")
                
            }}, error = function(e) {{
                print(paste("ERROR in subgroup forest plot:", e$message))
                plot(1, type="n", main="Error in Subgroup Forest Plot")
                text(1, 1, paste("Error:", e$message), col="red")
            }})
            
            dev.off()
            
        }} else {{
            print("WARNING: No valid indices for filtering")
        }}
        
    }} else {{
        print("WARNING: res_for_plot not available")
    }}
    
}} else {{
    print("WARNING: No valid subgroup results found")
}}

print("=== SUBGROUP FOREST PLOT END ===")
"""

print("📝 簡略化されたサブグループフォレストプロットテンプレート:")
print(simplified_template)

print("\n🔧 主な変更点:")
print("1. 複雑な前提条件チェックを簡略化")
print("2. データフィルタリングロジックを明確化") 
print("3. エラーハンドリングを強化")
print("4. デバッグ出力を追加")
print("5. フォールバック処理を追加")