
library(metafor)
library(jsonlite)


dat <- read.csv('/tmp/tmpvq7g77qk.csv', na.strings = c('NA', 'na', 'N/A', 'n/a', ''))


# データ品質チェック
cat("データ読み込み完了\n")
cat("総行数:", nrow(dat), "\n")
if (any(is.na(dat))) {
    na_summary <- sapply(dat, function(x) sum(is.na(x)))
    na_cols <- na_summary[na_summary > 0]
    if (length(na_cols) > 0) {
        cat("欠損値を含む列:\n")
        for (col_name in names(na_cols)) {
            cat("  ", col_name, ":", na_cols[col_name], "個\n")
        }
    }
} else {
    cat("欠損値なし\n")
}

# 解析に必要な数値列の数値変換とNA値処理
numeric_cols_to_check <- c()



if ("events_treatment" %in% names(dat)) {
    cat("数値変換: events_treatment\n")
    original_values <- dat$events_treatment
    dat$events_treatment <- as.numeric(as.character(dat$events_treatment))
    invalid_rows <- which(is.na(dat$events_treatment))
    if (length(invalid_rows) > 0) {
        cat("⚠️ データ品質警告: events_treatment列でNA値または非数値データが検出されました\n")
        cat("   対象行: ", paste(invalid_rows, collapse=", "), "\n")
        if ("Study" %in% names(dat)) {
            invalid_studies <- dat[invalid_rows, "Study"]
            cat("   該当研究: ", paste(invalid_studies, collapse=", "), "\n")
        }
        cat("   元の値: ", paste(original_values[invalid_rows], collapse=", "), "\n")
        cat("   これらの研究は解析から除外されます\n")
    }
}

if ("events_control" %in% names(dat)) {
    cat("数値変換: events_control\n")
    original_values <- dat$events_control
    dat$events_control <- as.numeric(as.character(dat$events_control))
    invalid_rows <- which(is.na(dat$events_control))
    if (length(invalid_rows) > 0) {
        cat("⚠️ データ品質警告: events_control列でNA値または非数値データが検出されました\n")
        cat("   対象行: ", paste(invalid_rows, collapse=", "), "\n")
        if ("Study" %in% names(dat)) {
            invalid_studies <- dat[invalid_rows, "Study"]
            cat("   該当研究: ", paste(invalid_studies, collapse=", "), "\n")
        }
        cat("   元の値: ", paste(original_values[invalid_rows], collapse=", "), "\n")
        cat("   これらの研究は解析から除外されます\n")
    }
}

dat$slab <- dat$Study


# ゼロセル分析（NA値を適切に処理）
zero_cells_summary <- list()
zero_cells_summary$total_studies <- nrow(dat)

# NA値を除いてゼロセルを計算
valid_rows <- !is.na(dat$events_treatment) & !is.na(dat$total_treatment) & !is.na(dat$events_control) & !is.na(dat$total_control)
zero_cells_summary$valid_studies <- sum(valid_rows, na.rm=TRUE)

if (zero_cells_summary$valid_studies > 0) {{
    valid_dat <- dat[valid_rows, ]
    zero_cells_summary$studies_with_zero_cells <- sum((valid_dat$events_treatment == 0) | (valid_dat$total_treatment == 0) | (valid_dat$events_control == 0) | (valid_dat$total_control == 0), na.rm=TRUE)
    zero_cells_summary$double_zero_studies <- sum((valid_dat$events_treatment == 0 & valid_dat$events_control == 0), na.rm=TRUE)
    zero_cells_summary$zero_in_treatment <- sum(valid_dat$events_treatment == 0, na.rm=TRUE)
    zero_cells_summary$zero_in_control <- sum(valid_dat$events_control == 0, na.rm=TRUE)
}} else {{
    zero_cells_summary$studies_with_zero_cells <- 0
    zero_cells_summary$double_zero_studies <- 0
    zero_cells_summary$zero_in_treatment <- 0
    zero_cells_summary$zero_in_control <- 0
}}

print("📊 ゼロセル分析:")
if (exists("zero_cells_summary")) {{
  print(paste("総研究数:", zero_cells_summary$total_studies))
  print(paste("有効研究数（NA値除外後）:", zero_cells_summary$valid_studies))
  
  # NA値により除外された研究があれば警告
  excluded_count <- zero_cells_summary$total_studies - zero_cells_summary$valid_studies
  if (excluded_count > 0) {{
    print(paste("⚠️ ", excluded_count, "件の研究がNA値のため解析から除外されました"))
  }}
  
  print(paste("ゼロセルを含む研究数:", zero_cells_summary$studies_with_zero_cells))
  print(paste("両群ゼロ研究数:", zero_cells_summary$double_zero_studies))
  print(paste("介入群ゼロ研究数:", zero_cells_summary$zero_in_treatment))
  print(paste("対照群ゼロ研究数:", zero_cells_summary$zero_in_control))
}}

# ゼロセルがある場合の推奨手法の判定
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    print("ゼロセルが検出されました。Mantel-Haenszel法を推奨します。")
    recommended_method <- "MH"
}} else {{
    print("ゼロセルは検出されませんでした。逆分散法で問題ありません。")
    recommended_method <- "IV"
}}



# 二値アウトカムの効果量計算 (例: オッズ比)
# 修正: slabを列名参照に変更してベクトル長さ不整合を回避
dat <- escalc(measure="OR", ai=events_treatment, bi=total_treatment, ci=events_control, di=total_control, data=dat, slab=slab)



# 主解析手法の選択（ゼロセルがある場合はMH法、ない場合は逆分散法）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    print("ゼロセルが検出されました。主解析にMantel-Haenszel法を使用します。")
    main_analysis_method <- "MH"
    
    # 主解析：Mantel-Haenszel法（補正なし）
    # 修正: slabを列名参照に変更してベクトル長さ不整合を回避
    res <- rma.mh(ai=events_treatment, bi=total_treatment, ci=events_control, di=total_control, data=dat, measure="OR",
                  add=0, to="none", drop00=TRUE, correct=TRUE, slab=slab)
    res_for_plot <- res  # プロット用にも同じ結果を使用
    
    print("主解析完了: Mantel-Haenszel法（補正なし）")
}} else {{
    print("ゼロセルは検出されませんでした。主解析に逆分散法を使用します。")
    main_analysis_method <- "IV"
    
    # 主解析：逆分散法（従来通り）
    res <- rma(dat$yi, dat$vi, data=dat, method="REML")
    res_for_plot <- res  # プロット用にも同じ結果を使用
    
    print("主解析完了: 逆分散法")
}}



