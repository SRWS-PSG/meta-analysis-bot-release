# R Template Modularization Design

## 問題の概要
現在のRテンプレートは単一の大きなファイル（約1600行）で、サブグループ除外処理に問題がある：
- `dat_ordered_filtered`でデータをフィルタリングしているが、`res_for_plot`は元の全データを含む
- 除外されたサブグループの研究がフォレストプロットに表示される

## モジュール化設計

### 1. Core Functions Module (`r_template_functions.py`)
共通関数をまとめたモジュール：

```python
class RTemplateFunctions:
    """Rスクリプトで使用する関数テンプレート"""
    
    @staticmethod
    def get_data_loading_functions():
        """データ読み込みと前処理の関数"""
        return """
# --- データ読み込み関数 ---
load_and_prepare_data <- function(csv_path) {
    dat <- read.csv(csv_path, na.strings = c('NA', 'na', 'N/A', 'n/a', ''))
    
    # データ品質チェック
    cat("データ読み込み完了\\n")
    cat("総行数:", nrow(dat), "\\n")
    
    # Study列の追加（存在しない場合）
    if (!"Study" %in% names(dat)) {
        dat$Study <- paste("Study", 1:nrow(dat))
    }
    
    # slab列の追加
    dat$slab <- dat$Study
    
    return(dat)
}

# --- ゼロセル処理関数 ---
handle_zero_cells <- function(dat, measure, ai_col, bi_col, ci_col, di_col) {
    zero_cells_info <- list(has_zero_cells = FALSE, studies_with_zero = c())
    
    if (measure %in% c("OR", "RR", "RD", "PETO") && 
        all(c(ai_col, bi_col, ci_col, di_col) %in% names(dat))) {
        
        zero_mask <- (dat[[ai_col]] == 0 | dat[[bi_col]] == 0 | 
                      dat[[ci_col]] == 0 | dat[[di_col]] == 0)
        
        if (any(zero_mask, na.rm = TRUE)) {
            zero_cells_info$has_zero_cells <- TRUE
            zero_cells_info$studies_with_zero <- dat$Study[which(zero_mask)]
            zero_cells_info$count <- sum(zero_mask, na.rm = TRUE)
        }
    }
    
    return(zero_cells_info)
}
"""

    @staticmethod
    def get_subgroup_functions():
        """サブグループ解析の関数"""
        return """
# --- サブグループ除外判定関数 ---
identify_excluded_subgroups <- function(dat, subgroup_col, min_studies = 2) {
    sg_counts <- table(dat[[subgroup_col]])
    excluded_sgs <- names(sg_counts)[sg_counts < min_studies]
    valid_sgs <- names(sg_counts)[sg_counts >= min_studies]
    
    return(list(
        excluded = excluded_sgs,
        valid = valid_sgs,
        counts = sg_counts
    ))
}

# --- サブグループ別メタ解析関数 ---
perform_subgroup_analysis <- function(dat, subgroup_col, measure, method, ...) {
    sg_info <- identify_excluded_subgroups(dat, subgroup_col)
    
    # 有効なサブグループのみでデータをフィルタ
    dat_valid <- dat[dat[[subgroup_col]] %in% sg_info$valid, ]
    
    if (nrow(dat_valid) == 0) {
        return(list(
            test = NULL,
            by_subgroup = list(),
            excluded_info = sg_info
        ))
    }
    
    # メタ解析実行（有効なデータのみ）
    res <- escalc(measure = measure, data = dat_valid, ...)
    res_model <- rma(yi, vi, data = res, method = method, 
                     mods = ~ factor(get(subgroup_col)) - 1)
    
    # サブグループテスト
    res_test <- rma(yi, vi, data = res, method = method, 
                    mods = ~ factor(get(subgroup_col)))
    
    # 各サブグループの結果
    by_subgroup <- list()
    for (sg in sg_info$valid) {
        sg_data <- res[res[[subgroup_col]] == sg, ]
        if (nrow(sg_data) > 0) {
            by_subgroup[[sg]] <- rma(yi, vi, data = sg_data, method = method)
        }
    }
    
    return(list(
        test = res_test,
        by_subgroup = by_subgroup,
        excluded_info = sg_info,
        filtered_data = dat_valid
    ))
}

# --- サブグループフォレストプロット用データ準備 ---
prepare_subgroup_forest_data <- function(dat, subgroup_col, valid_subgroups) {
    # 有効なサブグループのみでフィルタリング
    dat_filtered <- dat[dat[[subgroup_col]] %in% valid_subgroups, ]
    
    # サブグループでソート
    dat_ordered <- dat_filtered[order(dat_filtered[[subgroup_col]]), ]
    
    return(dat_ordered)
}
"""

    @staticmethod 
    def get_plotting_functions():
        """プロット生成の関数"""
        return """
# --- サブグループフォレストプロット関数 ---
plot_subgroup_forest <- function(res_main, dat_subgroup, subgroup_col, 
                                 subgroup_results, measure, output_path) {
    # dat_subgroupは既にフィルタ済みのデータ
    
    # 各サブグループの位置計算
    sg_table <- table(dat_subgroup[[subgroup_col]])
    sg_names <- names(sg_table)
    n_sg <- length(sg_names)
    
    # 行位置計算
    total_studies <- nrow(dat_subgroup)
    current_row <- total_studies + (n_sg * 2) + 2
    
    rows_list <- list()
    subtotal_rows <- c()
    
    for (i in 1:n_sg) {
        sg_name <- sg_names[i]
        n_studies_sg <- sg_table[sg_name]
        
        study_rows <- seq(current_row - n_studies_sg + 1, current_row)
        rows_list[[sg_name]] <- study_rows
        
        subtotal_row <- current_row - n_studies_sg - 1
        subtotal_rows <- c(subtotal_rows, subtotal_row)
        names(subtotal_rows)[length(subtotal_rows)] <- sg_name
        
        current_row <- current_row - n_studies_sg - 2
    }
    
    # フィルタ済みデータに対応するres_mainのサブセットを作成
    filtered_indices <- which(rownames(res_main$data) %in% rownames(dat_subgroup))
    res_for_plot <- res_main
    res_for_plot$yi <- res_main$yi[filtered_indices]
    res_for_plot$vi <- res_main$vi[filtered_indices]
    res_for_plot$se <- res_main$se[filtered_indices]
    res_for_plot$ni <- res_main$ni[filtered_indices]
    
    # プロット
    all_study_rows <- unlist(rows_list)
    ylim_range <- c(min(subtotal_rows) - 3, max(all_study_rows) + 3)
    
    forest(res_for_plot, 
           slab = dat_subgroup$slab,
           rows = all_study_rows,
           ylim = ylim_range,
           atransf = if(measure %in% c("OR", "RR", "HR")) exp else I)
    
    # サブグループサマリー追加
    for (sg_name in sg_names) {
        if (!is.null(subgroup_results[[sg_name]])) {
            addpoly(subgroup_results[[sg_name]], 
                    row = subtotal_rows[sg_name],
                    mlab = paste(sg_name, " (k=", sg_table[sg_name], ")", sep=""))
        }
    }
    
    return(invisible(NULL))
}
"""
```

