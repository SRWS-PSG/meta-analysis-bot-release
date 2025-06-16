
library(metafor)
library(jsonlite)


dat <- read.csv('/tmp/tmpp6vwxxth.csv', na.strings = c('NA', 'na', 'N/A', 'n/a', ''))


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

png('forest_plot.png', width=plot_width_in_val, height=plot_height_in_main, units="in", res=plot_dpi_val, pointsize=9)
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



# ファンネルプロット作成
png('funnel_plot.png', width=2400, height=2400, res=300, pointsize=9)
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

summary_list$generated_plots_paths <- list(list(label = "forest_plot_overall", path = "forest_plot.png"), list(label = "funnel_plot", path = "funnel_plot.png"))

# Note: Subgroup exclusions are already saved in summary_list during forest plot generation
print("DEBUG: Subgroup exclusions stored in summary_list during processing")

# main_analysis_methodをトップレベルに移動（ゼロセル対応から）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    summary_list$main_analysis_method <- "Mantel-Haenszel (no correction)"
}} else {{
    summary_list$main_analysis_method <- "Inverse Variance (standard)"
}}

json_output_file_path <- "results.json"
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
    save(res, res_for_plot, file='results.RData') 
    print(paste("RData saved to:", 'results.RData'))
}, error = function(e_rdata) {
    print(paste("Error saving RData:", e_rdata$message))
    print(sprintf("Error saving RData: %s", e_rdata$message))
})