# ゼロセル対応の感度解析（主解析以外の手法で比較）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    sensitivity_results <- list()
    
    # 主解析の結果を記録
    sensitivity_results$main_analysis <- list(
        method = paste0("Mantel-Haenszel (no correction) - MAIN ANALYSIS"),
        estimate = as.numeric(res$b)[1],
        ci_lb = as.numeric(res$ci.lb)[1],
        ci_ub = as.numeric(res$ci.ub)[1],
        pval = as.numeric(res$pval)[1],
        I2 = res$I2,
        note = "Primary analysis method for sparse data"
    )
    
    # 感度解析1: 逆分散法（デフォルト0.5補正）
    tryCatch({{
        res_iv_corrected <- rma(`yi`, `vi`, data=dat, method="REML")
        sensitivity_results$sensitivity_iv_corrected <- list(
            method = "Inverse Variance (0.5 correction) - SENSITIVITY",
            estimate = as.numeric(res_iv_corrected$b)[1],
            ci_lb = as.numeric(res_iv_corrected$ci.lb)[1],
            ci_ub = as.numeric(res_iv_corrected$ci.ub)[1],
            pval = as.numeric(res_iv_corrected$pval)[1],
            I2 = res_iv_corrected$I2,
            note = "Traditional method with continuity correction"
        )
    }}, error = function(e) {{
        sensitivity_results$sensitivity_iv_corrected <<- list(
            method = "Inverse Variance (0.5 correction) - SENSITIVITY",
            error = e$message
        )
    }})
    
    # 感度解析2: Mantel-Haenszel法（個別効果量のみ補正）
    tryCatch({{
        res_mh_corr <- rma.mh(ai=`events_treatment`, bi=`total_treatment`, ci=`events_control`, di=`total_control`, data=dat, 
                             measure="OR", add=c(0.5, 0), to=c("only0", "none"), drop00=TRUE)
        sensitivity_results$sensitivity_mh_with_correction <- list(
            method = "Mantel-Haenszel (forest plot correction) - SENSITIVITY",
            estimate = as.numeric(res_mh_corr$b)[1],
            ci_lb = as.numeric(res_mh_corr$ci.lb)[1],
            ci_ub = as.numeric(res_mh_corr$ci.ub)[1],
            pval = as.numeric(res_mh_corr$pval)[1],
            I2 = res_mh_corr$I2,
            note = "MH method with correction for visualization only"
        )
    }}, error = function(e) {{
        sensitivity_results$sensitivity_mh_with_correction <<- list(
            method = "Mantel-Haenszel (forest plot correction) - SENSITIVITY", 
            error = e$message
        )
    }})
    
    # 結果の比較表示
    print("\n=== 主解析とゼロセル対応感度解析の結果 ===")
    print("主解析: Mantel-Haenszel法（補正なし）- Cochrane推奨手法")
    print("感度解析: 他の補正手法との比較")
    print("-------------------------------------------------------")
    
    for (method_name in names(sensitivity_results)) {{
        result <- sensitivity_results[[method_name]]
        if ("error" %in% names(result)) {{
            print(paste(result$method, ": エラー -", result$error))
        }} else {{
            analysis_type <- if(grepl("MAIN", result$method)) "【主解析】" else "【感度解析】"
            print(sprintf("%s %s: %s = %.3f [%.3f, %.3f], p = %.3f, I² = %.1f%%",
                         analysis_type, result$method, "OR", 
                         if("OR" %in% c("OR", "RR")) exp(result$estimate) else result$estimate,
                         if("OR" %in% c("OR", "RR")) exp(result$ci_lb) else result$ci_lb,
                         if("OR" %in% c("OR", "RR")) exp(result$ci_ub) else result$ci_ub,
                         result$pval, result$I2))
            if (!is.null(result$note)) {{
                print(paste("   └", result$note))
            }}
        }}
    }}
    
    # JSONに保存
    if (exists("summary_list")) {{
        summary_list$zero_cell_sensitivity <- sensitivity_results
        summary_list$zero_cell_analysis <- zero_cells_summary
        summary_list$main_analysis_method <- "Mantel-Haenszel (no correction)"
    }}
}} else {{
    print("ゼロセルが検出されなかったため、ゼロセル対応感度解析をスキップします。")
    if (exists("summary_list")) {{
        summary_list$zero_cell_sensitivity_skipped <- "No zero cells detected"
        summary_list$main_analysis_method <- "Inverse Variance (standard)"
    }}
}}



# --- Subgroup analysis for 'Region' ---

# Subgroup moderation test for 'Region'
valid_data_for_subgroup_test <- dat[is.finite(dat$yi) & is.finite(dat$vi) & dat$vi > 0, ]

if (nrow(valid_data_for_subgroup_test) >= 2 && "Region" %in% names(valid_data_for_subgroup_test)) {
    tryCatch({
        res_subgroup_test_Region <- rma(yi, vi, mods = ~ factor(Region), data=valid_data_for_subgroup_test, method="REML")
        print("Subgroup test for 'Region' completed")
    }, error = function(e) {
        print(sprintf("Subgroup test for 'Region' failed: %s", e$message))
        res_subgroup_test_Region <- NULL
    })
} else {
    print("Subgroup test for 'Region': 有効データが不足またはカラムが存在しません")
    res_subgroup_test_Region <- NULL
}

# Subgroup analysis for 'Region' by levels
if ("Region" %in% names(dat)) {
    dat_split_Region <- split(dat, dat[['Region']])
    res_by_subgroup_Region <- lapply(names(dat_split_Region), function(level_name) {
        current_data_sg <- dat_split_Region[[level_name]]
        if (nrow(current_data_sg) > 0) {
            # 無限大値をチェックして除外
            valid_sg_data <- current_data_sg[is.finite(current_data_sg$yi) & is.finite(current_data_sg$vi) & current_data_sg$vi > 0, ]
            
            if (nrow(valid_sg_data) >= 2) {
                tryCatch({
                    rma_result_sg <- rma(yi, vi, data=valid_sg_data, method="REML")
                    # 結果にレベル名を追加して返す (後でアクセスしやすくするため)
                    rma_result_sg$subgroup_level <- level_name 
                    return(rma_result_sg)
                }, error = function(e) {
                    print(sprintf("RMA failed for subgroup 'Region' level '%s': %s", level_name, e$message))
                    return(NULL) # エラー時はNULLを返す
                })
            } else {
                print(sprintf("Subgroup 'Region' level '%s': 有効データが不足 (n=%d)", level_name, nrow(valid_sg_data)))
                return(NULL) # 有効データが不足の場合はNULL
            }
        } else {
            return(NULL) # データがない場合はNULL
        }
    })
    # NULL要素をリストから除去
    res_by_subgroup_Region <- res_by_subgroup_Region[!sapply(res_by_subgroup_Region, is.null)]
    # リストの要素に名前を付ける (サブグループのレベル名)
    if (length(res_by_subgroup_Region) > 0) {
        names(res_by_subgroup_Region) <- sapply(res_by_subgroup_Region, function(x) x$subgroup_level)
    }
} else {
    res_subgroup_test_Region <- NULL
    res_by_subgroup_Region <- NULL
    print("Subgroup column 'Region' not found in data for subgroup analysis.")
}


