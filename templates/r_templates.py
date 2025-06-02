"""
Rスクリプトテンプレートに基づいてRコードを生成するモジュール
"""
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class RTemplateGenerator:
    """
    Rスクリプトテンプレートを管理し、パラメータに基づいてRコードを生成するクラス
    """
    # プロットサイズのデフォルト値
    PLOT_ROW_H_IN = 0.3  # 1行あたりの高さ (インチ)
    PLOT_BASE_H_IN = 6   # ベースの高さ (インチ)
    PLOT_WIDTH_IN = 10   # プロットの幅 (インチ)
    PLOT_DPI = 300       # 解像度 (dpi)
    PLOT_EXTRA_ROWS_MAIN = 5 # メインプロット用の追加行数 (タイトル、全体サマリーなど)
    PLOT_EXTRA_ROWS_SUBGROUP = 7 # サブグループプロット用の追加行数 (全体タイトル、サブグループタイトル、全体サマリーなど)


    def __init__(self):
        """
        RTemplateGeneratorを初期化し、テンプレートをロードします。
        """
        self.templates = self._load_templates()

    def _safe_format(self, template: str, **kwargs) -> str:
        """Safely format a template containing many curly braces.

        Parameters
        ----------
        template : str
            The template string where ``{placeholder}`` will be replaced.
            Any other ``{`` or ``}`` are treated as literal braces.
        **kwargs : Any
            Values to substitute for placeholders.

        Returns
        -------
        str
            The formatted string with placeholders replaced and all other
            braces preserved.
        """
        # Temporarily replace placeholders with unique tokens so we can
        # escape the remaining curly braces without interfering with them.
        token_map = {}
        for key in kwargs:
            token = f"__PLACEHOLDER_{key.upper()}__"
            token_map[token] = f"{{{key}}}"
            template = template.replace(f"{{{key}}}", token)

        # Escape any remaining braces which belong to the R code itself.
        template = template.replace('{', '{{').replace('}', '}}')

        # Restore the placeholder tokens to standard format markers.
        for token, marker in token_map.items():
            template = template.replace(token, marker)

        return template.format(**kwargs)

    def _load_templates(self) -> Dict[str, str]:
        """
        Rスクリプトのテンプレートをロードします。
        将来的にはファイルや設定からロードするように拡張します。
        現時点では、主要なテンプレートのプレースホルダーを定義します。
        """
        templates = {
            "library_load": """
library(metafor)
library(jsonlite)
""",
            "data_load": """
# CSVファイルからデータを読み込みます
# この部分は呼び出し側で dat <- read.csv('{csv_path}') のように挿入される想定
""",
            "escalc_binary": """
# 二値アウトカムの効果量計算 (例: オッズ比)
dat <- escalc(measure="{measure}", ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat{slab_param_string})
""",
            "escalc_continuous": """
# 連続アウトカムの効果量計算 (例: 標準化平均差)
dat <- escalc(measure="{measure}", n1i={n1i}, n2i={n2i}, m1i={m1i}, m2i={m2i}, sd1i={sd1i}, sd2i={sd2i}, data=dat{slab_param_string})
""",
            "escalc_proportion": """
# 割合の効果量計算
dat <- escalc(measure="{measure}", xi={events}, ni={total}, data=dat{slab_param_string})
""",
             "escalc_precalculated": """
# 事前計算された効果量を使用 (yi, vi)
# この場合、escalcは不要なことが多いが、もし追加処理が必要ならここに記述
""",
            "rma_basic": """
# 基本的なメタアナリシス実行
res <- rma(yi, vi, data=dat, method="{method}")
""",
            "rma_with_mods": """
# モデレーターを用いたメタ回帰実行
res <- rma(yi, vi, mods = ~ {mods_formula}, data=dat, method="{method}")
""",
            "subgroup_analysis": """
# サブグループ解析 (必要な場合)
# 各サブグループ変数ごとに解析を実行
# for (subgroup_col in c({subgroup_columns_list})) {{
#     if (subgroup_col %in% names(dat)) {{
#         # サブグループ間の差の検定
#         res_subgroup_test_{subgroup_col} <- rma(yi, vi, mods = ~ factor(dat[[subgroup_col]]), data=dat, method="{method}")
#         # 各サブグループごとの解析 (これは通常プロットや詳細表示用)
#         # by = factor(dat[[subgroup_col]]) を使用
#         res_by_subgroup_{subgroup_col} <- rma(yi, vi, data=dat, method="{method}", by = factor(dat[[subgroup_col}]))
#     }}
# }}
""",
            "forest_plot": """
# フォレストプロット作成
# メインのフォレストプロット

# --- プロットサイズパラメータ ---
row_h_in_val <- {row_h_in_placeholder}        # 1行あたりの高さ (インチ)
base_h_in_val <- {base_h_in_placeholder}       # ベースの高さ (インチ)
plot_width_in_val <- {plot_width_in_placeholder} # プロットの幅 (インチ)
plot_dpi_val <- {plot_dpi_placeholder}         # 解像度 (dpi)
extra_rows_val <- {extra_rows_main_placeholder} # 追加行数

# --- 高さ計算 ---
# res_for_plot がこの時点で存在することを前提とする
k_study_main <- ifelse(exists("res_for_plot") && !is.null(res_for_plot$k), res_for_plot$k, nrow(dat))
k_header_main <- 0 # メインプロットではサブグループヘッダーは基本なし
plot_height_in_main <- max(base_h_in_val, (k_study_main + k_header_main + extra_rows_val) * row_h_in_val)

png('{forest_plot_path}', width=plot_width_in_val, height=plot_height_in_main, units="in", res=plot_dpi_val, pointsize=9)
tryCatch({{
    # 効果量の種類に応じて atransf と at を調整
    current_measure <- "{measure_for_plot}"
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
        ai_col <- "{ai_col}"
        bi_col <- "{bi_col}" 
        ci_col <- "{ci_col}"
        di_col <- "{di_col}" 
        
        required_ilab_cols <- c(ai_col, bi_col, ci_col, di_col)
        required_ilab_cols <- required_ilab_cols[required_ilab_cols != ""]

        if (length(required_ilab_cols) == 4 && all(required_ilab_cols %in% names(dat))) {{
            ilab_data <- cbind(dat[[ai_col]], dat[[bi_col]], dat[[ci_col]], dat[[di_col]])
            ilab_xpos <- c(-9.5, -8, -6, -4.5) 
            ilab_lab <- c("Events", "No Events", "Events", "No Events") 
        }} else if (length(required_ilab_cols) == 2 && all(required_ilab_cols %in% names(dat))) {{
            ilab_data <- cbind(dat[[ai_col]], dat[[ci_col]])
            ilab_xpos <- c(-9.5, -6)
            ilab_lab <- c("Events", "Events") 
        }}
    }}

    # フォレストプロット描画 (res_for_plot を使用)
    forest_args <- list(
        x = res_for_plot,
        slab = dat$slab,
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

    if (!is.null(ilab_data) && length(ilab_xpos) == 4) { 
        text(c(-8.75, -5.25), res_for_plot$k+2.8, c("Treatment", "Control"), cex=0.75, font=2)
    }
    
    text(-16, -1, pos=4, cex=0.75, bquote(paste(
        "RE Model (Q = ", .(formatC(res_for_plot$QE, digits=2, format="f")),
        ", df = ", .(res_for_plot$k - res_for_plot$p), ", ",
        "p = ", .(formatC(res_for_plot$QEp, digits=4, format="f")), "; ",
        I^2, " = ", .(formatC(res_for_plot$I2, digits=1, format="f")), "%, ",
        tau^2, " = ", .(formatC(res_for_plot$tau2, digits=2, format="f")), ")"
    )))
    
}}, error = function(e) {{
    plot(1, type="n", main="Forest Plot Error", xlab="", ylab="")
    text(1, 1, paste("Error generating forest plot:\n", e$message), col="red")
    logger::log_error(sprintf("Forest plot generation failed: %s", e$message))
}})
dev.off()
""",
            "subgroup_forest_plot_template": """
# サブグループ '{subgroup_col_name}' のフォレストプロット
if (exists("res_by_subgroup_{subgroup_col_name}") && !is.null(res_by_subgroup_{subgroup_col_name}) && 
    exists("res_subgroup_test_{subgroup_col_name}") && !is.null(res_subgroup_test_{subgroup_col_name}) &&
    exists("res_for_plot") && !is.null(res_for_plot)) {{ # res_for_plot の存在も確認
    
    # --- プロットサイズパラメータ ---
    row_h_in_sg_val <- {row_h_in_placeholder}
    base_h_in_sg_val <- {base_h_in_placeholder}
    plot_width_in_sg_val <- {plot_width_in_placeholder}
    plot_dpi_sg_val <- {plot_dpi_placeholder}
    extra_rows_sg_val <- {extra_rows_subgroup_placeholder}

    # --- サブグループごとの行位置計算 ---
    sg_level_names <- names(res_by_subgroup_{subgroup_col_name})
    n_sg_levels <- length(sg_level_names)
    
    # データをサブグループでソート
    dat_ordered <- dat[order(dat[['{subgroup_col_name}']]), ]
    
    # 各サブグループの研究数を計算
    studies_per_sg <- table(dat[['{subgroup_col_name}']])[sg_level_names]
    
    # 行位置を計算 (下から上へ)
    # 各サブグループ間に2行のギャップ（1行はサブグループサマリー、1行は空白）
    total_studies <- nrow(dat)
    current_row <- total_studies + (n_sg_levels * 2) + 2  # 開始位置
    
    rows_list <- list()
    subtotal_rows <- c()
    
    for (i in 1:n_sg_levels) {{
        sg_name <- sg_level_names[i]
        n_studies_sg <- studies_per_sg[sg_name]
        
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
    
    # ylimを設定 (十分な空間を確保)
    ylim_bottom <- min(subtotal_rows) - 3
    ylim_top <- max(all_study_rows) + 3
    
    # --- 高さ計算 ---
    total_plot_rows <- ylim_top - ylim_bottom + extra_rows_sg_val
    plot_height_in_sg <- max(base_h_in_sg_val, total_plot_rows * row_h_in_sg_val)

    png('{subgroup_forest_plot_path}', 
        width=plot_width_in_sg_val, 
        height=plot_height_in_sg, 
        units="in", res=plot_dpi_sg_val, pointsize=9)
    
    tryCatch({{
        current_measure <- "{measure_for_plot}"
        apply_exp_transform <- current_measure %in% c("OR", "RR", "HR", "IRR", "PLO", "IR")
        
        # ilab データの準備
        ilab_data_main <- NULL
        ilab_xpos_main <- NULL
        ilab_lab_main <- NULL
        if (current_measure %in% c("OR", "RR", "RD", "PETO")) {{
            ai_col_main <- "{ai_col}"
            bi_col_main <- "{bi_col}"
            ci_col_main <- "{ci_col}"
            di_col_main <- "{di_col}"
            required_ilab_cols_main <- c(ai_col_main, bi_col_main, ci_col_main, di_col_main)
            required_ilab_cols_main <- required_ilab_cols_main[required_ilab_cols_main != ""]
            if (length(required_ilab_cols_main) == 4 && all(required_ilab_cols_main %in% names(dat))) {{
                ilab_data_main <- cbind(dat_ordered[[ai_col_main]], dat_ordered[[bi_col_main]], 
                                      dat_ordered[[ci_col_main]], dat_ordered[[di_col_main]])
                ilab_xpos_main <- c(-9.5, -8, -6, -4.5)
                ilab_lab_main <- c("Events", "No Events", "Events", "No Events")
            }}
        }}
        
        # メインのforest plotを描画（サブグループ順序、行位置指定）
        forest_sg_args <- list(
            x = {res_for_plot_model_name}, # res_for_plot を使用
            slab = dat_ordered$slab,
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
        if (!is.null(ilab_data_main) && length(ilab_xpos_main) == 4) {{
             text(c(-8.75,-5.25), ylim_top - 1, c("Treatment", "Control"), font=2, cex=0.75)
        }}
        
        # サブグループラベルとサマリーポリゴンを追加
        for (i in 1:n_sg_levels) {{
            sg_name <- sg_level_names[i]
            res_sg_obj <- res_by_subgroup_{subgroup_col_name}[[sg_name]]
            subtotal_row <- subtotal_rows[sg_name]
            
            if (!is.null(res_sg_obj)) {{
                # サブグループ名をラベルとして追加
                text(-16, max(rows_list[[sg_name]]) + 0.5, 
                     paste0(sg_name, " (k=", res_sg_obj$k, ")"), 
                     pos=4, font=4, cex=0.75)
                
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
                                   exp(as.numeric({res_for_plot_model_name}$b)[1]),
                                   exp(as.numeric({res_for_plot_model_name}$ci.lb)[1]),
                                   exp(as.numeric({res_for_plot_model_name}$ci.ub)[1]),
                                   {res_for_plot_model_name}$I2)
        }} else {{
            overall_mlab <- sprintf("Overall: Effect=%.2f [%.2f, %.2f], I²=%.1f%%",
                                   as.numeric({res_for_plot_model_name}$b)[1],
                                   as.numeric({res_for_plot_model_name}$ci.lb)[1],
                                   as.numeric({res_for_plot_model_name}$ci.ub)[1],
                                   {res_for_plot_model_name}$I2)
        }}
        addpoly({res_for_plot_model_name}, row=overall_row, mlab=overall_mlab, cex=0.75, font=2)

        # サブグループ間の差の検定結果を追加
        test_res_sg <- res_subgroup_test_{subgroup_col_name}
        text(-16, ylim_bottom + 0.5, pos=4, cex=0.75,
             sprintf("Test for Subgroup Differences (Q_M = %.2f, df = %d, p = %.3f)",
                    test_res_sg$QM, test_res_sg$p - 1, test_res_sg$QMp))
        
    }}, error = function(e) {{
        plot(1, type="n", main="Subgroup Forest Plot Error ({subgroup_col_name})", xlab="", ylab="")
        text(1, 1, paste("Error generating subgroup forest plot for {subgroup_col_name}:\n", e$message), col="red")
        logger::log_error(sprintf("Subgroup forest plot generation failed for {subgroup_col_name}: %s", e$message))
    }})
    dev.off()
}}
""",
            "funnel_plot": """
# ファンネルプロット作成
png('{funnel_plot_path}', width=2400, height=2400, res=300, pointsize=9)
tryCatch({{
    funnel(res)
    # Egger's testの結果を追記することも可能
    # egger_res <- regtest(res)
    # legend("topright", legend=paste("Egger's test p =", format.pval(egger_res$pval, digits=3)), bty="n")
}}, error = function(e) {{
    plot(1, type="n", main="Funnel Plot Error", xlab="", ylab="")
    text(1, 1, paste("Error generating funnel plot:\n", e$message), col="red")
    logger::log_error(sprintf("Funnel plot generation failed: %s", e$message))
}})
dev.off()
""",
            "bubble_plot": """
# バブルプロット作成 (メタ回帰用) - res_moderated を使用
# generate_full_r_script で res (メインモデル) が res_moderated という名前で生成されることを想定
if ("{moderator_column_for_bubble}" %in% names(dat) && exists("res") && !is.null(res$beta) && length(res$beta) > 1) {{
   actual_moderator_name_in_model <- "{moderator_column_for_bubble}" 
   is_moderator_in_model <- FALSE
   if (!is.null(rownames(res$beta))) {{
       if (any(grepl(paste0("^", actual_moderator_name_in_model), rownames(res$beta)[-1], fixed = FALSE)) ||
           any(grepl(paste0("^factor\\(", actual_moderator_name_in_model, "\\)"), rownames(res$beta)[-1], fixed = FALSE)) ){{
           is_moderator_in_model <- TRUE
       }}
   }}

   if (is_moderator_in_model) {{
       png('{bubble_plot_path}', width=2400, height=2400, res=300, pointsize=9)
       tryCatch({{
           regplot(res, mod="{moderator_column_for_bubble}", pred=TRUE, ci=TRUE, pi=TRUE,
                   xlab="{moderator_column_for_bubble}", ylab="Effect Size",
                   cex.axis=0.8,
                   cex.lab=0.9,
                   labsize=0.7)
       }}, error = function(e) {{
           plot(1, type="n", main="Bubble Plot Error", xlab="", ylab="")
           text(1, 1, paste("Error generating bubble plot for {moderator_column_for_bubble}:\n", e$message), col="red")
           logger::log_error(sprintf("Bubble plot generation failed for {moderator_column_for_bubble}: %s", e$message))
       }})
       dev.off()
   }} else {{
        print(paste("Bubble plot for {moderator_column_for_bubble} skipped: moderator not found in the main model 'res' or model has no moderators."))
   }}
}} else {{
    print(paste("Bubble plot for {moderator_column_for_bubble} skipped: moderator column not in data, 'res' object not found, or model has no moderators."))
}}
""",
            "save_results": """
# 結果の保存
summary_list <- list()
tryCatch({
    summary_list$overall_summary_text <- paste(capture.output(summary(res)), collapse = "\n")
    
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
    
    {subgroup_json_update_code}

    {regression_json_update_code}
    
    {egger_json_update_code}

    # Add R and metafor versions
    summary_list$r_version <- R.version.string
    summary_list$metafor_version <- as.character(packageVersion("metafor"))

}, error = function(e_sum) {
    summary_list$error_in_summary_generation <- paste("Error creating parts of summary:", e_sum$message)
    logger::log_error(sprintf("Error creating parts of summary_list: %s", e_sum$message))
})

{generated_plots_r_code}

json_output_file_path <- "{json_summary_path}"
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
    logger::log_error(sprintf("Error saving summary_list as JSON: %s", e_json$message))
})

tryCatch({
    save(res{additional_objects_str}, file='{rdata_path}') 
    print(paste("RData saved to:", '{rdata_path}'))
}, error = function(e_rdata) {
    print(paste("Error saving RData:", e_rdata$message))
    logger::log_error(sprintf("Error saving RData: %s", e_rdata$message))
})
""",
            "sensitivity_analysis": """
# 感度分析: {sensitivity_variable} = {sensitivity_value} に限定
if (exists("dat") && !is.null(dat) && "{sensitivity_variable}" %in% names(dat) && "{sensitivity_value}" %in% dat${sensitivity_variable}) {{
    n_total_sensitivity <- nrow(dat)
    n_category_sensitivity <- sum(dat${sensitivity_variable} == "{sensitivity_value}")
    dat_sensitivity <- dat[dat${sensitivity_variable} == "{sensitivity_value}", ]
    
    if (nrow(dat_sensitivity) > 0) {{
        res_sensitivity <- tryCatch({{
            rma(yi, vi, data=dat_sensitivity, method="{method}")
        }}, error = function(e) {{
            logger::log_error(sprintf("Error in sensitivity analysis rma for {sensitivity_variable}={sensitivity_value}: %s", e$message))
            return(NULL)
        }})
        
        if (!is.null(res_sensitivity)) {{
            sensitivity_summary_for_json <- list(
                variable = "{sensitivity_variable}",
                limited_to = "{sensitivity_value}",
                n_included = n_category_sensitivity,
                n_total = n_total_sensitivity,
                full_estimate = as.numeric(res$b)[1],
                full_ci_lb = as.numeric(res$ci.lb)[1],
                full_ci_ub = as.numeric(res$ci.ub)[1],
                sensitivity_estimate = as.numeric(res_sensitivity$b)[1],
                sensitivity_ci_lb = as.numeric(res_sensitivity$ci.lb)[1],
                sensitivity_ci_ub = as.numeric(res_sensitivity$ci.ub)[1]
            )
            if (exists("summary_list")) {{
                summary_list$sensitivity_analysis <- sensitivity_summary_for_json
            }}
        }} else {{
            if (exists("summary_list")) {{
                summary_list$sensitivity_analysis_error <- paste("Failed to run rma for sensitivity analysis on {sensitivity_variable}={sensitivity_value}")
            }}
        }}
    }} else {{
        if (exists("summary_list")) {{
            summary_list$sensitivity_analysis_error <- paste("No data remaining after filtering for sensitivity analysis on {sensitivity_variable}={sensitivity_value}")
        }}
    }}
}} else {{
    if (exists("summary_list")) {{
        summary_list$sensitivity_analysis_skipped <- paste("Sensitivity analysis for {sensitivity_variable}={sensitivity_value} skipped: variable not found or value not in data.")
    }}
}}
"""
        }
        return templates

    def _generate_escalc_code(self, analysis_params: Dict[str, Any], data_summary: Dict[str, Any]) -> str:
        measure = analysis_params.get("measure", "RR") 
        data_cols = analysis_params.get("data_columns", {})
        
        slab_param_string = ""
        if data_cols.get("study_label_author") and data_cols.get("study_label_year"):
            slab_param_string = ", slab=slab"
        elif data_cols.get("study_label"):
            slab_param_string = ", slab=slab"

        if measure in ["OR", "RR", "RD", "PETO"]: 
            ai_col = data_cols.get("ai")
            ci_col = data_cols.get("ci")
            if not ai_col or not ci_col:
                logger.error(f"二値アウトカム ({measure}) の効果量計算に必要な基本列 (ai, ci) が不足しています。")
                return f"# Error: Missing essential columns (ai: {ai_col}, ci: {ci_col}) for binary outcome {measure}"
            bi_col = data_cols.get("bi")
            di_col = data_cols.get("di")
            n1i_col = data_cols.get("n1i")
            n2i_col = data_cols.get("n2i")
            pre_escalc_code = []
            actual_bi_col = bi_col
            if not bi_col: 
                if n1i_col and ai_col:
                    calculated_bi_col_name = f"{ai_col}_n_minus_event"
                    pre_escalc_code.append(f"dat${calculated_bi_col_name} <- dat${n1i_col} - dat${ai_col}")
                    actual_bi_col = calculated_bi_col_name
                else:
                    logger.error(f"列 'bi' がなく、'n1i' または 'ai' もないため計算できません。")
                    return f"# Error: Column 'bi' is missing and cannot be calculated from 'n1i' (present: {bool(n1i_col)}) and 'ai' (present: {bool(ai_col)}) for measure {measure}."
            actual_di_col = di_col
            if not di_col: 
                if n2i_col and ci_col:
                    calculated_di_col_name = f"{ci_col}_n_minus_event"
                    pre_escalc_code.append(f"dat${calculated_di_col_name} <- dat${n2i_col} - dat${ci_col}")
                    actual_di_col = calculated_di_col_name
                else:
                    logger.error(f"列 'di' がなく、'n2i' または 'ci' もないため計算できません。")
                    return f"# Error: Column 'di' is missing and cannot be calculated from 'n2i' (present: {bool(n2i_col)}) and 'ci' (present: {bool(ci_col)}) for measure {measure}."
            escalc_call = self._safe_format(
                self.templates["escalc_binary"],
                measure=measure, ai=ai_col, bi=actual_bi_col,
                ci=ci_col, di=actual_di_col, slab_param_string=slab_param_string
            )
            return "\n".join(pre_escalc_code) + f"\n{escalc_call.lstrip()}" if pre_escalc_code else escalc_call
        elif measure in ["SMD", "MD", "ROM"]: 
            required_cols = ["n1i", "n2i", "m1i", "m2i", "sd1i", "sd2i"]
            if not all(data_cols.get(col) for col in required_cols):
                logger.error(f"連続アウトカム ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                return "# Error: Missing columns for continuous outcome effect size calculation"
            return self._safe_format(
                self.templates["escalc_continuous"],
                measure=measure, n1i=data_cols["n1i"], n2i=data_cols["n2i"],
                m1i=data_cols["m1i"], m2i=data_cols["m2i"],
                sd1i=data_cols["sd1i"], sd2i=data_cols["sd2i"],
                slab_param_string=slab_param_string
            )
        elif measure in ["PLO", "IR", "PR"]: 
            if measure == "IR":
                required_cols = ["proportion_events", "proportion_time"]
                if not all(data_cols.get(col) for col in required_cols):
                    logger.error(f"発生率 ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                    return "# Error: Missing columns for incidence rate effect size calculation"
                return self._safe_format(
                    self.templates["escalc_proportion"],
                    measure=measure, events=data_cols['proportion_events'],
                    total=data_cols['proportion_time'], slab_param_string=slab_param_string
                )
            required_cols = ["proportion_events", "proportion_total"]
            if not all(data_cols.get(col) for col in required_cols):
                logger.error(f"割合 ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                return "# Error: Missing columns for proportion effect size calculation"
            escalc_measure = "PLO" if measure == "proportion" else measure
            return self._safe_format(
                self.templates["escalc_proportion"],
                measure=escalc_measure, events=data_cols["proportion_events"],
                total=data_cols["proportion_total"], slab_param_string=slab_param_string
            )
        elif measure == "PRE": # "yi" から "PRE" に変更 (パラメータ設定モーダルと合わせる)
            if not (data_cols.get("yi") and data_cols.get("vi")):
                logger.error("事前計算された効果量を使用するには 'yi' と 'vi' 列が必要です。")
                return "# Error: Missing 'yi' or 'vi' columns for pre-calculated effect sizes"
            return self.templates["escalc_precalculated"]
        else:
            logger.warning(f"未対応の効果量タイプ: {measure}")
            return f"# Warning: Unsupported effect size type: {measure}"

    def _generate_rma_code(self, analysis_params: Dict[str, Any]) -> str:
        method = analysis_params.get("model", "REML") # "method" から "model" に変更
        moderators = analysis_params.get("moderator_columns", [])
        mods_formula_parts = []
        if moderators:
            # モデレーターが数値型かカテゴリ型かを考慮する必要がある場合がある
            # ここでは単純に結合
            mods_formula_parts.extend(moderators)
        
        if mods_formula_parts:
            mods_formula = " + ".join(mods_formula_parts)
            return self._safe_format(
                self.templates["rma_with_mods"],
                method=method, mods_formula=mods_formula,
            )
        else:
            return self._safe_format(
                self.templates["rma_basic"], method=method,
            )

    def _generate_subgroup_code(self, analysis_params: Dict[str, Any]) -> str:
        subgroup_columns = analysis_params.get("subgroup_columns", [])
        method = analysis_params.get("model", "REML") # "method" から "model" に変更
        if not subgroup_columns:
            return ""
        
        subgroup_codes = []
        for subgroup_col in subgroup_columns:
            # サブグループテスト用のモデル (res_subgroup_test_{subgroup_col} に結果を格納)
            subgroup_test_model_code = self._safe_format(
                self.templates["rma_with_mods"], # mods を使うテンプレート
                method=method, 
                mods_formula=f"factor({subgroup_col})" # サブグループ列をfactorとして指定
            ).replace("res <-", f"res_subgroup_test_{subgroup_col} <-")
            
            # 各サブグループごとの解析結果を格納するリストを作成 (res_by_subgroup_{subgroup_col} に結果を格納)
            # splitとlapplyを使って、各サブグループレベルでrmaを実行し、結果をリストにまとめる
            subgroup_by_level_code = f"""
# Subgroup analysis for '{subgroup_col}' by levels
if ("{subgroup_col}" %in% names(dat)) {{
    dat_split_{subgroup_col} <- split(dat, dat[['{subgroup_col}']])
    res_by_subgroup_{subgroup_col} <- lapply(names(dat_split_{subgroup_col}), function(level_name) {{
        current_data_sg <- dat_split_{subgroup_col}[[level_name]]
        if (nrow(current_data_sg) > 0) {{
            tryCatch({{
                rma_result_sg <- rma(yi, vi, data=current_data_sg, method="{method}")
                # 結果にレベル名を追加して返す (後でアクセスしやすくするため)
                rma_result_sg$subgroup_level <- level_name 
                return(rma_result_sg)
            }}, error = function(e) {{
                logger::log_warn(sprintf("RMA failed for subgroup '{subgroup_col}' level '%s': %s", level_name, e$message))
                return(NULL) # エラー時はNULLを返す
            }})
        }} else {{
            return(NULL) # データがない場合はNULL
        }}
    }})
    # NULL要素をリストから除去
    res_by_subgroup_{subgroup_col} <- res_by_subgroup_{subgroup_col}[!sapply(res_by_subgroup_{subgroup_col}, is.null)]
    # リストの要素に名前を付ける (サブグループのレベル名)
    if (length(res_by_subgroup_{subgroup_col}) > 0) {{
        names(res_by_subgroup_{subgroup_col}) <- sapply(res_by_subgroup_{subgroup_col}, function(x) x$subgroup_level)
    }}
}} else {{
    res_subgroup_test_{subgroup_col} <- NULL
    res_by_subgroup_{subgroup_col} <- NULL
    logger::log_warn("Subgroup column '{subgroup_col}' not found in data for subgroup analysis.")
}}
"""
            subgroup_codes.append(f"\n# --- Subgroup analysis for '{subgroup_col}' ---\n{subgroup_test_model_code}\n{subgroup_by_level_code}")
        return "\n".join(subgroup_codes)
        
    def _generate_plot_code(self, analysis_params: Dict[str, Any], output_paths: Dict[str, str], data_summary: Dict[str, Any]) -> str:
        plot_parts = []
        # analysis_params から data_columns を取得、なければ空の辞書
        data_cols = analysis_params.get("data_columns", {})
        ai_col = data_cols.get("ai", "") # data_columns がなくてもエラーにならないように
        bi_col = data_cols.get("bi", "") 
        ci_col = data_cols.get("ci", "")
        di_col = data_cols.get("di", "")

        # 1. メインフォレストプロット
        main_forest_plot_path = output_paths.get("forest_plot_path", "forest_plot_overall.png")
        plot_parts.append(
            self._safe_format(
                self.templates["forest_plot"],
                forest_plot_path=main_forest_plot_path.replace('\\', '/'),
                measure_for_plot=analysis_params.get("measure", "RR"),
                ai_col=ai_col, bi_col=bi_col, ci_col=ci_col, di_col=di_col,
                row_h_in_placeholder=self.PLOT_ROW_H_IN,
                base_h_in_placeholder=self.PLOT_BASE_H_IN,
                plot_width_in_placeholder=self.PLOT_WIDTH_IN,
                plot_dpi_placeholder=self.PLOT_DPI,
                extra_rows_main_placeholder=self.PLOT_EXTRA_ROWS_MAIN
            )
        )
        
        # 2. サブグループごとのフォレストプロット
        subgroup_columns = analysis_params.get("subgroup_columns", [])
        if subgroup_columns and "subgroup_forest_plot_template" in self.templates:
            subgroup_plot_prefix = output_paths.get("forest_plot_subgroup_prefix", "forest_plot_subgroup")
            for sg_col in subgroup_columns:
                # サブグループ列が実際にデータに存在するか確認
                if sg_col not in data_summary.get("columns", []):
                    logger.warning(f"サブグループ列 '{sg_col}' がデータに存在しないため、サブグループプロットをスキップします。")
                    continue
                safe_sg_col_name = "".join(c if c.isalnum() else "_" for c in sg_col)
                sg_forest_plot_path = f"{subgroup_plot_prefix}_{safe_sg_col_name}.png".replace('\\', '/')
                plot_parts.append(
                    self._safe_format(
                        self.templates["subgroup_forest_plot_template"],
                        subgroup_col_name=sg_col,
                        subgroup_forest_plot_path=sg_forest_plot_path,
                        measure_for_plot=analysis_params.get("measure", "RR"),
                        ai_col=ai_col, bi_col=bi_col, ci_col=ci_col, di_col=di_col,
                        res_for_plot_model_name="res_for_plot", # メインモデルのプロット用オブジェクト名
                        row_h_in_placeholder=self.PLOT_ROW_H_IN,
                        base_h_in_placeholder=self.PLOT_BASE_H_IN,
                        plot_width_in_placeholder=self.PLOT_WIDTH_IN,
                        plot_dpi_placeholder=self.PLOT_DPI,
                        extra_rows_subgroup_placeholder=self.PLOT_EXTRA_ROWS_SUBGROUP
                    )
                )

        # 3. ファンネルプロット
        if output_paths.get("funnel_plot_path"):
            plot_parts.append(
                self._safe_format(
                    self.templates["funnel_plot"],
                    funnel_plot_path=output_paths["funnel_plot_path"].replace('\\', '/')
                )
            )
            
        # 4. バブルプロット (メタ回帰用)
        moderators = analysis_params.get("moderator_columns", [])
        if moderators and output_paths.get("bubble_plot_path_prefix"):
            bubble_plot_prefix = output_paths.get("bubble_plot_path_prefix", "bubble_plot")
            for mod_col in moderators:
                 # モデレーター列が実際にデータに存在するか確認
                if mod_col not in data_summary.get("columns", []):
                    logger.warning(f"モデレーター列 '{mod_col}' がデータに存在しないため、バブルプロットをスキップします。")
                    continue
                safe_mod_col_name = "".join(c if c.isalnum() else "_" for c in mod_col)
                bubble_plot_path_specific = f"{bubble_plot_prefix}_{safe_mod_col_name}.png".replace('\\', '/')
                plot_parts.append(
                    self._safe_format(
                        self.templates["bubble_plot"],
                        moderator_column_for_bubble=mod_col,
                        bubble_plot_path=bubble_plot_path_specific
                    )
                )
        return "\n\n".join(plot_parts)

    def _generate_save_code(self, analysis_params: Dict[str, Any], output_paths: Dict[str, str], data_summary: Dict[str, Any]) -> str:
        additional_objects_to_save = ["res_for_plot"] # res_for_plot は常に保存
        subgroup_json_str_parts = []
        
        subgroup_columns = analysis_params.get("subgroup_columns", [])
        if subgroup_columns:
            for subgroup_col in subgroup_columns:
                # サブグループ列が実際にデータに存在するか確認
                if subgroup_col not in data_summary.get("columns", []):
                    continue # スキップ
                additional_objects_to_save.append(f"res_subgroup_test_{subgroup_col}")
                additional_objects_to_save.append(f"res_by_subgroup_{subgroup_col}")
                subgroup_json_str_parts.append(f"""
    if (exists("res_subgroup_test_{subgroup_col}") && !is.null(res_subgroup_test_{subgroup_col})) {{
        summary_list$subgroup_moderation_test_{subgroup_col} <- list(
            subgroup_column = "{subgroup_col}", QM = res_subgroup_test_{subgroup_col}$QM,
            QMp = res_subgroup_test_{subgroup_col}$QMp, df = res_subgroup_test_{subgroup_col}$p -1, # df is p-1 for QM
            summary_text = paste(capture.output(print(res_subgroup_test_{subgroup_col})), collapse = "\\n")
        )
    }}
    if (exists("res_by_subgroup_{subgroup_col}") && !is.null(res_by_subgroup_{subgroup_col}) && length(res_by_subgroup_{subgroup_col}) > 0) {{
        subgroup_results_list_{subgroup_col} <- list()
        for (subgroup_name_idx in seq_along(res_by_subgroup_{subgroup_col})) {{
            current_res_sg <- res_by_subgroup_{subgroup_col}[[subgroup_name_idx]]
            subgroup_level_name <- names(res_by_subgroup_{subgroup_col})[subgroup_name_idx]
            if (!is.null(current_res_sg)) {{ # NULLチェックを追加
                subgroup_results_list_{subgroup_col}[[subgroup_level_name]] <- list(
                    k = current_res_sg$k, estimate = as.numeric(current_res_sg$b)[1], 
                    se = as.numeric(current_res_sg$se)[1], zval = as.numeric(current_res_sg$zval)[1],
                    pval = as.numeric(current_res_sg$pval)[1], ci_lb = as.numeric(current_res_sg$ci.lb)[1],
                    ci_ub = as.numeric(current_res_sg$ci.ub)[1], I2 = current_res_sg$I2, tau2 = current_res_sg$tau2,
                    summary_text = paste(capture.output(print(current_res_sg)), collapse = "\\n")
                )
            }}
        }}
        summary_list$subgroup_analyses_{subgroup_col} <- subgroup_results_list_{subgroup_col}
    }}
""")
        regression_json_str = ""
        moderators = analysis_params.get("moderator_columns", [])
        if moderators:
            # 実際にモデルに含まれるモデレーターのみを対象とする
            valid_moderators_in_code = [m for m in moderators if m in data_summary.get("columns", [])]
            if valid_moderators_in_code:
                regression_json_str = f"""
    if (exists("res") && !is.null(res$beta) && length(res$beta) > 1 && "{' + '.join(valid_moderators_in_code)}" != "") {{
        moderator_results <- list()
        if (!is.null(res$beta) && nrow(res$beta) > 1) {{ 
            for (i in 2:nrow(res$beta)) {{ 
                mod_name <- rownames(res$beta)[i]
                moderator_results[[mod_name]] <- list(
                    estimate = res$beta[i,1], se = res$se[i,1], zval = res$zval[i,1],
                    pval = res$pval[i,1], ci_lb = res$ci.lb[i,1], ci_ub = res$ci.ub[i,1]
                )
            }}
        }}
        summary_list$meta_regression_results <- list(
            moderators = moderator_results, R2 = ifelse(!is.null(res$R2), res$R2, NA), # R2が存在しない場合NA
            QM = res$QM, QMp = res$QMp, # Test of moderators
            summary_text = paste(capture.output(print(res)), collapse = "\\n")
        )
    }}
"""
        egger_json_str = ""
        if output_paths.get("funnel_plot_path"):
            egger_json_str = """
    if (exists("egger_test_res") && !is.null(egger_test_res)) {
        summary_list$egger_test <- list(
            statistic = egger_test_res$statistic,
            pval = egger_test_res$p.value,
            summary_text = paste(capture.output(print(egger_test_res)), collapse = "\\n")
        )
    } else {
        summary_list$egger_test <- list(message = "Egger's test was not performed or resulted in an error.")
    }
"""
        additional_objects_str = ""
        if additional_objects_to_save:
            unique_additional_objects = list(set(additional_objects_to_save) - set(["res"]))
            # 存在しない可能性のあるオブジェクトは除外
            valid_unique_additional_objects = [obj for obj in unique_additional_objects if obj is not None] # 簡単なNoneチェック
            if valid_unique_additional_objects:
                 additional_objects_str = ", " + ", ".join(valid_unique_additional_objects)

        generated_plots_r_list = []
        main_forest_plot_path = output_paths.get("forest_plot_path", "forest_plot_overall.png")
        main_forest_plot_path_cleaned = main_forest_plot_path.replace("\\\\", "/")
        generated_plots_r_list.append(f'list(label = "forest_plot_overall", path = "{main_forest_plot_path_cleaned}")')
        
        if subgroup_columns:
            subgroup_plot_prefix = output_paths.get("forest_plot_subgroup_prefix", "forest_plot_subgroup")
            for sg_col in subgroup_columns:
                if sg_col not in data_summary.get("columns", []): continue
                safe_sg_col_name = "".join(c if c.isalnum() else "_" for c in sg_col)
                sg_forest_plot_path = f"{subgroup_plot_prefix}_{safe_sg_col_name}.png".replace('\\\\', '/')
                generated_plots_r_list.append(f'list(label = "forest_plot_subgroup_{safe_sg_col_name}", path = "{sg_forest_plot_path}")')
        
        if output_paths.get("funnel_plot_path"):
            funnel_plot_path_cleaned = output_paths["funnel_plot_path"].replace("\\\\", "/")
            generated_plots_r_list.append(f'list(label = "funnel_plot", path = "{funnel_plot_path_cleaned}")')
        
        if moderators:
            bubble_plot_prefix = output_paths.get("bubble_plot_path_prefix", "bubble_plot")
            for mod_col in moderators:
                if mod_col not in data_summary.get("columns", []): continue
                safe_mod_col_name = "".join(c if c.isalnum() else "_" for c in mod_col)
                bubble_plot_path_specific = f"{bubble_plot_prefix}_{safe_mod_col_name}.png".replace('\\\\','/')
                generated_plots_r_list.append(f'list(label = "bubble_plot_{safe_mod_col_name}", path = "{bubble_plot_path_specific}")')
        
        generated_plots_r_code = f"summary_list$generated_plots_paths <- list({', '.join(generated_plots_r_list)})" # キー名を変更

        return self._safe_format(
            self.templates["save_results"],
            rdata_path=output_paths["rdata_path"].replace('\\', '/'),
            json_summary_path=output_paths["json_summary_path"].replace('\\', '/'),
            additional_objects_str=additional_objects_str,
            subgroup_json_update_code="\n".join(subgroup_json_str_parts),
            regression_json_update_code=regression_json_str,
            egger_json_update_code=egger_json_str,
            generated_plots_r_code=generated_plots_r_code
        )

    def generate_full_r_script(self, 
                               analysis_params: Dict[str, Any], 
                               data_summary: Dict[str, Any], # CSVの列情報などを含むサマリー
                               output_paths: Dict[str, str],
                               csv_file_path_in_script: str) -> str:
        logger.info(f"Rスクリプト生成開始。解析パラメータ: {analysis_params}")
        logger.info(f"データサマリー (列名など): {data_summary.get('columns', 'N/A')}") # data_summary全体は大きい可能性があるので一部のみログ
        logger.info(f"出力パス: {output_paths}")
        logger.info(f"スクリプト内CSVパス: {csv_file_path_in_script}")

        script_parts = [self.templates["library_load"]]
        
        # データ読み込み (パスはバックスラッシュをスラッシュに置換)
        script_parts.append(f"dat <- read.csv('{csv_file_path_in_script.replace('\\\\', '/')}')")
        
        # 研究ラベル(slab)の準備
        data_cols = analysis_params.get("data_columns", {})
        study_label_author_col = data_cols.get("study_label_author")
        study_label_year_col = data_cols.get("study_label_year")
        study_label_col = data_cols.get("study_label")
        
        slab_expression = ""
        if study_label_author_col and study_label_year_col and \
           study_label_author_col in data_summary.get("columns", []) and \
           study_label_year_col in data_summary.get("columns", []):
            slab_expression = f"paste(dat${study_label_author_col}, dat${study_label_year_col}, sep=\", \")"
        elif study_label_col and study_label_col in data_summary.get("columns", []):
            slab_expression = f"dat${study_label_col}"
        
        if slab_expression:
            script_parts.append(f"dat$slab <- {slab_expression}")
        else: # slabがない場合は、行番号をstudy labelとして使うフォールバック
            script_parts.append(f"dat$slab <- rownames(dat)")


        # 効果量計算 (escalc)
        escalc_code = self._generate_escalc_code(analysis_params, data_summary)
        script_parts.append(escalc_code)

        # メインのメタ解析モデル (プロット用、res_for_plot に格納)
        # これはモデレーターやサブグループを含まないシンプルなモデルが良い場合が多い
        plot_model_method = analysis_params.get("model", "REML") # "method" から "model" に変更
        rma_for_plot_code = self._safe_format(
            self.templates["rma_basic"], method=plot_model_method,
        ).replace("res <-", "res_for_plot <-") # 結果を res_for_plot に格納
        script_parts.append(rma_for_plot_code)

        # 詳細なメタ解析モデル (モデレーターやサブグループテスト用、res に格納)
        rma_code = self._generate_rma_code(analysis_params) # analysis_params に基づく
        script_parts.append(rma_code)

        # サブグループ解析 (res_subgroup_test_{col} と res_by_subgroup_{col} に結果格納)
        subgroup_cols = analysis_params.get("subgroup_columns", [])
        if subgroup_cols:
            # サブグループ列が実際にデータに存在するか確認
            valid_subgroup_cols = [sgc for sgc in subgroup_cols if sgc in data_summary.get("columns", [])]
            if valid_subgroup_cols:
                # analysis_params をコピーして、有効なサブグループ列のみを設定
                subgroup_analysis_params = analysis_params.copy()
                subgroup_analysis_params["subgroup_columns"] = valid_subgroup_cols
                subgroup_code = self._generate_subgroup_code(subgroup_analysis_params)
                script_parts.append(subgroup_code)
            else:
                logger.warning("指定されたサブグループ列がデータに存在しないため、サブグループ解析をスキップします。")


        # Egger's test (ファンネルプロットが要求されている場合)
        if output_paths.get("funnel_plot_path"):
            script_parts.append("egger_test_res <- tryCatch(regtest(res_for_plot), error = function(e) { logger::log_warn(sprintf(\"Egger's test failed: %s\", e$message)); return(NULL) })")


        # プロット生成
        plot_code = self._generate_plot_code(analysis_params, output_paths, data_summary)
        script_parts.append(plot_code)
        
        # 感度分析 (もしあれば)
        sensitivity_variable = analysis_params.get("sensitivity_variable")
        sensitivity_value = analysis_params.get("sensitivity_value")
        if sensitivity_variable and sensitivity_value and sensitivity_variable in data_summary.get("columns", []):
            sensitivity_code = self._safe_format(
                self.templates["sensitivity_analysis"],
                sensitivity_variable=sensitivity_variable,
                sensitivity_value=sensitivity_value,
                method=analysis_params.get("model", "REML") # "method" から "model"
            )
            script_parts.append(sensitivity_code)
        elif sensitivity_variable:
             logger.warning(f"感度分析変数 '{sensitivity_variable}' がデータに存在しないためスキップします。")


        # 結果保存
        save_code = self._generate_save_code(analysis_params, output_paths, data_summary)
        script_parts.append(save_code)
        
        full_script = "\n\n".join(filter(None, script_parts))
        logger.info(f"生成されたRスクリプト (最初の1000文字):\n{full_script[:1000]}...")
        return full_script

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    generator = RTemplateGenerator()
    test_analysis_params = {
        "measure": "OR", "model": "REML", # method -> model
        "data_columns": {
            "ai": "tpos", "bi": "tneg", "ci": "cpos", "di": "cneg",
            "study_label_author": "author", "study_label_year": "year"
        },
        "subgroup_columns": ["alloc", "gender"], 
        "moderator_columns": ["ablat", "year"]
    }
    test_data_summary = { # 実際のCSV分析結果に近い形を想定
        "columns": ["author", "year", "tpos", "tneg", "cpos", "cneg", "ablat", "alloc", "gender", "yi", "vi"],
        "shape": [13, 11] # yi, vi も含むと仮定
    }
    test_output_paths = {
        "forest_plot_path": "test_forest_overall.png",
        "forest_plot_subgroup_prefix": "test_forest_subgroup",
        "funnel_plot_path": "test_funnel.png",
        "rdata_path": "test_result.RData",
        "json_summary_path": "test_summary.json",
        "bubble_plot_path_prefix": "test_bubble"
    }
    test_csv_path = "path/to/your/data.csv" # 実際には存在するパスを指定
    
    print("--- Test Case 1: Binary Outcome with Subgroups and Moderators ---")
    r_script = generator.generate_full_r_script(
        test_analysis_params, test_data_summary, test_output_paths, test_csv_path
    )
    # print(r_script) # 全文表示は長いのでコメントアウト

    test_analysis_params_pre = {
        "measure": "PRE", "model": "DL", # yi -> PRE, method -> model
        "data_columns": { # PREの場合、escalcはyi,viを直接使うので、これらのマッピングはescalcには不要だが、
                          # 他の処理（slabなど）で使われる可能性はある
            "yi": "effect_value", "vi": "variance_value", "study_label": "study_name"
        }
        # サブグループやモデレーターがないシンプルなケース
    }
    test_data_summary_pre = {
        "columns": ["study_name", "effect_value", "variance_value", "yi", "vi"], # yi, vi も含むと仮定
        "shape": [10, 5]
    }
    simple_output_paths = {
        "forest_plot_path": "test_forest_pre.png",
        "funnel_plot_path": "test_funnel_pre.png",
        "rdata_path": "test_result_pre.RData",
        "json_summary_path": "test_summary_pre.json"
        # バブルプロットやサブグループプロットはなし
    }
    print("\n--- Test Case 2: Pre-calculated Effect Size (yi, vi) ---")
    r_script_pre = generator.generate_full_r_script(
        test_analysis_params_pre, test_data_summary_pre, simple_output_paths, test_csv_path
    )
    # print(r_script_pre)
    print("\nNote: Full R scripts are long and not printed here. Check logic if needed.")