### 2. Template Modules

#### `r_template_base.py`
```python
class RTemplateBase:
    """基本的なテンプレート構造"""
    
    def __init__(self):
        self.functions = RTemplateFunctions()
        
    def get_library_load(self):
        return """
library(metafor)
library(jsonlite)

# 共通関数の読み込み
{functions}
""".format(functions=self.functions.get_data_loading_functions() + 
                      self.functions.get_subgroup_functions() + 
                      self.functions.get_plotting_functions())
```

#### `r_template_analysis.py`
```python
class RTemplateAnalysis:
    """解析実行のテンプレート"""
    
    @staticmethod
    def get_main_analysis_template():
        return """
# --- メイン解析 ---
dat <- load_and_prepare_data('{csv_path}')

# ゼロセル処理
zero_cells_info <- handle_zero_cells(dat, "{measure}", 
                                     "{ai_col}", "{bi_col}", 
                                     "{ci_col}", "{di_col}")

# 効果量計算
res <- escalc(measure = "{measure}", 
              ai = {ai_safe}, bi = {bi_safe},
              ci = {ci_safe}, di = {di_safe},
              data = dat, append = TRUE)

# メタ解析モデル
res_model <- rma(yi, vi, data = res, method = "{method}")

# プロット用オブジェクト（全データ）
res_for_plot <- res_model
"""

    @staticmethod
    def get_subgroup_analysis_template():
        return """
# --- サブグループ解析: {subgroup_col} ---
sg_analysis <- perform_subgroup_analysis(
    dat = dat,
    subgroup_col = "{subgroup_col}",
    measure = "{measure}",
    method = "{method}",
    ai = {ai_safe}, bi = {bi_safe},
    ci = {ci_safe}, di = {di_safe}
)

res_subgroup_test_{safe_var_name} <- sg_analysis$test
res_by_subgroup_{safe_var_name} <- sg_analysis$by_subgroup
excluded_subgroups_{safe_var_name} <- sg_analysis$excluded_info

# 除外情報をサマリーに記録
if (!exists("summary_list")) {{
    summary_list <- list()
}}
if (is.null(summary_list$subgroup_exclusions)) {{
    summary_list$subgroup_exclusions <- list()
}}
summary_list$subgroup_exclusions[['{subgroup_col}']] <- list(
    excluded_subgroups = sg_analysis$excluded_info$excluded,
    reason = "insufficient_data",
    included_subgroups = sg_analysis$excluded_info$valid
)
"""
```