# === Subgroup Exclusion Detection (Early) ===
# Initialize exclusion tracking in summary_list
if (!exists('summary_list')) { summary_list <- list() }
if (is.null(summary_list$subgroup_exclusions)) { summary_list$subgroup_exclusions <- list() }


# Detect exclusions for subgroup 'Region'
if (exists("res_by_subgroup_Region") && !is.null(res_by_subgroup_Region)) {
    # Get all subgroups in original data
    all_subgroups_in_data <- unique(dat[['Region']])
    
    # Get subgroups that have valid analysis results 
    subgroups_in_res <- names(res_by_subgroup_Region)
    
    # Find excluded subgroups using setdiff
    excluded_subgroups <- setdiff(all_subgroups_in_data, subgroups_in_res)
    
    print(paste("DEBUG: Early exclusion detection for Region"))
    print(paste("DEBUG: All subgroups in data:", paste(all_subgroups_in_data, collapse=", ")))
    print(paste("DEBUG: Valid subgroups in results:", paste(subgroups_in_res, collapse=", ")))
    print(paste("DEBUG: Excluded subgroups:", paste(excluded_subgroups, collapse=", ")))
    
    # Save exclusion information if any subgroups were excluded
    if (length(excluded_subgroups) > 0) {
        excluded_info <- list(
            excluded_subgroups = excluded_subgroups,
            reason = "insufficient_data_n_le_1",
            included_subgroups = subgroups_in_res
        )
        
        # Save to summary_list (this runs before forest plots, so no scoping issues)
        summary_list$subgroup_exclusions[['Region']] <- excluded_info
        
        print(paste("DEBUG: Saved exclusion info for Region to summary_list"))
        print(paste("DEBUG: Excluded subgroups saved:", paste(excluded_subgroups, collapse=", ")))
    } else {
        print(paste("DEBUG: No exclusions detected for Region"))
    }
}

egger_test_res <- tryCatch(regtest(res_for_plot), error = function(e) { print(sprintf("Egger's test failed: %s", e$message)); return(NULL) })


# フォレストプロット作成
# メインのフォレストプロット

# --- プロットサイズパラメータ ---
row_h_in_val <- 0.3        # 1行あたりの高さ (インチ)
base_h_in_val <- 6       # ベースの高さ (インチ)
plot_width_in_val <- 10 # プロットの幅 (インチ)
plot_dpi_val <- 300         # 解像度 (dpi)
extra_rows_val <- 5 # 追加行数

# --- 高さ計算 ---
# res_for_plot がこの時点で存在することを前提とする
k_study_main <- ifelse(exists("res_for_plot") && !is.null(res_for_plot$k), res_for_plot$k, nrow(dat))
k_header_main <- 0 # メインプロットではサブグループヘッダーは基本なし
plot_height_in_main <- max(base_h_in_val, (k_study_main + k_header_main + extra_rows_val) * row_h_in_val)

