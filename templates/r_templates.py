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
# 修正: slabを列名参照に変更してベクトル長さ不整合を回避
dat <- escalc(measure="{measure}", ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, slab={slab_column})
""",
            "escalc_binary_no_correction": """
# 二値アウトカムの効果量計算（連続性補正なし）
# 修正: slabを列名参照に変更してベクトル長さ不整合を回避
dat <- escalc(measure="{measure}", ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, add=0, to="none", slab={slab_column})
""",
            "rma_mh": """
# Mantel-Haenszel法による解析（補正なし）
# 修正: slabを列名参照に変更してベクトル長さ不整合を回避
res <- rma.mh(ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, measure="{measure}", 
              add=0, to="none", drop00=TRUE, correct=TRUE, slab={slab_column})
""",
            "rma_mh_with_correction": """
# Mantel-Haenszel法による解析（個別効果量のみ補正、集計は補正なし）
# 修正: slabを列名参照に変更してベクトル長さ不整合を回避
res <- rma.mh(ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, measure="{measure}", 
              add=c(0.5, 0), to=c("only0", "none"), drop00=TRUE, correct=TRUE, slab={slab_column})
""",
            "main_analysis_selection": """
# 主解析手法の選択（ゼロセルがある場合はMH法、ない場合は逆分散法）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    print("ゼロセルが検出されました。主解析にMantel-Haenszel法を使用します。")
    main_analysis_method <- "MH"
    
    # 主解析：Mantel-Haenszel法（補正なし）
    # 修正: slabを列名参照に変更してベクトル長さ不整合を回避
    res <- rma.mh(ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, measure="{measure}",
                  add=0, to="none", drop00=TRUE, correct=TRUE, slab={slab_column})
    res_for_plot <- res  # プロット用にも同じ結果を使用
    
    print("主解析完了: Mantel-Haenszel法（補正なし）")
}} else {{
    print("ゼロセルは検出されませんでした。主解析に逆分散法を使用します。")
    main_analysis_method <- "IV"
    
    # 主解析：逆分散法（従来通り）
    res <- rma(dat$yi, dat$vi, data=dat, method="{method}")
    res_for_plot <- res  # プロット用にも同じ結果を使用
    
    print("主解析完了: 逆分散法")
}}
""",
            "zero_cell_analysis": """
# ゼロセル分析（NA値を適切に処理）
zero_cells_summary <- list()
zero_cells_summary$total_studies <- nrow(dat)

# NA値を除いてゼロセルを計算
valid_rows <- !is.na(dat${ai}) & !is.na(dat${bi}) & !is.na(dat${ci}) & !is.na(dat${di})
zero_cells_summary$valid_studies <- sum(valid_rows, na.rm=TRUE)

if (zero_cells_summary$valid_studies > 0) {{
    valid_dat <- dat[valid_rows, ]
    zero_cells_summary$studies_with_zero_cells <- sum((valid_dat${ai} == 0) | (valid_dat${bi} == 0) | (valid_dat${ci} == 0) | (valid_dat${di} == 0), na.rm=TRUE)
    zero_cells_summary$double_zero_studies <- sum((valid_dat${ai} == 0 & valid_dat${ci} == 0), na.rm=TRUE)
    zero_cells_summary$zero_in_treatment <- sum(valid_dat${ai} == 0, na.rm=TRUE)
    zero_cells_summary$zero_in_control <- sum(valid_dat${ci} == 0, na.rm=TRUE)
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
""",
            "or_ci_conversion": """
# OR/RRと信頼区間からlnOR/lnRRとSEへの変換
dat$yi <- log(dat$`{or_col}`)
dat$vi <- ((log(dat$`{ci_upper_col}`) - log(dat$`{ci_lower_col}`)) / (2 * 1.96))^2
# 変換後の確認
print("OR/RR to log scale conversion completed:")
print(head(dat[, c("{or_col}", "{ci_lower_col}", "{ci_upper_col}", "yi", "vi")]))
""",
            "escalc_continuous": """
# 連続アウトカムの効果量計算 (例: 標準化平均差)
dat <- escalc(measure="{measure}", n1i=`{n1i}`, n2i=`{n2i}`, m1i=`{m1i}`, m2i=`{m2i}`, sd1i=`{sd1i}`, sd2i=`{sd2i}`, data=dat{slab_param_string})
""",
            "escalc_proportion": """
# 割合の効果量計算
dat <- escalc(measure="{measure}", xi=`{events}`, ni=`{total}`, data=dat{slab_param_string})
""",
            "escalc_correlation": """
# 相関の効果量計算
dat <- escalc(measure="{measure}", ri=`{ri}`, ni=`{ni}`, data=dat{slab_param_string})
""",
             "escalc_precalculated": """
# 事前計算された効果量を使用 (yi, vi)
# この場合、escalcは不要なことが多いが、もし追加処理が必要ならここに記述
""",
            "rma_basic": """
# 基本的なメタアナリシス実行
res <- rma(yi, vi, data=dat, method="{method}")
res_for_plot <- res  # プロット用にも同じ結果を使用
""",
            "rma_with_mods": """
# モデレーターを用いたメタ回帰実行
res <- rma(yi, vi, mods = ~ {mods_formula}, data=dat, method="{method}")
""",
            "subgroup_single": """
# Subgroup analysis for '{subgroup_col}'
res_subgroup_test_{subgroup_col} <- rma(yi, vi, mods = ~ factor(`{subgroup_col}`), data=dat, method="{method}")

# 各サブグループ '{subgroup_col}' ごとの解析 (splitとlapplyを使用し、個別のrmaオブジェクトのリストを作成)
dat_split_{subgroup_col} <- split(dat, dat[['{subgroup_col}']])
res_by_subgroup_{subgroup_col} <- lapply(dat_split_{subgroup_col}, function(x) rma(yi, vi, data=x, method="{method}"))
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
        n1i_col <- "{n1i_col}"
        n2i_col <- "{n2i_col}"
        
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
        n1i_col <- "{n1i_col}"
        n2i_col <- "{n2i_col}"
        
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
        ai_col <- "{ai_col}"
        ci_col <- "{ci_col}"
        n1i_col <- "{n1i_col}"
        n2i_col <- "{n2i_col}"
        
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
    text(1, 1, paste("Error generating forest plot:\n", e$message), col="red")
    print(sprintf("Forest plot generation failed: %s", e$message))
}})
dev.off()
""",
            "subgroup_forest_plot_template": """
# サブグループ '{subgroup_col_name}' のフォレストプロット（簡略化版）

print("=== SUBGROUP FOREST PLOT START: {subgroup_col_name} ===")
print(paste("DEBUG: Starting subgroup forest plot for {subgroup_col_name}"))