#### `r_template_plots.py`
```python
class RTemplatePlots:
    """プロット生成のテンプレート"""
    
    @staticmethod
    def get_subgroup_forest_plot_template():
        return """
# --- サブグループフォレストプロット: {subgroup_col} ---
if (exists("sg_analysis") && !is.null(sg_analysis$filtered_data) && 
    nrow(sg_analysis$filtered_data) > 0) {{
    
    png('{subgroup_forest_plot_path}', width=10, height=8, 
        units="in", res=300)
    
    tryCatch({{
        plot_subgroup_forest(
            res_main = res,
            dat_subgroup = sg_analysis$filtered_data,
            subgroup_col = "{subgroup_col}",
            subgroup_results = sg_analysis$by_subgroup,
            measure = "{measure}",
            output_path = '{subgroup_forest_plot_path}'
        )
    }}, error = function(e) {{
        plot(1, type="n", main="Error in Subgroup Forest Plot", 
             xlab="", ylab="")
        text(1, 1, paste("Error:", e$message), col="red")
    }})
    
    dev.off()
}}
"""
```

### 3. Main Generator Integration

```python
# templates/r_template_generator.py の修正

class RTemplateGenerator:
    def __init__(self):
        self.base = RTemplateBase()
        self.analysis = RTemplateAnalysis()
        self.plots = RTemplatePlots()
        
    def generate_full_r_script(self, analysis_params, data_summary, 
                               output_paths, csv_file_path):
        """モジュール化されたテンプレートからRスクリプトを生成"""
        
        script_parts = [
            self.base.get_library_load(),
            self._generate_data_loading(csv_file_path),
            self._generate_main_analysis(analysis_params),
            self._generate_subgroup_analyses(analysis_params, data_summary),
            self._generate_plots(analysis_params, output_paths, data_summary),
            self._generate_save_results(output_paths)
        ]
        
        return "\n\n".join(script_parts)
```

## 利点

1. **保守性向上**: 各機能が独立したモジュールに分離
2. **テスト容易性**: 各モジュールを個別にテスト可能
3. **再利用性**: 共通関数を複数の場所で使用可能
4. **バグ修正**: サブグループ除外処理が明確に分離され、修正が容易
5. **拡張性**: 新機能の追加が簡単

## 実装手順

1. 新しいモジュール構造を作成
2. 既存のテンプレートを段階的に移行
3. サブグループ除外処理を修正
4. テストケースで動作確認