png('comprehensive_test_forest_plot.png', width=plot_width_in_val, height=plot_height_in_main, units="in", res=plot_dpi_val, pointsize=9)
tryCatch({{
    # 効果量の種類に応じて atransf と at を調整
    current_measure <- "OR"
    apply_exp_transform <- current_measure %in% c("OR", "RR", "HR", "IRR", "PLO", "IR")

    if (apply_exp_transform) {{
        forest_at <- log(c(0.05, 0.25, 1, 4))
        forest_refline <- 0 # logスケールでの参照線
    }} else {{
        forest_at <- NULL
        forest_refline <- 0
    }}

    # 二値アウトカムの場合の追加情報列の準備
    ilab_data <- NULL
    ilab_xpos <- NULL
    ilab_lab <- NULL
    
    if (current_measure %in% c("OR", "RR", "RD", "PETO")) {{
        ai_col <- "events_treatment"
        bi_col <- "total_treatment" 
        ci_col <- "events_control"
        di_col <- "total_control"
        n1i_col <- ""
        n2i_col <- ""
        
        # 二値アウトカムでEvents/Total形式で表示
        if (ai_col != "" && ci_col != "" && n1i_col != "" && n2i_col != "" &&
            all(c(ai_col, ci_col, n1i_col, n2i_col) %in% names(dat))) {{
            # Events/Total 形式で表示
            treatment_display <- paste(dat[[ai_col]], "/", dat[[n1i_col]], sep="")
            control_display <- paste(dat[[ci_col]], "/", dat[[n2i_col]], sep="")
            ilab_data <- cbind(treatment_display, control_display)
            ilab_xpos <- c(-8.5, -5.5)
            ilab_lab <- c("Events/Total", "Events/Total")
        }} else if (ai_col != "" && ci_col != "" && all(c(ai_col, ci_col) %in% names(dat))) {{
            # フォールバック: イベント数のみ
            ilab_data <- cbind(dat[[ai_col]], dat[[ci_col]])
            ilab_xpos <- c(-8.5, -5.5)
            ilab_lab <- c("Events", "Events")
        }}
    }} else if (current_measure %in% c("SMD", "MD", "ROM")) {{
        # 連続アウトカムの場合: n1i, n2i を表示
        n1i_col <- ""
        n2i_col <- ""
        
        if (n1i_col != "" && n2i_col != "" && all(c(n1i_col, n2i_col) %in% names(dat))) {{
            ilab_data <- cbind(dat[[n1i_col]], dat[[n2i_col]])
            ilab_xpos <- c(-8.5, -5.5)
            ilab_lab <- c("N", "N")
        }}
    }}

    # フォレストプロット描画 (res_for_plot を使用)
    # 修正: slabはres_for_plotに既に含まれているため明示的指定不要
    forest_args <- list(
        x = res_for_plot,
        atransf = if(apply_exp_transform) exp else I, 
        at = forest_at,
        xlim = c(-16, 6),
        digits = 2, 
        mlab = "",
        header = "Author(s) and Year",
        refline = forest_refline,
        shade = TRUE,
        cex = 0.75
    )
    
    # ilab_data が NULL でない場合のみ、ilab関連の引数を追加
    if (!is.null(ilab_data)) {
        forest_args$ilab <- ilab_data
        forest_args$ilab.xpos <- ilab_xpos
        forest_args$ilab.lab <- ilab_lab
    }
    
    # 引数リストを使って forest 関数を呼び出し
    do.call(forest, forest_args)

    if (!is.null(ilab_data) && length(ilab_xpos) == 2) { 
        text(c(-8.5, -5.5), res_for_plot$k+2.8, c("Treatment", "Control"), cex=0.75, font=2)
    }
    
    # 合計行を追加（二値アウトカムの場合のみ）
    if (current_measure %in% c("OR", "RR", "RD", "PETO") && !is.null(ilab_data)) {{
        ai_col <- "events_treatment"
        ci_col <- "events_control"
        n1i_col <- ""
        n2i_col <- ""
        
        # 全体合計の計算と表示
        if (ai_col != "" && ci_col != "" && n1i_col != "" && n2i_col != "" &&
            all(c(ai_col, ci_col, n1i_col, n2i_col) %in% names(dat))) {{
            
            total_ai <- sum(dat[[ai_col]], na.rm = TRUE)
            total_n1i <- sum(dat[[n1i_col]], na.rm = TRUE)
            total_ci <- sum(dat[[ci_col]], na.rm = TRUE)
            total_n2i <- sum(dat[[n2i_col]], na.rm = TRUE)
            
            # 合計行の位置（最下部）
            total_row_y <- 0.3
            
            # 合計行のラベルと数値を表示
            text(-16, total_row_y, "Total", font = 2, pos = 4, cex = 0.75)
            text(c(-8.5, -5.5), total_row_y, 
                 c(paste(total_ai, "/", total_n1i, sep=""),
                   paste(total_ci, "/", total_n2i, sep="")),
                 font = 2, cex = 0.75)
        }}
    }}
    
    text(-16, -1, pos=4, cex=0.75, bquote(paste(
        "RE Model (Q = ", .(formatC(res_for_plot$QE, digits=2, format="f")),
        ", df = ", .(res_for_plot$k - res_for_plot$p), ", ",
        "p = ", .(formatC(res_for_plot$QEp, digits=4, format="f")), "; ",
        I^2, " = ", .(formatC(res_for_plot$I2, digits=1, format="f")), "%, ",
        tau^2, " = ", .(formatC(res_for_plot$tau2, digits=2, format="f")), ")"
    )))
    
}}, error = function(e) {{
    plot(1, type="n", main="Forest Plot Error", xlab="", ylab="")
    text(1, 1, paste("Error generating forest plot:
", e$message), col="red")
    print(sprintf("Forest plot generation failed: %s", e$message))
}})
dev.off()



# サブグループ 'Region' のフォレストプロット（簡略化版）

print("=== SUBGROUP FOREST PLOT START: Region ===")
print(paste("DEBUG: Starting subgroup forest plot for Region"))

# より単純な前提条件チェック
if (exists("res_by_subgroup_Region") && length(res_by_subgroup_Region) > 0) {{
    
    print("DEBUG: All prerequisites met, starting subgroup forest plot generation")
    
    # --- プロットサイズパラメータ ---
    row_h_in_sg_val <- 0.3
    base_h_in_sg_val <- 6
    plot_width_in_sg_val <- 10
    plot_dpi_sg_val <- 300
    extra_rows_sg_val <- 7

    # --- サブグループごとの行位置計算 ---
    sg_level_names <- names(res_by_subgroup_Region)
    n_sg_levels <- length(sg_level_names)
    
    print(paste("DEBUG: sg_level_names in res_by_subgroup:", paste(sg_level_names, collapse=", ")))
    
    # データをサブグループでソート
    dat_ordered <- dat[order(dat[['Region']]), ]
    
    # 全データのサブグループ別研究数
    all_studies_per_sg <- table(dat[['Region']])
    print(paste("DEBUG: All subgroups in data:", paste(names(all_studies_per_sg), collapse=", ")))
    print(paste("DEBUG: Studies per subgroup:", paste(all_studies_per_sg, collapse=", ")))
    
    # res_by_subgroupに含まれるサブグループの研究数のみ取得
    studies_per_sg <- all_studies_per_sg[sg_level_names]
    
    # 元データのすべてのサブグループと res_by_subgroup に含まれるサブグループを比較
    # res_by_subgroup に含まれていないサブグループが除外されたサブグループ
    all_subgroups_in_data <- unique(dat[['Region']])
    subgroups_in_res <- sg_level_names
    
    excluded_subgroups <- setdiff(all_subgroups_in_data, subgroups_in_res)
    valid_sg_names <- subgroups_in_res
    
    # Note: subgroup_exclusions is initialized globally in plot generation
    print(paste("DEBUG: subgroup_exclusions exists at start of exclusion processing:", exists("subgroup_exclusions")))
    
    print(paste("DEBUG: All subgroups in original data:", paste(all_subgroups_in_data, collapse=", ")))
    print(paste("DEBUG: Subgroups in res_by_subgroup:", paste(subgroups_in_res, collapse=", ")))
    print(paste("DEBUG: Excluded subgroups (calculated):", paste(excluded_subgroups, collapse=", ")))
    print(paste("DEBUG: Valid subgroups:", paste(valid_sg_names, collapse=", ")))
    
    # 除外理由を確認（1研究のみかどうか）
    if (length(excluded_subgroups) > 0) {{
        for (excluded_sg in excluded_subgroups) {{
            n_studies_excluded <- all_studies_per_sg[excluded_sg]
            print(paste("Subgroup '", excluded_sg, "' was excluded (n=", n_studies_excluded, " studies)", sep=""))
        }}
    }}
    
    # 有効なサブグループのみでフィルタリング
    if (length(valid_sg_names) == 0) {{
        print("All subgroups have insufficient data (n<=1). Skipping subgroup forest plot.")
        plot(1, type="n", main="Subgroup Forest Plot: Insufficient Data", xlab="", ylab="")
        text(1, 1, "All subgroups have insufficient data (n<=1)\nfor forest plot visualization", col="red", cex=1.2)
        dev.off()
        next
    }}
    
    # 除外後のパラメータ更新
    sg_level_names <- valid_sg_names
    n_sg_levels <- length(sg_level_names)
    studies_per_sg <- studies_per_sg[sg_level_names]
    
    # 除外後のデータでdat_orderedを再作成（重要な修正）
    dat_ordered_filtered <- dat_ordered[dat_ordered[['Region']] %in% valid_sg_names, ]
    
    print(paste("DEBUG: Original data rows:", nrow(dat_ordered)))
    print(paste("DEBUG: Filtered data rows:", nrow(dat_ordered_filtered)))
    
    # 除外されたサブグループ情報をサマリーに記録
    print(paste("DEBUG: About to check excluded_subgroups condition, length:", length(excluded_subgroups)))
    print(paste("DEBUG: subgroup_exclusions exists before condition:", exists("subgroup_exclusions")))
    if (length(excluded_subgroups) > 0) {{
        print("DEBUG: Entered excluded_subgroups > 0 condition block")
        excluded_info <- list(
            excluded_subgroups = excluded_subgroups,
            reason = "insufficient_data_n_le_1",
            included_subgroups = valid_sg_names
        )
        
        # summary_listに直接追加（より確実な方法）
        if (!exists("summary_list")) {{
            summary_list <- list()
        }}
        if (is.null(summary_list$subgroup_exclusions)) {{
            summary_list$subgroup_exclusions <- list()
        }}
        summary_list$subgroup_exclusions[['Region']] <- excluded_info
        
        # Skip problematic global variable assignment - use summary_list only
        print("DEBUG: Skipping subgroup_exclusions global assignment, using summary_list only")
        
        # デバッグ用ログ出力
        print(paste("DEBUG: Excluded subgroups for Region:", paste(excluded_subgroups, collapse=", ")))
        print(paste("DEBUG: subgroup_exclusions variable exists:", exists("subgroup_exclusions")))
        print(paste("DEBUG: summary_list$subgroup_exclusions exists:", !is.null(summary_list$subgroup_exclusions)))
    }}
    
    # 行位置を計算 (下から上へ) - 除外後のデータに基づいて計算
    # 各サブグループ間に2行のギャップ（1行はサブグループサマリー、1行は空白）
    total_studies_filtered <- nrow(dat_ordered_filtered)
    current_row <- total_studies_filtered + (n_sg_levels * 2) + 2  # 開始位置
    
    rows_list <- list()
    subtotal_rows <- c()
    
    # 除外後のデータでのサブグループ別研究数を再計算
    studies_per_sg_filtered <- table(dat_ordered_filtered[['Region']])[sg_level_names]
    
    for (i in 1:n_sg_levels) {{
        sg_name <- sg_level_names[i]
        n_studies_sg <- studies_per_sg_filtered[sg_name]
        print(paste("DEBUG: Subgroup", sg_name, "filtered studies:", n_studies_sg))
        
        # この サブグループの研究の行位置
        study_rows <- seq(current_row - n_studies_sg + 1, current_row)
        rows_list[[sg_name]] <- study_rows
        
        # サブグループサマリーの行位置
        subtotal_row <- current_row - n_studies_sg - 1
        subtotal_rows <- c(subtotal_rows, subtotal_row)
        names(subtotal_rows)[length(subtotal_rows)] <- sg_name
        
        # 次のサブグループのための位置更新 (2行のギャップ)
        current_row <- current_row - n_studies_sg - 2
    }}
    
    # 全ての研究の行位置を統合
    all_study_rows <- unlist(rows_list[sg_level_names])
    
    # 行位置は後でres_for_plot_filteredに合わせて調整される
    
    # ylimを設定 (十分な空間を確保)
    ylim_bottom <- min(subtotal_rows) - 3
    ylim_top <- max(all_study_rows) + 3
    
    # --- 高さ計算 ---
    total_plot_rows <- ylim_top - ylim_bottom + extra_rows_sg_val
    plot_height_in_sg <- max(base_h_in_sg_val, total_plot_rows * row_h_in_sg_val)

    png('forest_plot_subgroup_Region.png', 
        width=plot_width_in_sg_val, 
        height=plot_height_in_sg, 
        units="in", res=plot_dpi_sg_val, pointsize=9)
    
    tryCatch({{
        current_measure <- "OR"
        apply_exp_transform <- current_measure %in% c("OR", "RR", "HR", "IRR", "PLO", "IR")
        
        # ilab データの準備
        ilab_data_main <- NULL
        ilab_xpos_main <- NULL
        ilab_lab_main <- NULL
        if (current_measure %in% c("OR", "RR", "RD", "PETO")) {{
            ai_col_main <- "events_treatment"
            bi_col_main <- "total_treatment"
            ci_col_main <- "events_control"
            di_col_main <- "total_control"
            n1i_col_main <- ""
            n2i_col_main <- ""
            
            # Events/Total 形式で表示（除外後のデータを使用）
            if (ai_col_main != "" && ci_col_main != "" && n1i_col_main != "" && n2i_col_main != "" &&
                all(c(ai_col_main, ci_col_main, n1i_col_main, n2i_col_main) %in% names(dat))) {{
                treatment_display_main <- paste(dat_ordered_filtered[[ai_col_main]], "/", dat_ordered_filtered[[n1i_col_main]], sep="")
                control_display_main <- paste(dat_ordered_filtered[[ci_col_main]], "/", dat_ordered_filtered[[n2i_col_main]], sep="")
                ilab_data_main <- cbind(treatment_display_main, control_display_main)
                ilab_xpos_main <- c(-8.5, -5.5)
                ilab_lab_main <- c("Events/Total", "Events/Total")
            }} else if (ai_col_main != "" && ci_col_main != "" && all(c(ai_col_main, ci_col_main) %in% names(dat))) {{
                # フォールバック: イベント数のみ（除外後のデータを使用）
                ilab_data_main <- cbind(dat_ordered_filtered[[ai_col_main]], dat_ordered_filtered[[ci_col_main]])
                ilab_xpos_main <- c(-8.5, -5.5)
                ilab_lab_main <- c("Events", "Events")
            }}
        }} else if (current_measure %in% c("SMD", "MD", "ROM")) {{
            # 連続アウトカムの場合: n1i, n2i を表示
            n1i_col_main <- ""
            n2i_col_main <- ""
            
            if (n1i_col_main != "" && n2i_col_main != "" && all(c(n1i_col_main, n2i_col_main) %in% names(dat))) {{
                ilab_data_main <- cbind(dat_ordered_filtered[[n1i_col_main]], dat_ordered_filtered[[n2i_col_main]])
                ilab_xpos_main <- c(-8.5, -5.5)
                ilab_lab_main <- c("N", "N")
            }}
        }}
        
        # res_for_plotをフィルタリング（除外されたサブグループのデータを削除）
        print("DEBUG: Filtering res_for_plot for subgroup forest plot")
        print(paste("DEBUG: Original res_for_plot data rows:", nrow(res_for_plot$data)))
        print(paste("DEBUG: Filtered data rows:", nrow(dat_ordered_filtered)))
        
        # フィルタ済みデータのインデックスを取得（Study列で照合）
        if ("Study" %in% names(res_for_plot$data)) {{
            filtered_indices <- which(res_for_plot$data$Study %in% dat_ordered_filtered$Study)
        }} else {{
            # Study列がない場合は、dat_ordered_filteredと同じ順序でインデックスを取得
            original_order <- match(rownames(dat_ordered_filtered), rownames(dat))
            filtered_indices <- original_order[!is.na(original_order)]
        }}
        
        print(paste("DEBUG: Filtered indices length:", length(filtered_indices)))
        print(paste("DEBUG: dat_ordered_filtered rows:", nrow(dat_ordered_filtered)))
        
        # インデックスの長さがdat_ordered_filteredと一致することを確認
        if (length(filtered_indices) != nrow(dat_ordered_filtered)) {{
            print("ERROR: Index length mismatch, using sequential indices")
            filtered_indices <- seq_len(nrow(dat_ordered_filtered))
        }}
        
        # res_for_plotのコピーを作成し、フィルタ済みデータのみを含むようにする
        res_for_plot_filtered <- res_for_plot
        
        # 効果量と分散をフィルタリング
        res_for_plot_filtered$yi <- res_for_plot$yi[filtered_indices]
        res_for_plot_filtered$vi <- res_for_plot$vi[filtered_indices]
        res_for_plot_filtered$se <- res_for_plot$se[filtered_indices]
        
        # その他の要素もフィルタリング（存在する場合）
        if (!is.null(res_for_plot$ni)) {{
            res_for_plot_filtered$ni <- res_for_plot$ni[filtered_indices]
        }}
        if (!is.null(res_for_plot$weights)) {{
            res_for_plot_filtered$weights <- res_for_plot$weights[filtered_indices]
        }}
        
        # slabもフィルタリング（重要：整合性を保つ）
        if (!is.null(res_for_plot$slab)) {{
            res_for_plot_filtered$slab <- res_for_plot$slab[filtered_indices]
        }}
        
        # データ行数を更新
        res_for_plot_filtered$k <- length(filtered_indices)
        
        # データフレームもフィルタリング
        res_for_plot_filtered$data <- res_for_plot$data[filtered_indices, ]
        
        # ilab_data_main も同様にフィルタリング（重要：サイズ整合性維持）
        if (!is.null(ilab_data_main)) {{
            ilab_data_main <- ilab_data_main[filtered_indices, , drop=FALSE]
            print(paste("DEBUG: Filtered ilab_data_main to", nrow(ilab_data_main), "rows"))
            
            # サイズ検証
            if (nrow(ilab_data_main) != res_for_plot_filtered$k) {{
                print("WARNING: ilab size still mismatched after filtering, disabling ilab")
                ilab_data_main <- NULL
                ilab_xpos_main <- NULL  
                ilab_lab_main <- NULL
            }}
        }}
        
        print(paste("DEBUG: res_for_plot_filtered k:", res_for_plot_filtered$k))
        print(paste("DEBUG: res_for_plot_filtered data rows:", nrow(res_for_plot_filtered$data)))
        print(paste("DEBUG: dat_ordered_filtered rows:", nrow(dat_ordered_filtered)))
        print(paste("DEBUG: slab length in filtered data:", length(res_for_plot_filtered$slab)))
        
        # 修正: subset引数は使用せず、フィルタ済みデータを直接使用
        # forest()関数はsubsetパラメータをサポートしていないため
        print("DEBUG: Using pre-filtered data for forest plot - no subset parameter needed")
        
        # 行位置をフィルタ済みデータのサイズに調整
        if (length(all_study_rows) != length(filtered_indices)) {{
            print("WARNING: Adjusting row positions to match filtered data size")
            # 実際のフィルタ済みデータのサイズに基づいて行位置を再計算
            total_filtered_studies <- length(filtered_indices)
            all_study_rows <- seq(1, total_filtered_studies)
            
            # ylimも再調整
            ylim_bottom <- min(subtotal_rows) - 3
            ylim_top <- max(all_study_rows) + 3
        }}
        
        # メインのforest plotを描画（修正版：フィルタ済みデータを使用）
        # forest()関数はsubsetパラメータをサポートしていないため、フィルタ済みデータを使用
        forest_sg_args <- list(
            x = res_for_plot_filtered, # フィルタ済みデータを使用
            rows = all_study_rows,
            ylim = c(ylim_bottom, ylim_top),
            atransf = if(apply_exp_transform) exp else I,
            at = if(apply_exp_transform) log(c(0.25, 1, 4)) else NULL,
            xlim = c(-16, 6),
            digits = 2,
            header = "Author(s) and Year",
            refline = if(apply_exp_transform) 0 else 0,
            cex = 0.75,
            mlab = ""
        )
        
        if (!is.null(ilab_data_main)) {{
            forest_sg_args$ilab <- ilab_data_main
            forest_sg_args$ilab.xpos <- ilab_xpos_main
            forest_sg_args$ilab.lab <- ilab_lab_main
        }}
        
        do.call(forest, forest_sg_args)
        
        # Treatment/Control ヘッダーの追加
        if (!is.null(ilab_data_main) && length(ilab_xpos_main) == 2) {{
             text(c(-8.5,-5.5), ylim_top - 1, c("Treatment", "Control"), font=2, cex=0.75)
        }}
        
        # サブグループラベルとサマリーポリゴンを追加
        for (i in 1:n_sg_levels) {{
            sg_name <- sg_level_names[i]
            res_sg_obj <- res_by_subgroup_Region[[sg_name]]
            subtotal_row <- subtotal_rows[sg_name]
            
            if (!is.null(res_sg_obj)) {{
                # サブグループ名をラベルとして追加
                text(-16, max(rows_list[[sg_name]]) + 0.5, 
                     paste0(sg_name, " (k=", res_sg_obj$k, ")"), 
                     pos=4, font=4, cex=0.75)
                
                # サブグループの合計行を追加（二値アウトカムの場合のみ）
                if (current_measure %in% c("OR", "RR", "RD", "PETO") && !is.null(ilab_data_main)) {{
                    ai_col_sg <- "events_treatment"
                    ci_col_sg <- "events_control"
                    n1i_col_sg <- ""
                    n2i_col_sg <- ""
                    
                    if (ai_col_sg != "" && ci_col_sg != "" && n1i_col_sg != "" && n2i_col_sg != "" &&
                        all(c(ai_col_sg, ci_col_sg, n1i_col_sg, n2i_col_sg) %in% names(dat))) {{
                        
                        # このサブグループのデータのみを抽出（除外後のデータから）
                        sg_data <- dat_ordered_filtered[dat_ordered_filtered[['Region']] == sg_name, ]
                        
                        if (nrow(sg_data) > 0) {{
                            sg_total_ai <- sum(sg_data[[ai_col_sg]], na.rm = TRUE)
                            sg_total_n1i <- sum(sg_data[[n1i_col_sg]], na.rm = TRUE)
                            sg_total_ci <- sum(sg_data[[ci_col_sg]], na.rm = TRUE)
                            sg_total_n2i <- sum(sg_data[[n2i_col_sg]], na.rm = TRUE)
                            
                            # サブグループ合計行の位置（サブグループの最小行の0.3行上）
                            sg_total_row_y <- min(rows_list[[sg_name]]) - 0.3
                            
                            # サブグループ合計行のラベルと数値を表示
                            text(-16, sg_total_row_y, paste0(sg_name, " Total"), font = 2, pos = 4, cex = 0.7)
                            text(c(-8.5, -5.5), sg_total_row_y, 
                                 c(paste(sg_total_ai, "/", sg_total_n1i, sep=""),
                                   paste(sg_total_ci, "/", sg_total_n2i, sep="")),
                                 font = 2, cex = 0.7)
                        }}
                    }}
                }} else if (current_measure %in% c("SMD", "MD", "ROM") && !is.null(ilab_data_main)) {{
                    # 連続アウトカムの場合: サブグループ別のサンプルサイズ合計
                    n1i_col_sg <- ""
                    n2i_col_sg <- ""
                    
                    if (n1i_col_sg != "" && n2i_col_sg != "" && all(c(n1i_col_sg, n2i_col_sg) %in% names(dat))) {{
                        sg_data <- dat_ordered_filtered[dat_ordered_filtered[['Region']] == sg_name, ]
                        
                        if (nrow(sg_data) > 0) {{
                            sg_total_n1i <- sum(sg_data[[n1i_col_sg]], na.rm = TRUE)
                            sg_total_n2i <- sum(sg_data[[n2i_col_sg]], na.rm = TRUE)
                            
                            sg_total_row_y <- min(rows_list[[sg_name]]) - 0.3
                            
                            text(-16, sg_total_row_y, paste0(sg_name, " Total"), font = 2, pos = 4, cex = 0.7)
                            text(c(-8.5, -5.5), sg_total_row_y, 
                                 c(sg_total_n1i, sg_total_n2i),
                                 font = 2, cex = 0.7)
                        }}
                    }}
                }}
                
                # サブグループサマリーポリゴンを追加
                if (apply_exp_transform) {{
                    mlab_text <- sprintf("Subtotal: %s=%.2f [%.2f, %.2f], p=%.3f, I²=%.1f%%",
                                        current_measure,
                                        exp(as.numeric(res_sg_obj$b)[1]),
                                        exp(as.numeric(res_sg_obj$ci.lb)[1]),
                                        exp(as.numeric(res_sg_obj$ci.ub)[1]),
                                        as.numeric(res_sg_obj$pval)[1],
                                        res_sg_obj$I2)
                }} else {{
                    mlab_text <- sprintf("Subtotal: Effect=%.2f [%.2f, %.2f], p=%.3f, I²=%.1f%%",
                                        as.numeric(res_sg_obj$b)[1],
                                        as.numeric(res_sg_obj$ci.lb)[1],
                                        as.numeric(res_sg_obj$ci.ub)[1],
                                        as.numeric(res_sg_obj$pval)[1],
                                        res_sg_obj$I2)
                }}
                addpoly(res_sg_obj, row=subtotal_row, mlab=mlab_text, cex=0.70, font=2)
            }}
        }}

        # 全体サマリーを最下部に追加
        overall_row <- ylim_bottom + 2
        if (apply_exp_transform) {{
            overall_mlab <- sprintf("Overall: %s=%.2f [%.2f, %.2f], I²=%.1f%%",
                                   current_measure,
                                   exp(as.numeric(res_for_plot$b)[1]),
                                   exp(as.numeric(res_for_plot$ci.lb)[1]),
                                   exp(as.numeric(res_for_plot$ci.ub)[1]),
                                   res_for_plot$I2)
        }} else {{
            overall_mlab <- sprintf("Overall: Effect=%.2f [%.2f, %.2f], I²=%.1f%%",
                                   as.numeric(res_for_plot$b)[1],
                                   as.numeric(res_for_plot$ci.lb)[1],
                                   as.numeric(res_for_plot$ci.ub)[1],
                                   res_for_plot$I2)
        }}
        addpoly(res_for_plot, row=overall_row, mlab=overall_mlab, cex=0.75, font=2)

        # サブグループ間の差の検定結果を追加
        test_res_sg <- res_subgroup_test_Region
        text(-16, ylim_bottom + 0.5, pos=4, cex=0.75,
             sprintf("Test for Subgroup Differences (Q_M = %.2f, df = %d, p = %.3f)",
                    test_res_sg$QM, test_res_sg$p - 1, test_res_sg$QMp))
        
    }}, error = function(e) {{
        plot(1, type="n", main="Subgroup Forest Plot Error (Region)", xlab="", ylab="")
        text(1, 1, paste("Error generating subgroup forest plot for Region:
", e$message), col="red")
        print(sprintf("Subgroup forest plot generation failed for Region: %s", e$message))
    }})
    dev.off()
}} else {{
    print("DEBUG: Prerequisites not met for subgroup forest plot generation")
    print("DEBUG: Skipping subgroup forest plot for Region")
}}



# ファンネルプロット作成
png('comprehensive_test_funnel_plot.png', width=2400, height=2400, res=300, pointsize=9)
tryCatch({{
    funnel(res)
    # Egger's testの結果を追記することも可能
    # egger_res <- regtest(res)
    # legend("topright", legend=paste("Egger's test p =", format.pval(egger_res$pval, digits=3)), bty="n")
}}, error = function(e) {{
    plot(1, type="n", main="Funnel Plot Error", xlab="", ylab="")
    text(1, 1, paste("Error generating funnel plot:
", e$message), col="red")
    print(sprintf("Funnel plot generation failed: %s", e$message))
}})
dev.off()



# 結果の保存 (preserve existing summary_list with exclusion info)
if (!exists("summary_list")) {
    summary_list <- list()
    print("DEBUG: Created new summary_list in save_results")
} else {
    print("DEBUG: Preserving existing summary_list with potential exclusion info")
}

# バージョン情報を最初に追加（エラーが発生しても保持されるように）
summary_list$r_version <- R.version.string
summary_list$metafor_version <- as.character(packageVersion("metafor"))

# 詳細な解析環境情報
summary_list$analysis_environment <- list(
    r_version_full = R.version.string,
    r_version_short = paste(R.version$major, R.version$minor, sep="."),
    metafor_version = as.character(packageVersion("metafor")),
    jsonlite_version = as.character(packageVersion("jsonlite")),
    platform = R.version$platform,
    os_type = .Platform$OS.type,
    analysis_date = as.character(Sys.Date()),
    analysis_time = as.character(Sys.time()),
    packages_info = list(
        metafor = list(
            version = as.character(packageVersion("metafor")),
            description = "Conducting Meta-Analyses in R"
        ),
        jsonlite = list(
            version = as.character(packageVersion("jsonlite")),
            description = "JSON output generation"
        )
    )
)

tryCatch({
    summary_list$overall_summary_text <- paste(capture.output(summary(res)), collapse = "
")
    
    summary_list$overall_analysis <- list(
        k = res$k,
        estimate = as.numeric(res$b)[1], 
        se = as.numeric(res$se)[1],    
        zval = as.numeric(res$zval)[1],  
        pval = as.numeric(res$pval)[1],  
        ci_lb = as.numeric(res$ci.lb)[1],
        ci_ub = as.numeric(res$ci.ub)[1],
        I2 = res$I2,
        H2 = res$H2,
        tau2 = res$tau2,
        QE = res$QE,
        QEp = res$QEp,
        method = res$method
    )
    
    
    if (exists("res_subgroup_test_Region") && !is.null(res_subgroup_test_Region)) {
        summary_list$subgroup_moderation_test_Region <- list(
            subgroup_column = "Region", QM = res_subgroup_test_Region$QM,
            QMp = res_subgroup_test_Region$QMp, df = res_subgroup_test_Region$p -1, # df is p-1 for QM
            summary_text = paste(capture.output(print(res_subgroup_test_Region)), collapse = "\n")
        )
    }
    if (exists("res_by_subgroup_Region") && !is.null(res_by_subgroup_Region) && length(res_by_subgroup_Region) > 0) {
        subgroup_results_list_Region <- list()
        for (subgroup_name_idx in seq_along(res_by_subgroup_Region)) {
            current_res_sg <- res_by_subgroup_Region[[subgroup_name_idx]]
            subgroup_level_name <- names(res_by_subgroup_Region)[subgroup_name_idx]
            if (!is.null(current_res_sg)) { # NULLチェックを追加
                subgroup_results_list_Region[[subgroup_level_name]] <- list(
                    k = current_res_sg$k, estimate = as.numeric(current_res_sg$b)[1], 
                    se = as.numeric(current_res_sg$se)[1], zval = as.numeric(current_res_sg$zval)[1],
                    pval = as.numeric(current_res_sg$pval)[1], ci_lb = as.numeric(current_res_sg$ci.lb)[1],
                    ci_ub = as.numeric(current_res_sg$ci.ub)[1], I2 = current_res_sg$I2, tau2 = current_res_sg$tau2,
                    summary_text = paste(capture.output(print(current_res_sg)), collapse = "\n")
                )
            }
        }
        summary_list$subgroup_analyses_Region <- subgroup_results_list_Region
    }


    
    
    
    if (exists("egger_test_res") && !is.null(egger_test_res)) {
        summary_list$egger_test <- list(
            statistic = egger_test_res$statistic,
            pval = egger_test_res$p.value,
            summary_text = paste(capture.output(print(egger_test_res)), collapse = "\n")
        )
    } else {
        summary_list$egger_test <- list(message = "Egger's test was not performed or resulted in an error.")
    }

    
    # ゼロセル情報を追加（存在する場合）
    if (exists("zero_cells_summary") && !is.null(zero_cells_summary)) {
        summary_list$zero_cells_summary <- zero_cells_summary
        print("Zero cell summary added to JSON output")
    }

}, error = function(e_sum) {
    summary_list$error_in_summary_generation <- paste("Error creating parts of summary:", e_sum$message)
    print(sprintf("Error creating parts of summary_list: %s", e_sum$message))
})

summary_list$generated_plots_paths <- list(list(label = "forest_plot_overall", path = "comprehensive_test_forest_plot.png"), list(label = "forest_plot_subgroup_Region", path = "forest_plot_subgroup_Region.png"), list(label = "funnel_plot", path = "comprehensive_test_funnel_plot.png"))

# Note: Subgroup exclusions are already saved in summary_list during forest plot generation
print("DEBUG: Subgroup exclusions stored in summary_list during processing")

# main_analysis_methodをトップレベルに移動（ゼロセル対応から）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    summary_list$main_analysis_method <- "Mantel-Haenszel (no correction)"
}} else {{
    summary_list$main_analysis_method <- "Inverse Variance (standard)"
}}

json_output_file_path <- "comprehensive_test_results.json"
tryCatch({
    json_data <- jsonlite::toJSON(summary_list, auto_unbox = TRUE, pretty = TRUE, null = "null", force=TRUE)
    write(json_data, file=json_output_file_path)
    print(paste("Analysis summary saved to JSON:", json_output_file_path))
}, error = function(e_json) {
    print(paste("Error saving summary_list as JSON:", e_json$message))
    tryCatch({
        error_json <- jsonlite::toJSON(list(error="Failed to serialize full R results to JSON", details=e_json$message), auto_unbox = TRUE, pretty = TRUE)
        write(error_json, file=json_output_file_path)
    }, error = function(e_json_fallback) {
        print(paste("Error saving fallback error JSON:", e_json_fallback$message))
    })
    print(sprintf("Error saving summary_list as JSON: %s", e_json$message))
})

tryCatch({
    save(res, res_by_subgroup_Region, res_subgroup_test_Region, res_for_plot, file='comprehensive_test_results.RData') 
    print(paste("RData saved to:", 'comprehensive_test_results.RData'))
}, error = function(e_rdata) {
    print(paste("Error saving RData:", e_rdata$message))
    print(sprintf("Error saving RData: %s", e_rdata$message))
})