# より単純な前提条件チェック
if (exists("res_by_subgroup_{safe_var_name}") && length(res_by_subgroup_{safe_var_name}) > 0) {{
    
    print("DEBUG: All prerequisites met, starting subgroup forest plot generation")
    
    # --- プロットサイズパラメータ ---
    row_h_in_sg_val <- {row_h_in_placeholder}
    base_h_in_sg_val <- {base_h_in_placeholder}
    plot_width_in_sg_val <- {plot_width_in_placeholder}
    plot_dpi_sg_val <- {plot_dpi_placeholder}
    extra_rows_sg_val <- {extra_rows_subgroup_placeholder}

    # --- サブグループごとの行位置計算 ---
    sg_level_names <- names(res_by_subgroup_{safe_var_name})
    n_sg_levels <- length(sg_level_names)
    
    print(paste("DEBUG: sg_level_names in res_by_subgroup:", paste(sg_level_names, collapse=", ")))
    
    # 元の列名に対応するサニタイズ後の列名を取得
    sanitized_sg_col_name <- names(column_mapping)[column_mapping == "{subgroup_col_name}"]
    if (length(sanitized_sg_col_name) == 0) {{
        sanitized_sg_col_name <- make.names("{subgroup_col_name}")
    }}
    
    # データをサブグループでソート
    dat_ordered <- dat[order(dat[[sanitized_sg_col_name]]), ]
    
    # 全データのサブグループ別研究数
    all_studies_per_sg <- table(dat[[sanitized_sg_col_name]])
    print(paste("DEBUG: All subgroups in data:", paste(names(all_studies_per_sg), collapse=", ")))
    print(paste("DEBUG: Studies per subgroup:", paste(all_studies_per_sg, collapse=", ")))
    
    # res_by_subgroupに含まれるサブグループの研究数のみ取得
    studies_per_sg <- all_studies_per_sg[sg_level_names]
    
    # 元データのすべてのサブグループと res_by_subgroup に含まれるサブグループを比較
    # res_by_subgroup に含まれていないサブグループが除外されたサブグループ
    all_subgroups_in_data <- unique(dat[[sanitized_sg_col_name]])
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
        text(1, 1, "All subgroups have insufficient data (n<=1)\\nfor forest plot visualization", col="red", cex=1.2)
        dev.off()
        next
    }}
    
    # 除外後のパラメータ更新
    sg_level_names <- valid_sg_names
    n_sg_levels <- length(sg_level_names)
    studies_per_sg <- studies_per_sg[sg_level_names]
    
    # 除外後のデータでdat_orderedを再作成（重要な修正）
    dat_ordered_filtered <- dat_ordered[dat_ordered[[sanitized_sg_col_name]] %in% valid_sg_names, ]
    
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
        summary_list$subgroup_exclusions[['{subgroup_col_name}']] <- excluded_info
        
        # Skip problematic global variable assignment - use summary_list only
        print("DEBUG: Skipping subgroup_exclusions global assignment, using summary_list only")
        
        # デバッグ用ログ出力
        print(paste("DEBUG: Excluded subgroups for {subgroup_col_name}:", paste(excluded_subgroups, collapse=", ")))
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
    studies_per_sg_filtered <- table(dat_ordered_filtered[[sanitized_sg_col_name]])[sg_level_names]
    
    # 修正: 安全なforループ（subscript out of bounds エラー防止）
    if (length(sg_level_names) > 0 && n_sg_levels > 0) {{
        for (i in seq_along(sg_level_names)) {{
            sg_name <- sg_level_names[i]
            
            # 修正: サブグループが存在するかチェック
            if (!(sg_name %in% names(studies_per_sg_filtered))) {{
                print(paste("WARNING: Subgroup", sg_name, "not found in filtered data, skipping"))
                next
            }}
            
            n_studies_sg <- studies_per_sg_filtered[sg_name]
            
            # 修正: 研究数が0以下の場合のチェック
            if (is.na(n_studies_sg) || n_studies_sg <= 0) {{
                print(paste("WARNING: Subgroup", sg_name, "has no studies, skipping"))
                next
            }}
            
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
    }} else {{
        print("WARNING: No valid subgroups found for row position calculation")
    }}
    
    # 修正: 全ての研究の行位置を統合（安全な処理）
    if (length(rows_list) > 0 && length(sg_level_names) > 0) {{
        all_study_rows <- unlist(rows_list[sg_level_names])
        
        # 修正: 空の場合のフォールバック
        if (length(all_study_rows) == 0) {{
            print("WARNING: No study rows calculated, using default positions")
            all_study_rows <- seq_len(nrow(dat_ordered_filtered))
        }}
    }} else {{
        print("WARNING: No valid rows_list, using sequential positions")
        all_study_rows <- seq_len(nrow(dat_ordered_filtered))
    }}
    
    # 行位置は後でres_for_plot_filteredに合わせて調整される
    
    # ylimを設定 (十分な空間を確保)
    # 修正: subtotal_rowsが空の場合の対処
    if (length(subtotal_rows) > 0 && length(all_study_rows) > 0) {{
        ylim_bottom <- min(subtotal_rows) - 3
        ylim_top <- max(all_study_rows) + 3
    }} else {{
        print("WARNING: Cannot calculate ylim properly, using defaults")
        ylim_bottom <- 1
        ylim_top <- nrow(dat_ordered_filtered) + 5
    }}
    
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
            n1i_col_main <- "{n1i_col}"
            n2i_col_main <- "{n2i_col}"
            
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
            n1i_col_main <- "{n1i_col}"
            n2i_col_main <- "{n2i_col}"
            
            if (n1i_col_main != "" && n2i_col_main != "" && all(c(n1i_col_main, n2i_col_main) %in% names(dat))) {{
                ilab_data_main <- cbind(dat_ordered_filtered[[n1i_col_main]], dat_ordered_filtered[[n2i_col_main]])
                ilab_xpos_main <- c(-8.5, -5.5)
                ilab_lab_main <- c("N", "N")
            }}
        }}
        
        # res_for_plotをフィルタリング（除外されたサブグループのデータを削除）
        print("DEBUG: Filtering res_for_plot for subgroup forest plot")
        print(paste("DEBUG: Original res_for_plot data rows:", nrow({res_for_plot_model_name}$data)))
        print(paste("DEBUG: Filtered data rows:", nrow(dat_ordered_filtered)))
        
        # 修正: n=1のサブグループを持つ研究を特定して除外
        # まず、元データでどの研究が除外されたかを確認
        excluded_studies <- setdiff(dat$Study, dat_ordered_filtered$Study)
        if (length(excluded_studies) > 0) {{
            print(paste("DEBUG: Studies excluded due to n=1 subgroups:", paste(excluded_studies, collapse=", ")))
        }}
        
        # フィルタ済みデータのインデックスを取得（Study列で照合）
        if ("Study" %in% names({res_for_plot_model_name}$data)) {{
            # 修正: dat_ordered_filteredに存在する研究のみを選択
            filtered_indices <- which({res_for_plot_model_name}$data$Study %in% dat_ordered_filtered$Study)
            print(paste("DEBUG: Matching studies found:", length(filtered_indices)))
        }} else {{
            # Study列がない場合は、サブグループ列で直接フィルタリング
            # n=1のサブグループを除外
            valid_subgroups <- names(table(dat[['{subgroup_col_name}']])[table(dat[['{subgroup_col_name}']]) > 1])
            filtered_indices <- which({res_for_plot_model_name}$data[['{subgroup_col_name}']] %in% valid_subgroups)
            print(paste("DEBUG: Valid subgroups:", paste(valid_subgroups, collapse=", ")))
        }}
        
        print(paste("DEBUG: Filtered indices length:", length(filtered_indices)))
        print(paste("DEBUG: dat_ordered_filtered rows:", nrow(dat_ordered_filtered)))
        
        # 修正: インデックス範囲の安全性チェック（subscript out of bounds エラー防止）
        max_index <- length({res_for_plot_model_name}$yi)
        invalid_indices <- filtered_indices[filtered_indices <= 0 | filtered_indices > max_index]
        if (length(invalid_indices) > 0) {{
            print(paste("WARNING: Invalid indices detected:", paste(invalid_indices, collapse=", ")))
            print(paste("WARNING: Valid index range: 1 to", max_index))
            filtered_indices <- filtered_indices[filtered_indices > 0 & filtered_indices <= max_index]
        }}
        
        # インデックスの長さがdat_ordered_filteredと一致することを確認
        if (length(filtered_indices) != nrow(dat_ordered_filtered)) {{
            print("ERROR: Index length mismatch after validation, using sequential indices")
            print(paste("DEBUG: Expected:", nrow(dat_ordered_filtered), "Got:", length(filtered_indices)))
            filtered_indices <- seq_len(min(nrow(dat_ordered_filtered), max_index))
        }}
        
        # res_for_plotのコピーを作成し、フィルタ済みデータのみを含むようにする
        res_for_plot_filtered <- {res_for_plot_model_name}
        
        # 効果量と分散をフィルタリング
        res_for_plot_filtered$yi <- {res_for_plot_model_name}$yi[filtered_indices]
        res_for_plot_filtered$vi <- {res_for_plot_model_name}$vi[filtered_indices]
        res_for_plot_filtered$se <- {res_for_plot_model_name}$se[filtered_indices]
        
        # その他の要素もフィルタリング（存在する場合）
        if (!is.null({res_for_plot_model_name}$ni)) {{
            res_for_plot_filtered$ni <- {res_for_plot_model_name}$ni[filtered_indices]
        }}
        if (!is.null({res_for_plot_model_name}$weights)) {{
            res_for_plot_filtered$weights <- {res_for_plot_model_name}$weights[filtered_indices]
        }}
        
        # slabもフィルタリング（重要：整合性を保つ）
        if (!is.null({res_for_plot_model_name}$slab)) {{
            res_for_plot_filtered$slab <- {res_for_plot_model_name}$slab[filtered_indices]
        }}
        
        # データ行数を更新
        res_for_plot_filtered$k <- length(filtered_indices)
        
        # データフレームもフィルタリング
        res_for_plot_filtered$data <- {res_for_plot_model_name}$data[filtered_indices, ]
        
        # 修正: ilab_data_main を res_for_plot_filtered の順序に完全に合わせて再構築
        if (!is.null(ilab_data_main)) {{
            print(paste("DEBUG: Original ilab_data_main rows:", nrow(ilab_data_main)))
            print(paste("DEBUG: res_for_plot_filtered k:", res_for_plot_filtered$k))
            print(paste("DEBUG: dat_ordered_filtered rows:", nrow(dat_ordered_filtered)))
            
            # サイズまたは順序の不一致を確実に解決するため、ilab_data_mainを完全に再構築
            if (nrow(ilab_data_main) != res_for_plot_filtered$k || 
                !identical(rownames(ilab_data_main), rownames(res_for_plot_filtered$data))) {{
                
                print("NOTICE: Rebuilding ilab_data_main to match res_for_plot_filtered exactly")
                
                # res_for_plot_filtered$data から直接 Study 順序を取得
                if ("Study" %in% names(res_for_plot_filtered$data)) {{
                    target_studies <- res_for_plot_filtered$data$Study
                    print(paste("DEBUG: Target study order (first 3):", paste(head(target_studies, 3), collapse=", ")))
                    
                    # dat で target_studies の順序に合わせてデータを抽出
                    # 注意: dat_ordered_filtered ではなく dat を使用（完全なデータセット）
                    reordered_data <- dat[match(target_studies, dat$Study), ]
                    
                    # NA行をチェック（該当する研究が見つからない場合）
                    if (any(is.na(reordered_data$Study))) {{
                        print("ERROR: Some target studies not found in original data")
                        print(paste("Missing studies:", paste(target_studies[is.na(match(target_studies, dat$Study))], collapse=", ")))
                        ilab_data_main <- NULL
                        ilab_xpos_main <- NULL
                        ilab_lab_main <- NULL
                    }} else {{
                        # 正常ケース: ilab_data_main を再構築
                        if (current_measure %in% c("OR", "RR", "RD", "PETO")) {{
                            ai_col_rebuild <- "{ai_col}"
                            ci_col_rebuild <- "{ci_col}"
                            n1i_col_rebuild <- "{n1i_col}"
                            n2i_col_rebuild <- "{n2i_col}"
                            
                            if (ai_col_rebuild != "" && ci_col_rebuild != "" && n1i_col_rebuild != "" && n2i_col_rebuild != "" &&
                                all(c(ai_col_rebuild, ci_col_rebuild, n1i_col_rebuild, n2i_col_rebuild) %in% names(reordered_data))) {{
                                treatment_display_rebuild <- paste(reordered_data[[ai_col_rebuild]], "/", reordered_data[[n1i_col_rebuild]], sep="")
                                control_display_rebuild <- paste(reordered_data[[ci_col_rebuild]], "/", reordered_data[[n2i_col_rebuild]], sep="")
                                ilab_data_main <- cbind(treatment_display_rebuild, control_display_rebuild)
                                print("SUCCESS: Rebuilt ilab_data_main with Events/Total format")
                            }} else if (ai_col_rebuild != "" && ci_col_rebuild != "" && all(c(ai_col_rebuild, ci_col_rebuild) %in% names(reordered_data))) {{
                                ilab_data_main <- cbind(reordered_data[[ai_col_rebuild]], reordered_data[[ci_col_rebuild]])
                                print("SUCCESS: Rebuilt ilab_data_main with Events format")
                            }} else {{
                                print("ERROR: Required columns for ilab rebuild not found")
                                ilab_data_main <- NULL
                                ilab_xpos_main <- NULL
                                ilab_lab_main <- NULL
                            }}
                        }} else if (current_measure %in% c("SMD", "MD", "ROM")) {{
                            n1i_col_rebuild <- "{n1i_col}"
                            n2i_col_rebuild <- "{n2i_col}"
                            
                            if (n1i_col_rebuild != "" && n2i_col_rebuild != "" && all(c(n1i_col_rebuild, n2i_col_rebuild) %in% names(reordered_data))) {{
                                ilab_data_main <- cbind(reordered_data[[n1i_col_rebuild]], reordered_data[[n2i_col_rebuild]])
                                print("SUCCESS: Rebuilt ilab_data_main for continuous outcomes")
                            }} else {{
                                print("ERROR: Required columns for continuous ilab rebuild not found")
                                ilab_data_main <- NULL
                                ilab_xpos_main <- NULL
                                ilab_lab_main <- NULL
                            }}
                        }}
                        
                        if (!is.null(ilab_data_main)) {{
                            print(paste("SUCCESS: ilab_data_main rebuilt with", nrow(ilab_data_main), "rows matching res_for_plot_filtered"))
                        }}
                    }}
                }} else {{
                    print("ERROR: Study column not found in res_for_plot_filtered$data")
                    ilab_data_main <- NULL
                    ilab_xpos_main <- NULL
                    ilab_lab_main <- NULL
                }}
            }} else {{
                print("DEBUG: ilab_data_main size and order already match res_for_plot_filtered")
            }}
            
            # 最終検証: サイズが完全に一致することを確認
            if (!is.null(ilab_data_main)) {{
                if (nrow(ilab_data_main) == res_for_plot_filtered$k) {{
                    print("FINAL CHECK PASSED: ilab_data_main size matches res_for_plot_filtered")
                }} else {{
                    print(paste("FINAL CHECK FAILED: Size mismatch persists -", nrow(ilab_data_main), "vs", res_for_plot_filtered$k))
                    print("Disabling ilab to prevent forest plot error")
                    ilab_data_main <- NULL
                    ilab_xpos_main <- NULL  
                    ilab_lab_main <- NULL
                }}
            }}
        }}
        
        print(paste("DEBUG: res_for_plot_filtered k:", res_for_plot_filtered$k))
        print(paste("DEBUG: res_for_plot_filtered data rows:", nrow(res_for_plot_filtered$data)))
        print(paste("DEBUG: dat_ordered_filtered rows:", nrow(dat_ordered_filtered)))
        print(paste("DEBUG: slab length in filtered data:", length(res_for_plot_filtered$slab)))
        
        # 修正: subset引数は使用せず、フィルタ済みデータを直接使用
        # forest()関数はsubsetパラメータをサポートしていないため
        print("DEBUG: Using pre-filtered data for forest plot - no subset parameter needed")
        
        # 修正: rows引数を完全にフィルタ済みデータに合わせて再計算
        print(paste("DEBUG: Pre-adjustment - all_study_rows length:", length(all_study_rows)))
        print(paste("DEBUG: Pre-adjustment - filtered_indices length:", length(filtered_indices)))
        print(paste("DEBUG: Pre-adjustment - res_for_plot_filtered k:", res_for_plot_filtered$k))
        
        # 完全な rows 再計算: サブグループポジションをフィルタ済みデータサイズで再構築
        if (length(all_study_rows) != res_for_plot_filtered$k) {{
            print("NOTICE: Completely rebuilding row positions for filtered data")
            
            # フィルタ済みデータサイズに基づく新しい行位置計算
            total_filtered_studies <- res_for_plot_filtered$k
            
            # サブグループ構造を維持した行位置再計算
            if (length(sg_level_names) > 0 && length(subtotal_rows) > 0) {{
                print("DEBUG: Rebuilding with subgroup structure preserved")
                
                # 各サブグループの研究数を再計算（フィルタ済みデータ基準）
                sg_studies_filtered <- table(res_for_plot_filtered$data[['{subgroup_col_name}']])
                
                # 行位置を下から上に再配置
                current_row_rebuild <- total_filtered_studies + length(sg_level_names) * 2
                all_study_rows_rebuild <- c()
                subtotal_rows_rebuild <- c()
                
                for (sg_name_rebuild in names(sg_studies_filtered)) {{
                    if (sg_name_rebuild %in% sg_level_names) {{
                        n_studies_rebuild <- sg_studies_filtered[sg_name_rebuild]
                        
                        # このサブグループの研究行位置
                        study_rows_rebuild <- seq(current_row_rebuild - n_studies_rebuild + 1, current_row_rebuild)
                        all_study_rows_rebuild <- c(all_study_rows_rebuild, study_rows_rebuild)
                        
                        # サブグループサマリー行位置
                        subtotal_row_rebuild <- current_row_rebuild - n_studies_rebuild - 1
                        subtotal_rows_rebuild <- c(subtotal_rows_rebuild, subtotal_row_rebuild)
                        names(subtotal_rows_rebuild)[length(subtotal_rows_rebuild)] <- sg_name_rebuild
                        
                        # 次のサブグループ用位置更新
                        current_row_rebuild <- current_row_rebuild - n_studies_rebuild - 2
                    }}
                }}
                
                # 再構築された位置を使用
                all_study_rows <- all_study_rows_rebuild
                subtotal_rows <- subtotal_rows_rebuild
                
                print(paste("DEBUG: Rebuilt all_study_rows length:", length(all_study_rows)))
                print(paste("DEBUG: Rebuilt subtotal_rows length:", length(subtotal_rows)))
                
            }} else {{
                print("DEBUG: Simple sequential row positioning")
                # サブグループなし または subtotal_rows が空の場合、単純な連続配置
                all_study_rows <- seq(1, total_filtered_studies)
            }}
            
            # ylim再計算
            if (length(all_study_rows) > 0) {{
                if (length(subtotal_rows) > 0) {{
                    ylim_bottom <- min(subtotal_rows) - 3
                }} else {{
                    ylim_bottom <- min(all_study_rows) - 3
                }}
                ylim_top <- max(all_study_rows) + 5
            }} else {{
                # フォールバック
                ylim_bottom <- 1
                ylim_top <- total_filtered_studies + 5
                all_study_rows <- seq(1, total_filtered_studies)
            }}
            
            print(paste("DEBUG: Final all_study_rows length:", length(all_study_rows)))
            print(paste("DEBUG: Final ylim: bottom =", ylim_bottom, ", top =", ylim_top))
        }} else {{
            print("DEBUG: Row positions already match filtered data, no adjustment needed")
        }}
        
        # 最終検証: all_study_rows と res_for_plot_filtered のサイズ一致確認
        if (length(all_study_rows) != res_for_plot_filtered$k) {{
            print(paste("ERROR: Final row count mismatch:", length(all_study_rows), "vs", res_for_plot_filtered$k))
            print("FALLBACK: Using automatic row positioning (rows = NULL)")
            all_study_rows <- NULL  # NULL にして forest() の自動計算に任せる
        }} else {{
            print("SUCCESS: Row positions perfectly match filtered data size")
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
        
        # 修正: forest()呼び出し前の最終ilab安全性チェック
        if (!is.null(ilab_data_main)) {{
            # 最終的なサイズ整合性確認
            if (nrow(ilab_data_main) == res_for_plot_filtered$k) {{
                print("DEBUG: Final ilab validation passed, adding to forest plot")
                forest_sg_args$ilab <- ilab_data_main
                forest_sg_args$ilab.xpos <- ilab_xpos_main
                forest_sg_args$ilab.lab <- ilab_lab_main
            }} else {{
                print(paste("ERROR: Last-minute ilab size mismatch detected in forest call"))
                print(paste("  ilab rows:", nrow(ilab_data_main), "vs res_for_plot k:", res_for_plot_filtered$k))
                print("  Skipping ilab to prevent forest plot error")
                # ilab を無効化して forest plot を保護
            }}
        }} else {{
            print("DEBUG: ilab_data_main is NULL, forest plot will not include ilab columns")
        }}
        
        # 修正: 詳細なエラーログ付きでforest()を実行
        print("DEBUG: About to call forest() with following arguments:")
        print(paste("  - x (data) size:", res_for_plot_filtered$k))
        print(paste("  - rows argument:", if(is.null(forest_sg_args$rows)) "NULL (auto)" else paste("length =", length(forest_sg_args$rows))))
        print(paste("  - ilab argument:", if(is.null(forest_sg_args$ilab)) "NULL" else paste("size =", nrow(forest_sg_args$ilab))))
        print(paste("  - ylim:", paste(forest_sg_args$ylim, collapse=" to ")))
        
        tryCatch({{
            do.call(forest, forest_sg_args)
            print("SUCCESS: Forest plot generated successfully")
        }}, error = function(e) {{
            print("ERROR: Forest plot generation failed")
            print(paste("Error message:", e$message))
            
            # 詳細なサイズ情報をログ出力
            print("=== FOREST PLOT ERROR DIAGNOSIS ===")
            print(paste("res_for_plot_filtered$k:", res_for_plot_filtered$k))
            print(paste("length(res_for_plot_filtered$yi):", length(res_for_plot_filtered$yi)))
            print(paste("length(res_for_plot_filtered$vi):", length(res_for_plot_filtered$vi)))
            if (!is.null(res_for_plot_filtered$weights)) {{
                print(paste("length(res_for_plot_filtered$weights):", length(res_for_plot_filtered$weights)))
            }}
            if (!is.null(res_for_plot_filtered$slab)) {{
                print(paste("length(res_for_plot_filtered$slab):", length(res_for_plot_filtered$slab)))
            }}
            print(paste("nrow(res_for_plot_filtered$data):", nrow(res_for_plot_filtered$data)))
            if (!is.null(forest_sg_args$rows)) {{
                print(paste("length(forest_sg_args$rows):", length(forest_sg_args$rows)))
                print(paste("forest_sg_args$rows values:", paste(head(forest_sg_args$rows, 5), collapse=", "), "..."))
            }}
            if (!is.null(forest_sg_args$ilab)) {{
                print(paste("nrow(forest_sg_args$ilab):", nrow(forest_sg_args$ilab)))
            }}
            print("=== END DIAGNOSIS ===")
            
            # フォールバック: 簡易版プロットを試行
            print("ATTEMPTING FALLBACK: Simple forest plot without complex arguments")
            tryCatch({{
                forest(res_for_plot_filtered, 
                       ylim = forest_sg_args$ylim,
                       xlim = forest_sg_args$xlim,
                       header = "Subgroup Forest Plot (Fallback Mode)",
                       cex = 0.75)
                print("SUCCESS: Fallback forest plot generated")
            }}, error = function(e2) {{
                print(paste("FALLBACK ALSO FAILED:", e2$message))
                # 最終フォールバック: エラープロット
                plot(1, type="n", main="Forest Plot Error", xlab="", ylab="")
                text(1, 1, paste("Forest plot generation failed:\n", e$message), col="red", cex=0.8)
            }})
        }})
        
        # Treatment/Control ヘッダーの追加
        if (!is.null(ilab_data_main) && length(ilab_xpos_main) == 2) {{
             text(c(-8.5,-5.5), ylim_top - 1, c("Treatment", "Control"), font=2, cex=0.75)
        }}
        
        # サブグループラベルとサマリーポリゴンを追加
        # 修正: 安全なforループ境界チェック（subscript out of bounds エラー防止）
        if (length(sg_level_names) > 0 && n_sg_levels > 0) {{
            for (i in seq_along(sg_level_names)) {{
                sg_name <- sg_level_names[i]
                
                # 修正: 配列アクセス前の存在確認
                if (!(sg_name %in% names(res_by_subgroup_{subgroup_col_name}))) {{
                    print(paste("WARNING: Subgroup", sg_name, "not found in results, skipping"))
                    next
                }}
                if (!(sg_name %in% names(subtotal_rows))) {{
                    print(paste("WARNING: Subgroup", sg_name, "not found in subtotal_rows, skipping"))
                    next
                }}
                if (!(sg_name %in% names(rows_list))) {{
                    print(paste("WARNING: Subgroup", sg_name, "not found in rows_list, skipping"))
                    next
                }}
                
                res_sg_obj <- res_by_subgroup_{subgroup_col_name}[[sg_name]]
                subtotal_row <- subtotal_rows[sg_name]
                
                if (!is.null(res_sg_obj) && length(rows_list[[sg_name]]) > 0) {{
                # サブグループ名をラベルとして追加
                text(-16, max(rows_list[[sg_name]]) + 0.5, 
                     paste0(sg_name, " (k=", res_sg_obj$k, ")"), 
                     pos=4, font=4, cex=0.75)
                
                # サブグループの合計行を追加（二値アウトカムの場合のみ）
                if (current_measure %in% c("OR", "RR", "RD", "PETO") && !is.null(ilab_data_main)) {{
                    ai_col_sg <- "{ai_col}"
                    ci_col_sg <- "{ci_col}"
                    n1i_col_sg <- "{n1i_col}"
                    n2i_col_sg <- "{n2i_col}"
                    
                    if (ai_col_sg != "" && ci_col_sg != "" && n1i_col_sg != "" && n2i_col_sg != "" &&
                        all(c(ai_col_sg, ci_col_sg, n1i_col_sg, n2i_col_sg) %in% names(dat))) {{
                        
                        # このサブグループのデータのみを抽出（除外後のデータから）
                        sg_data <- dat_ordered_filtered[dat_ordered_filtered[[sanitized_sg_col_name]] == sg_name, ]
                        
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
                    n1i_col_sg <- "{n1i_col}"
                    n2i_col_sg <- "{n2i_col}"
                    
                    if (n1i_col_sg != "" && n2i_col_sg != "" && all(c(n1i_col_sg, n2i_col_sg) %in% names(dat))) {{
                        sg_data <- dat_ordered_filtered[dat_ordered_filtered[[sanitized_sg_col_name]] == sg_name, ]
                        
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
        }} else {{
            print("WARNING: No valid subgroups for polygon addition, skipping subgroup summaries")
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
        test_res_sg <- res_subgroup_test_{safe_var_name}
        text(-16, ylim_bottom + 0.5, pos=4, cex=0.75,
             sprintf("Test for Subgroup Differences (Q_M = %.2f, df = %d, p = %.3f)",
                    test_res_sg$QM, test_res_sg$p - 1, test_res_sg$QMp))
        
    }}, error = function(e) {{
        plot(1, type="n", main="Subgroup Forest Plot Error ({subgroup_col_name})", xlab="", ylab="")
        text(1, 1, paste("Error generating subgroup forest plot for {subgroup_col_name}:\n", e$message), col="red")
        print(sprintf("Subgroup forest plot generation failed for {subgroup_col_name}: %s", e$message))
    }})
    dev.off()
}} else {{
    print("DEBUG: Prerequisites not met for subgroup forest plot generation")
    print("DEBUG: Skipping subgroup forest plot for {subgroup_col_name}")
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
    print(sprintf("Funnel plot generation failed: %s", e$message))
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
           any(grepl(paste0("^factor\\\\(", actual_moderator_name_in_model, "\\\\)"), rownames(res$beta)[-1], fixed = FALSE)) ){{
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
           print(sprintf("Bubble plot generation failed for {moderator_column_for_bubble}: %s", e$message))
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
    
    # ゼロセル情報を追加（存在する場合）
    if (exists("zero_cells_summary") && !is.null(zero_cells_summary)) {
        summary_list$zero_cells_summary <- zero_cells_summary
        print("Zero cell summary added to JSON output")
    }

}, error = function(e_sum) {
    summary_list$error_in_summary_generation <- paste("Error creating parts of summary:", e_sum$message)
    print(sprintf("Error creating parts of summary_list: %s", e_sum$message))
})

{generated_plots_r_code}

# Note: Subgroup exclusions are already saved in summary_list during forest plot generation
print("DEBUG: Subgroup exclusions stored in summary_list during processing")

# main_analysis_methodをトップレベルに移動（ゼロセル対応から）
if (exists("zero_cells_summary") && !is.null(zero_cells_summary$studies_with_zero_cells) && 
    !is.na(zero_cells_summary$studies_with_zero_cells) && zero_cells_summary$studies_with_zero_cells > 0) {{
    summary_list$main_analysis_method <- "Mantel-Haenszel (no correction)"
}} else {{
    summary_list$main_analysis_method <- "Inverse Variance (standard)"
}}

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
    print(sprintf("Error saving summary_list as JSON: %s", e_json$message))
})

tryCatch({
    save(res{additional_objects_str}, file='{rdata_path}') 
    print(paste("RData saved to:", '{rdata_path}'))
}, error = function(e_rdata) {
    print(paste("Error saving RData:", e_rdata$message))
    print(sprintf("Error saving RData: %s", e_rdata$message))
})
""",
            "sensitivity_analysis": """
# 感度分析: {sensitivity_variable} = {sensitivity_value} に限定
if (exists("dat") && !is.null(dat) && "{sensitivity_variable}" %in% names(dat) && "{sensitivity_value}" %in% dat$`{sensitivity_variable}`) {{
    n_total_sensitivity <- nrow(dat)
    n_category_sensitivity <- sum(dat$`{sensitivity_variable}` == "{sensitivity_value}")
    dat_sensitivity <- dat[dat$`{sensitivity_variable}` == "{sensitivity_value}", ]
    
    if (nrow(dat_sensitivity) > 0) {{
        res_sensitivity <- tryCatch({{
            rma(`yi`, `vi`, data=dat_sensitivity, method="{method}")
        }}, error = function(e) {{
            print(sprintf("Error in sensitivity analysis rma for {sensitivity_variable}={sensitivity_value}: %s", e$message))
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
""",
            "zero_cell_sensitivity": """
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
        res_iv_corrected <- rma(`yi`, `vi`, data=dat, method="{method}")
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
        res_mh_corr <- rma.mh(ai=`{ai}`, bi=`{bi}`, ci=`{ci}`, di=`{di}`, data=dat, 
                             measure="{measure}", add=c(0.5, 0), to=c("only0", "none"), drop00=TRUE)
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
    print("\\n=== 主解析とゼロセル対応感度解析の結果 ===")
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
                         analysis_type, result$method, "{measure}", 
                         if("{measure}" %in% c("OR", "RR")) exp(result$estimate) else result$estimate,
                         if("{measure}" %in% c("OR", "RR")) exp(result$ci_lb) else result$ci_lb,
                         if("{measure}" %in% c("OR", "RR")) exp(result$ci_ub) else result$ci_ub,
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
"""
        }
        return templates

    def _generate_escalc_code(self, analysis_params: Dict[str, Any], data_summary: Dict[str, Any]) -> str:
        measure = analysis_params.get("measure", "RR") 
        data_cols = analysis_params.get("data_columns", {})
        data_format = analysis_params.get("data_format", "")
        detected_columns = analysis_params.get("detected_columns", {})
        
        slab_param_string = ""
        if data_cols.get("study_label_author") and data_cols.get("study_label_year"):
            slab_param_string = ", slab=slab"
        elif data_cols.get("study_label"):
            slab_param_string = ", slab=slab"

        # OR/RR + CI形式の場合の処理
        if data_format in ["or_ci", "rr_ci"] and detected_columns:
            or_col = detected_columns.get("or") or detected_columns.get("rr")
            ci_lower_col = detected_columns.get("ci_lower") or detected_columns.get("ci_low") or detected_columns.get("lower_ci")
            ci_upper_col = detected_columns.get("ci_upper") or detected_columns.get("ci_high") or detected_columns.get("upper_ci")
            
            if or_col and ci_lower_col and ci_upper_col:
                return self._safe_format(
                    self.templates["or_ci_conversion"],
                    or_col=or_col,
                    ci_lower_col=ci_lower_col,
                    ci_upper_col=ci_upper_col
                )
            else:
                logger.warning(f"OR/CI形式が検出されましたが、必要な列が見つかりません: or={or_col}, ci_lower={ci_lower_col}, ci_upper={ci_upper_col}")

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
                    # カラム名からスペースや特殊文字を除去して安全な名前を作成
                    safe_ai_col_name = "".join(c if c.isalnum() or c == "_" else "_" for c in ai_col)
                    calculated_bi_col_name = f"{safe_ai_col_name}_n_minus_event"
                    pre_escalc_code.append(f"dat${calculated_bi_col_name} <- dat${n1i_col} - dat${ai_col}")
                    actual_bi_col = calculated_bi_col_name
                else:
                    logger.error(f"列 'bi' がなく、'n1i' または 'ai' もないため計算できません。")
                    return f"# Error: Column 'bi' is missing and cannot be calculated from 'n1i' (present: {bool(n1i_col)}) and 'ai' (present: {bool(ai_col)}) for measure {measure}."
            actual_di_col = di_col
            if not di_col: 
                if n2i_col and ci_col:
                    # カラム名からスペースや特殊文字を除去して安全な名前を作成
                    safe_ci_col_name = "".join(c if c.isalnum() or c == "_" else "_" for c in ci_col)
                    calculated_di_col_name = f"{safe_ci_col_name}_n_minus_event"
                    pre_escalc_code.append(f"dat${calculated_di_col_name} <- dat${n2i_col} - dat${ci_col}")
                    actual_di_col = calculated_di_col_name
                else:
                    logger.error(f"列 'di' がなく、'n2i' または 'ci' もないため計算できません。")
                    return f"# Error: Column 'di' is missing and cannot be calculated from 'n2i' (present: {bool(n2i_col)}) and 'ci' (present: {bool(ci_col)}) for measure {measure}."
            # ゼロセル分析を追加
            zero_cell_analysis_code = self._safe_format(
                self.templates["zero_cell_analysis"],
                ai=ai_col, bi=actual_bi_col, ci=ci_col, di=actual_di_col
            )
            
            escalc_call = self._safe_format(
                self.templates["escalc_binary"],
                measure=measure, ai=ai_col, bi=actual_bi_col,
                ci=ci_col, di=actual_di_col, slab_column="slab"
            )
            
            # 主解析手法の選択（ゼロセルがある場合はMH法を優先）
            main_analysis_code = self._safe_format(
                self.templates["main_analysis_selection"],
                ai=ai_col, bi=actual_bi_col, ci=ci_col, di=actual_di_col,
                measure=measure, method=analysis_params.get("model", "REML"),
                slab_column="slab"
            )
            
            # ゼロセル対応の感度解析を追加
            sensitivity_code = self._safe_format(
                self.templates["zero_cell_sensitivity"],
                ai=ai_col, bi=actual_bi_col, ci=ci_col, di=actual_di_col,
                measure=measure, method=analysis_params.get("model", "REML")
            )
            
            # 組み合わせて返す
            all_code_parts = pre_escalc_code + [zero_cell_analysis_code, escalc_call, main_analysis_code, sensitivity_code]
            return "\n\n".join(filter(None, all_code_parts))
        elif measure in ["SMD", "MD", "ROM"]: 
            required_cols = ["n1i", "n2i", "m1i", "m2i", "sd1i", "sd2i"]
            if not all(data_cols.get(col) for col in required_cols):
                logger.error(f"連続アウトカム ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                return "# Error: Missing columns for continuous outcome effect size calculation"
            
            # escalc実行 + 主解析の組み合わせ
            escalc_code = self._safe_format(
                self.templates["escalc_continuous"],
                measure=measure, n1i=data_cols["n1i"], n2i=data_cols["n2i"],
                m1i=data_cols["m1i"], m2i=data_cols["m2i"],
                sd1i=data_cols["sd1i"], sd2i=data_cols["sd2i"],
                slab_param_string=slab_param_string
            )
            main_analysis_code = self._safe_format(
                self.templates["rma_basic"],
                method=analysis_params.get("model", "REML")
            )
            return escalc_code + "\n\n" + main_analysis_code
        elif measure in ["PLO", "IR", "PR", "PAS", "PFT", "PRAW", "IRLN", "IRS", "IRFT"]: 
            if measure in ["IR", "IRLN", "IRS", "IRFT"]:
                required_cols = ["proportion_events", "proportion_time"]
                if not all(data_cols.get(col) for col in required_cols):
                    logger.error(f"発生率 ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                    return "# Error: Missing columns for incidence rate effect size calculation"
                escalc_code = self._safe_format(
                    self.templates["escalc_proportion"],
                    measure=measure, events=data_cols['proportion_events'],
                    total=data_cols['proportion_time'], slab_param_string=slab_param_string
                )
                main_analysis_code = self._safe_format(
                    self.templates["rma_basic"],
                    method=analysis_params.get("model", "REML")
                )
                return escalc_code + "\n\n" + main_analysis_code
            required_cols = ["proportion_events", "proportion_total"]
            if not all(data_cols.get(col) for col in required_cols):
                logger.error(f"割合 ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                return "# Error: Missing columns for proportion effect size calculation"
            escalc_measure = "PLO" if measure == "proportion" else measure
            escalc_code = self._safe_format(
                self.templates["escalc_proportion"],
                measure=escalc_measure, events=data_cols["proportion_events"],
                total=data_cols["proportion_total"], slab_param_string=slab_param_string
            )
            main_analysis_code = self._safe_format(
                self.templates["rma_basic"],
                method=analysis_params.get("model", "REML")
            )
            return escalc_code + "\n\n" + main_analysis_code
        elif measure == "COR": # 相関係数
            required_cols = ["ri", "ni"]
            if not all(data_cols.get(col) for col in required_cols):
                logger.error(f"相関 ({measure}) の効果量計算に必要な列が不足しています: {required_cols}")
                return "# Error: Missing columns for correlation effect size calculation"
            escalc_code = self._safe_format(
                self.templates["escalc_correlation"],
                measure=measure, ri=data_cols["ri"], ni=data_cols["ni"],
                slab_param_string=slab_param_string
            )
            main_analysis_code = self._safe_format(
                self.templates["rma_basic"],
                method=analysis_params.get("model", "REML")
            )
            return escalc_code + "\n\n" + main_analysis_code
        elif measure == "HR": # ハザード比（ログ変換データの自動検出対応）
            # HRの場合、ログ変換済みかどうかを自動検出
            yi_col = data_cols.get("yi")
            vi_col = data_cols.get("vi") 
            if yi_col and vi_col:
                # ログ変換済みの場合は事前計算として扱う
                logger.info("HR: ログ変換済みデータとして検出、事前計算効果量として処理")
                main_analysis_code = self._safe_format(
                    self.templates["rma_basic"],
                    method=analysis_params.get("model", "REML")
                )
                return self.templates["escalc_precalculated"] + "\n\n" + main_analysis_code
            else:
                # 生のHRデータの場合（現在未実装、将来的に対応予定）
                logger.warning("HR: 生のハザード比データは現在未対応です。ログ変換済みのyiとviを使用してください。")
                return "# Warning: Raw hazard ratio data not supported. Please use log-transformed yi and vi columns."
        elif measure == "PRE": # "yi" から "PRE" に変更 (パラメータ設定モーダルと合わせる)
            if not (data_cols.get("yi") and data_cols.get("vi")):
                logger.error("事前計算された効果量を使用するには 'yi' と 'vi' 列が必要です。")
                return "# Error: Missing 'yi' or 'vi' columns for pre-calculated effect sizes"
            # 事前計算済みの場合はescalcは不要、直接rmaを実行
            main_analysis_code = self._safe_format(
                self.templates["rma_basic"],
                method=analysis_params.get("model", "REML")
            )
            return self.templates["escalc_precalculated"] + "\n\n" + main_analysis_code
        else:
            logger.warning(f"未対応の効果量タイプ: {measure}")
            return f"# Warning: Unsupported effect size type: {measure}"

    def _generate_rma_code(self, analysis_params: Dict[str, Any]) -> str:
        method = analysis_params.get("model", "REML") # "method" から "model" に変更
        moderators = analysis_params.get("moderator_columns", [])
        data_cols = analysis_params.get("data_columns", {})
        
        # 実際の列名を取得（デフォルトは yi, vi）
        yi_col = data_cols.get("yi", "yi")
        vi_col = data_cols.get("vi", "vi")
        
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
                yi_col=yi_col, vi_col=vi_col
            )
        else:
            return self._safe_format(
                self.templates["rma_basic"], method=method,
                yi_col=yi_col, vi_col=vi_col
            )

    def _make_safe_var_name(self, column_name: str) -> str:
        """Generate a safe R variable name from a column name"""
        import re
        # Step 1: Remove or replace problematic characters
        safe_name = re.sub(r'[^\w\d_]', '_', column_name)
        # Step 2: Remove consecutive underscores
        safe_name = re.sub(r'_+', '_', safe_name)
        # Step 3: Remove leading/trailing underscores
        safe_name = safe_name.strip('_')
        # Step 4: Ensure it doesn't start with a number
        if safe_name and safe_name[0].isdigit():
            safe_name = 'col_' + safe_name
        # Step 5: Ensure it's not empty
        if not safe_name:
            safe_name = 'col_unknown'
        return safe_name

    def _apply_column_mapping(self, analysis_params: Dict[str, Any], column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        analysis_paramsの列名参照を、column_mappingを使ってクリーンアップ済み列名に変換する
        
        Args:
            analysis_params: 解析パラメータ（元の列名を含む可能性）
            column_mapping: {original_name: cleaned_name}の辞書
            
        Returns:
            列名が変換されたanalysis_params
        """
        # analysis_paramsのコピーを作成（元データを変更しない）
        mapped_params = analysis_params.copy()
        
        # subgroup_columns / subgroupsのマッピング
        for key in ["subgroup_columns", "subgroups"]:
            if key in mapped_params and mapped_params[key]:
                original_cols = mapped_params[key]
                mapped_cols = []
                for col in original_cols:
                    if col in column_mapping:
                        mapped_col = column_mapping[col]
                        logger.info(f"Mapping subgroup column: '{col}' -> '{mapped_col}'")
                        mapped_cols.append(mapped_col)
                    else:
                        logger.warning(f"Subgroup column '{col}' not found in mapping, using as-is")
                        mapped_cols.append(col)
                mapped_params[key] = mapped_cols
        
        # moderator_columns / moderatorsのマッピング
        for key in ["moderator_columns", "moderators"]:
            if key in mapped_params and mapped_params[key]:
                original_cols = mapped_params[key]
                mapped_cols = []
                for col in original_cols:
                    if col in column_mapping:
                        mapped_col = column_mapping[col]
                        logger.info(f"Mapping moderator column: '{col}' -> '{mapped_col}'")
                        mapped_cols.append(mapped_col)
                    else:
                        logger.warning(f"Moderator column '{col}' not found in mapping, using as-is")
                        mapped_cols.append(col)
                mapped_params[key] = mapped_cols
        
        # data_columnsがあれば、その中の列名もマッピング
        if "data_columns" in mapped_params and mapped_params["data_columns"]:
            data_cols = mapped_params["data_columns"].copy()
            for col_type, col_name in data_cols.items():
                if isinstance(col_name, str) and col_name in column_mapping:
                    mapped_col = column_mapping[col_name]
                    logger.info(f"Mapping data column [{col_type}]: '{col_name}' -> '{mapped_col}'")
                    data_cols[col_type] = mapped_col
                elif isinstance(col_name, list):
                    # 列名のリストの場合（複数列指定）
                    mapped_list = []
                    for item in col_name:
                        if item in column_mapping:
                            mapped_item = column_mapping[item]
                            logger.info(f"Mapping data column [{col_type}] list item: '{item}' -> '{mapped_item}'")
                            mapped_list.append(mapped_item)
                        else:
                            mapped_list.append(item)
                    data_cols[col_type] = mapped_list
            mapped_params["data_columns"] = data_cols
        
        return mapped_params

    def _generate_subgroup_code(self, analysis_params: Dict[str, Any]) -> str:
        subgroup_columns = analysis_params.get("subgroups", analysis_params.get("subgroup_columns", []))
        method = analysis_params.get("model", "REML") # "method" から "model" に変更
        data_cols = analysis_params.get("data_columns", {})
        
        # 実際の列名を取得
        yi_col = data_cols.get("yi", "yi")
        vi_col = data_cols.get("vi", "vi")
        
        if not subgroup_columns:
            return ""
        
        subgroup_codes = []
        for subgroup_col in subgroup_columns:
            # R変数名として安全な名前を生成（改善版）
            safe_var_name = self._make_safe_var_name(subgroup_col)
            
            # サブグループテスト用のモデル (res_subgroup_test_{safe_var_name} に結果を格納)
            subgroup_test_model_code = f"""
# Subgroup moderation test for '{subgroup_col}'
# 元の列名に対応するサニタイズ後の列名を取得
sanitized_subgroup_col <- names(column_mapping)[column_mapping == "{subgroup_col}"]
if (length(sanitized_subgroup_col) == 0) {{
    sanitized_subgroup_col <- make.names("{subgroup_col}")
}}

valid_data_for_subgroup_test <- dat[is.finite(dat$yi) & is.finite(dat$vi) & dat$vi > 0, ]

if (nrow(valid_data_for_subgroup_test) >= 2 && sanitized_subgroup_col %in% names(valid_data_for_subgroup_test)) {{
    tryCatch({{
        res_subgroup_test_{safe_var_name} <- rma(yi, vi, mods = ~ factor(valid_data_for_subgroup_test[[sanitized_subgroup_col]]), data=valid_data_for_subgroup_test, method="{method}")
        print("Subgroup test for '{subgroup_col}' completed")
    }}, error = function(e) {{
        print(sprintf("Subgroup test for '{subgroup_col}' failed: %s", e$message))
        res_subgroup_test_{safe_var_name} <- NULL
    }})
}} else {{
    print("Subgroup test for '{subgroup_col}': 有効データが不足またはカラムが存在しません")
    res_subgroup_test_{safe_var_name} <- NULL
}}"""
            
            # 各サブグループごとの解析結果を格納するリストを作成 (res_by_subgroup_{safe_var_name} に結果を格納)
            # splitとlapplyを使って、各サブグループレベルでrmaを実行し、結果をリストにまとめる
            subgroup_by_level_code = f"""
# Subgroup analysis for '{subgroup_col}' by levels
if (sanitized_subgroup_col %in% names(dat)) {{
    dat_split_{safe_var_name} <- split(dat, dat[[sanitized_subgroup_col]])
    res_by_subgroup_{safe_var_name} <- lapply(names(dat_split_{safe_var_name}), function(level_name) {{
        current_data_sg <- dat_split_{safe_var_name}[[level_name]]
        if (nrow(current_data_sg) > 0) {{
            # Valid data check and filtering
            valid_sg_data <- current_data_sg[is.finite(current_data_sg$yi) & is.finite(current_data_sg$vi) & current_data_sg$vi > 0, ]
            
            if (nrow(valid_sg_data) >= 2) {{
                tryCatch({{
                    rma_result_sg <- rma(yi, vi, data=valid_sg_data, method="{method}")
                    # Add level name to result for easier access later
                    rma_result_sg$subgroup_level <- level_name 
                    return(rma_result_sg)
                }}, error = function(e) {{
                    print(sprintf("RMA failed for subgroup '{subgroup_col}' level '%s': %s", level_name, e$message))
                    return(NULL) # Return NULL on error
                }})
            }} else {{
                print(sprintf("Subgroup '{subgroup_col}' level '%s': 有効データが不足 (n=%d)", level_name, nrow(valid_sg_data)))
                return(NULL) # Return NULL when insufficient data
            }}
        }} else {{
            return(NULL) # Return NULL when no data
        }}
    }})
    # Remove NULL elements from list
    res_by_subgroup_{safe_var_name} <- res_by_subgroup_{safe_var_name}[!sapply(res_by_subgroup_{safe_var_name}, is.null)]
    # Name list elements with subgroup level names
    if (length(res_by_subgroup_{safe_var_name}) > 0) {{
        names(res_by_subgroup_{safe_var_name}) <- sapply(res_by_subgroup_{safe_var_name}, function(x) x$subgroup_level)
    }}
}} else {{
    res_subgroup_test_{safe_var_name} <- NULL
    res_by_subgroup_{safe_var_name} <- NULL
    print("Subgroup column '{subgroup_col}' not found in data for subgroup analysis.")
}}
"""
            comment_line = f"# --- Subgroup analysis for '{subgroup_col}' ---"
            subgroup_codes.append(f"\n{comment_line}\n{subgroup_test_model_code}\n{subgroup_by_level_code}")
        return "\n".join(subgroup_codes)
    
    def _generate_subgroup_exclusion_detection(self, subgroup_columns: List[str]) -> str:
        """Generate early subgroup exclusion detection code that runs before forest plots"""
        exclusion_codes = []
        
        exclusion_codes.append("# === Subgroup Exclusion Detection (Early) ===")
        exclusion_codes.append("# Initialize exclusion tracking in summary_list")
        exclusion_codes.append("if (!exists('summary_list')) { summary_list <- list() }")
        exclusion_codes.append("if (is.null(summary_list$subgroup_exclusions)) { summary_list$subgroup_exclusions <- list() }")
        exclusion_codes.append("")
        
        for subgroup_col in subgroup_columns:
            safe_var_name = self._make_safe_var_name(subgroup_col)
            
            exclusion_code = f'''
# Detect exclusions for subgroup '{subgroup_col}'
# 元の列名に対応するサニタイズ後の列名を取得
sanitized_subgroup_col_{safe_var_name} <- names(column_mapping)[column_mapping == "{subgroup_col}"]
if (length(sanitized_subgroup_col_{safe_var_name}) == 0) {{
    sanitized_subgroup_col_{safe_var_name} <- make.names("{subgroup_col}")
}}

if (exists("res_by_subgroup_{safe_var_name}") && !is.null(res_by_subgroup_{safe_var_name})) {{
    # Get all subgroups in original data
    all_subgroups_in_data <- unique(dat[[sanitized_subgroup_col_{safe_var_name}]])
    
    # Get subgroups that have valid analysis results 
    subgroups_in_res <- names(res_by_subgroup_{safe_var_name})
    
    # Find excluded subgroups using setdiff
    excluded_subgroups <- setdiff(all_subgroups_in_data, subgroups_in_res)
    
    print(paste("DEBUG: Early exclusion detection for {subgroup_col}"))
    print(paste("DEBUG: All subgroups in data:", paste(all_subgroups_in_data, collapse=", ")))
    print(paste("DEBUG: Valid subgroups in results:", paste(subgroups_in_res, collapse=", ")))
    print(paste("DEBUG: Excluded subgroups:", paste(excluded_subgroups, collapse=", ")))
    
    # Save exclusion information if any subgroups were excluded
    if (length(excluded_subgroups) > 0) {{
        excluded_info <- list(
            excluded_subgroups = excluded_subgroups,
            reason = "insufficient_data_n_le_1",
            included_subgroups = subgroups_in_res
        )
        
        # Save to summary_list (this runs before forest plots, so no scoping issues)
        summary_list$subgroup_exclusions[['{subgroup_col}']] <- excluded_info
        
        print(paste("DEBUG: Saved exclusion info for {subgroup_col} to summary_list"))
        print(paste("DEBUG: Excluded subgroups saved:", paste(excluded_subgroups, collapse=", ")))
    }} else {{
        print(paste("DEBUG: No exclusions detected for {subgroup_col}"))
    }}
}}'''
            exclusion_codes.append(exclusion_code)
        
        return "\n".join(exclusion_codes)
        
    def _generate_plot_code(self, analysis_params: Dict[str, Any], output_paths: Dict[str, str], data_summary: Dict[str, Any]) -> str:
        plot_parts = []
        # analysis_params から data_columns を取得、なければ空の辞書
        data_cols = analysis_params.get("data_columns", {})
        ai_col = data_cols.get("ai", "") # data_columns がなくてもエラーにならないように
        bi_col = data_cols.get("bi", "") 
        ci_col = data_cols.get("ci", "")
        di_col = data_cols.get("di", "")
        n1i_col = data_cols.get("n1i", "")
        n2i_col = data_cols.get("n2i", "")

        # 1. メインフォレストプロット
        main_forest_plot_path = output_paths.get("forest_plot_path", "forest_plot_overall.png")
        plot_parts.append(
            self._safe_format(
                self.templates["forest_plot"],
                forest_plot_path=main_forest_plot_path.replace('\\', '/'),
                measure_for_plot=analysis_params.get("measure", "RR"),
                ai_col=ai_col, bi_col=bi_col, ci_col=ci_col, di_col=di_col,
                n1i_col=n1i_col, n2i_col=n2i_col,
                row_h_in_placeholder=self.PLOT_ROW_H_IN,
                base_h_in_placeholder=self.PLOT_BASE_H_IN,
                plot_width_in_placeholder=self.PLOT_WIDTH_IN,
                plot_dpi_placeholder=self.PLOT_DPI,
                extra_rows_main_placeholder=self.PLOT_EXTRA_ROWS_MAIN
            )
        )
        
        # 2. サブグループごとのフォレストプロット
        subgroup_columns = analysis_params.get("subgroups", analysis_params.get("subgroup_columns", []))
        if subgroup_columns and "subgroup_forest_plot_template" in self.templates:
            # Note: Using summary_list for exclusion info instead of global variables
            subgroup_plot_prefix = output_paths.get("forest_plot_subgroup_prefix", "forest_plot_subgroup")
            for sg_col in subgroup_columns:
                # サブグループ列が実際にデータに存在するか確認
                if sg_col not in data_summary.get("columns", []):
                    logger.warning(f"サブグループ列 '{sg_col}' がデータに存在しないため、サブグループプロットをスキップします。")
                    continue
                safe_var_name = self._make_safe_var_name(sg_col)
                sg_forest_plot_path = f"{subgroup_plot_prefix}_{safe_var_name}.png".replace('\\', '/')
                plot_parts.append(
                    self._safe_format(
                        self.templates["subgroup_forest_plot_template"],
                        subgroup_col_name=sg_col,
                        safe_var_name=safe_var_name,  # 安全な変数名を追加で渡す
                        subgroup_forest_plot_path=sg_forest_plot_path,
                        measure_for_plot=analysis_params.get("measure", "RR"),
                        ai_col=ai_col, bi_col=bi_col, ci_col=ci_col, di_col=di_col,
                        n1i_col=n1i_col, n2i_col=n2i_col,
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
                safe_mod_col_name = self._make_safe_var_name(mod_col)
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
        
        subgroup_columns = analysis_params.get("subgroups", analysis_params.get("subgroup_columns", []))
        if subgroup_columns:
            for subgroup_col in subgroup_columns:
                # サブグループ列が実際にデータに存在するか確認
                if subgroup_col not in data_summary.get("columns", []):
                    continue # スキップ
                # R変数名として安全な名前を生成（英数字とアンダースコアのみ）
                safe_var_name = self._make_safe_var_name(subgroup_col)
                additional_objects_to_save.append(f"res_subgroup_test_{safe_var_name}")
                additional_objects_to_save.append(f"res_by_subgroup_{safe_var_name}")
                subgroup_json_str_parts.append(f"""
    if (exists("res_subgroup_test_{safe_var_name}") && !is.null(res_subgroup_test_{safe_var_name})) {{
        summary_list$subgroup_moderation_test_{safe_var_name} <- list(
            subgroup_column = "{subgroup_col}", QM = res_subgroup_test_{safe_var_name}$QM,
            QMp = res_subgroup_test_{safe_var_name}$QMp, df = res_subgroup_test_{safe_var_name}$p -1, # df is p-1 for QM
            summary_text = paste(capture.output(print(res_subgroup_test_{safe_var_name})), collapse = "\\n")
        )
    }}
    if (exists("res_by_subgroup_{safe_var_name}") && !is.null(res_by_subgroup_{safe_var_name}) && length(res_by_subgroup_{safe_var_name}) > 0) {{
        subgroup_results_list_{safe_var_name} <- list()
        for (subgroup_name_idx in seq_along(res_by_subgroup_{safe_var_name})) {{
            current_res_sg <- res_by_subgroup_{safe_var_name}[[subgroup_name_idx]]
            subgroup_level_name <- names(res_by_subgroup_{safe_var_name})[subgroup_name_idx]
            if (!is.null(current_res_sg)) {{ # NULLチェックを追加
                subgroup_results_list_{safe_var_name}[[subgroup_level_name]] <- list(
                    k = current_res_sg$k, estimate = as.numeric(current_res_sg$b)[1], 
                    se = as.numeric(current_res_sg$se)[1], zval = as.numeric(current_res_sg$zval)[1],
                    pval = as.numeric(current_res_sg$pval)[1], ci_lb = as.numeric(current_res_sg$ci.lb)[1],
                    ci_ub = as.numeric(current_res_sg$ci.ub)[1], I2 = current_res_sg$I2, tau2 = current_res_sg$tau2,
                    summary_text = paste(capture.output(print(current_res_sg)), collapse = "\\n")
                )
            }}
        }}
        summary_list$subgroup_analyses_{safe_var_name} <- subgroup_results_list_{safe_var_name}
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
                safe_var_name = self._make_safe_var_name(sg_col)
                sg_forest_plot_path = f"{subgroup_plot_prefix}_{safe_var_name}.png".replace('\\\\', '/')
                generated_plots_r_list.append(f'list(label = "forest_plot_subgroup_{safe_var_name}", path = "{sg_forest_plot_path}")')
        
        if output_paths.get("funnel_plot_path"):
            funnel_plot_path_cleaned = output_paths["funnel_plot_path"].replace("\\\\", "/")
            generated_plots_r_list.append(f'list(label = "funnel_plot", path = "{funnel_plot_path_cleaned}")')
        
        if moderators:
            bubble_plot_prefix = output_paths.get("bubble_plot_path_prefix", "bubble_plot")
            for mod_col in moderators:
                if mod_col not in data_summary.get("columns", []): continue
                safe_mod_col_name = self._make_safe_var_name(mod_col)
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

        # 列名マッピングをanalysis_paramsに適用
        column_mapping = data_summary.get('column_mapping', {})
        if column_mapping:
            logger.info(f"Column mapping detected: {column_mapping}")
            analysis_params = self._apply_column_mapping(analysis_params, column_mapping)
            logger.info(f"Column mapping applied. Updated analysis_params: {analysis_params}")

        script_parts = [self.templates["library_load"]]
        
        # データ読み込み (パスはバックスラッシュをスラッシュに置換)
        # na.stringsで"NA"文字列を欠損値として処理
        csv_path_cleaned = csv_file_path_in_script.replace('\\\\', '/')
        script_parts.append(f"dat <- read.csv('{csv_path_cleaned}', na.strings = c('NA', 'na', 'N/A', 'n/a', ''))")
        
        # 列名のサニタイズ処理を追加
        script_parts.append("""
# 列名のサニタイズ（特殊文字を含む列名への対応）
original_colnames <- colnames(dat)
sanitized_colnames <- make.names(original_colnames, unique = TRUE)
if (!identical(original_colnames, sanitized_colnames)) {
    cat("列名のサニタイズを実行\\n")
    cat("変更前:", paste(original_colnames, collapse = ", "), "\\n")
    cat("変更後:", paste(sanitized_colnames, collapse = ", "), "\\n")
    
    # 元の列名とサニタイズ後の列名のマッピングを作成
    column_mapping <- setNames(original_colnames, sanitized_colnames)
    colnames(dat) <- sanitized_colnames
} else {
    column_mapping <- setNames(original_colnames, original_colnames)
}
""")
        
        # データ品質チェック（NA値の確認）
        script_parts.append("""
# データ品質チェック
cat("データ読み込み完了\\n")
cat("総行数:", nrow(dat), "\\n")
if (any(is.na(dat))) {
    na_summary <- sapply(dat, function(x) sum(is.na(x)))
    na_cols <- na_summary[na_summary > 0]
    if (length(na_cols) > 0) {
        cat("欠損値を含む列:\\n")
        for (col_name in names(na_cols)) {
            cat("  ", col_name, ":", na_cols[col_name], "個\\n")
        }
    }
} else {
    cat("欠損値なし\\n")
}

# 解析に必要な数値列の数値変換とNA値処理
numeric_cols_to_check <- c()
""")
        
        # 数値変換が必要な列をリストに追加
        data_cols = analysis_params.get("data_columns", {})
        numeric_conversion_code = []
        
        # 二値アウトカムの場合の数値列
        if analysis_params.get("measure") in ["OR", "RR", "RD", "PETO"]:
            for col_key in ["ai", "ci", "n1i", "n2i"]:
                col_name = data_cols.get(col_key)
                if col_name:
                    numeric_conversion_code.append(f"""
if ("{col_name}" %in% names(dat)) {{
    cat("数値変換: {col_name}\\n")
    original_values <- dat${col_name}
    dat${col_name} <- as.numeric(as.character(dat${col_name}))
    invalid_rows <- which(is.na(dat${col_name}))
    if (length(invalid_rows) > 0) {{
        cat("⚠️ データ品質警告: {col_name}列でNA値または非数値データが検出されました\\n")
        cat("   対象行: ", paste(invalid_rows, collapse=", "), "\\n")
        if ("{data_cols.get('study_label', 'study_id')}" %in% names(dat)) {{
            invalid_studies <- dat[invalid_rows, "{data_cols.get('study_label', 'study_id')}"]
            cat("   該当研究: ", paste(invalid_studies, collapse=", "), "\\n")
        }}
        cat("   元の値: ", paste(original_values[invalid_rows], collapse=", "), "\\n")
        cat("   これらの研究は解析から除外されます\\n")
    }}
}}""")
        
        if numeric_conversion_code:
            script_parts.append("\n".join(numeric_conversion_code))
        
        # SE列を分散に変換する処理
        data_cols = analysis_params.get("data_columns", {})
        se_col_needs_squaring = data_cols.get("se_col_needs_squaring")
        if se_col_needs_squaring:
            squared_col_name = f"{se_col_needs_squaring}_squared"
            script_parts.append(f"# SE列を分散に変換")
            script_parts.append(f"dat${squared_col_name} <- dat${se_col_needs_squaring}^2")
        
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

        # メインの解析は escalc_code内の main_analysis_selection で既に実行済み
        # res と res_for_plot がここで設定される
        
        # モデレーターがある場合のみ追加の回帰解析を実行
        moderators = analysis_params.get("moderator_columns", [])
        if moderators:
            # 有効なモデレーターのみを対象とする
            valid_moderators_in_code = [m for m in moderators if m in data_summary.get("columns", [])]
            if valid_moderators_in_code:
                # モデレーター列名のサニタイズ処理
                sanitized_moderator_formula_parts = []
                for mod in valid_moderators_in_code:
                    sanitized_moderator_formula_parts.append(f'dat[[names(column_mapping)[column_mapping == "{mod}"]]]')
                
                mods_formula_sanitized = " + ".join(sanitized_moderator_formula_parts)
                
                # モデレーター解析の追加（主解析とは別に実行）
                moderator_analysis_code = f"""
# モデレーター解析（主解析とは別途実行）
# モデレーター列のサニタイズ処理
moderator_cols_original <- c({', '.join([f'"{m}"' for m in valid_moderators_in_code])})
moderator_cols_sanitized <- sapply(moderator_cols_original, function(col) {{
    sanitized <- names(column_mapping)[column_mapping == col]
    if (length(sanitized) == 0) {{ 
        sanitized <- make.names(col)
    }}
    return(sanitized)
}})

if (exists("main_analysis_method") && main_analysis_method == "MH") {{
    # MH法の場合は逆分散法でモデレーター解析（MH法はモデレーター未対応のため）
    print("モデレーター解析: MH法では直接モデレーター分析ができないため、逆分散法で実行")
    
    # 無限大値をチェックして除外
    valid_data_for_regression <- dat[is.finite(dat$yi) & is.finite(dat$vi) & dat$vi > 0, ]
    
    if (nrow(valid_data_for_regression) >= 2) {{
        # サニタイズされた列名でフォーミュラを作成
        mods_formula_str <- paste(moderator_cols_sanitized, collapse = " + ")
        mods_formula <- as.formula(paste("~ ", mods_formula_str))
        
        res_moderator <- rma(yi, vi, mods = mods_formula, data=valid_data_for_regression, method="REML")
        print(paste("モデレーター解析完了: 有効データ", nrow(valid_data_for_regression), "件で実行"))
    }} else {{
        print("モデレーター解析: 有効データが不足のため実行できません")
        res_moderator <- NULL
    }}
}} else {{
    # 逆分散法の場合はそのままモデレーター解析
    valid_data_for_regression <- dat[is.finite(dat$yi) & is.finite(dat$vi) & dat$vi > 0, ]
    
    if (nrow(valid_data_for_regression) >= 2) {{
        # サニタイズされた列名でフォーミュラを作成
        mods_formula_str <- paste(moderator_cols_sanitized, collapse = " + ")
        mods_formula <- as.formula(paste("~ ", mods_formula_str))
        
        res_moderator <- rma(yi, vi, mods = mods_formula, data=valid_data_for_regression, method="{analysis_params.get("model", "REML")}")
    }} else {{
        print("モデレーター解析: 有効データが不足のため実行できません")
        res_moderator <- NULL
    }}
}}
"""
                script_parts.append(moderator_analysis_code)

        # サブグループ解析 (res_subgroup_test_{col} と res_by_subgroup_{col} に結果格納)
        subgroup_cols = analysis_params.get("subgroup_columns", [])
        if subgroup_cols:
            # サブグループ列が実際にデータに存在するか確認
            valid_subgroup_cols = [sgc for sgc in subgroup_cols if sgc in data_summary.get("columns", [])]
            if valid_subgroup_cols:
                # analysis_params をコピーして、有効なサブグループ列のみを設定
                subgroup_analysis_params = analysis_params.copy()
                subgroup_analysis_params["subgroups"] = valid_subgroup_cols
                subgroup_code = self._generate_subgroup_code(subgroup_analysis_params)
                script_parts.append(subgroup_code)
                
                # サブグループ除外情報を早期に検出・保存（森林プロット生成前）
                subgroup_exclusion_code = self._generate_subgroup_exclusion_detection(valid_subgroup_cols)
                script_parts.append(subgroup_exclusion_code)
            else:
                logger.warning("指定されたサブグループ列がデータに存在しないため、サブグループ解析をスキップします。")


        # Egger's test (ファンネルプロットが要求されている場合)
        if output_paths.get("funnel_plot_path"):
            script_parts.append("egger_test_res <- tryCatch(regtest(res_for_plot), error = function(e) { print(sprintf(\"Egger's test failed: %s\", e$message)); return(NULL) })")


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
