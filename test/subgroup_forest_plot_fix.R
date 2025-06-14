# サブグループフォレストプロット修正案
# res_for_plotをフィルタリングする処理を追加

# 修正前のコード（問題あり）:
# forest_sg_args <- list(
#     x = res_for_plot,  # 全データを含む
#     slab = dat_ordered_filtered$slab,  # フィルタ済み
#     ...
# )

# 修正後のコード:
# フィルタ済みデータのインデックスを取得
filtered_indices <- which(rownames(res_for_plot$data) %in% rownames(dat_ordered_filtered))

# res_for_plotのコピーを作成し、フィルタ済みデータのみを含むようにする
res_for_plot_filtered <- res_for_plot

# 効果量と分散をフィルタリング
res_for_plot_filtered$yi <- res_for_plot$yi[filtered_indices]
res_for_plot_filtered$vi <- res_for_plot$vi[filtered_indices]
res_for_plot_filtered$se <- res_for_plot$se[filtered_indices]

# その他の要素もフィルタリング（存在する場合）
if (!is.null(res_for_plot$ni)) {
    res_for_plot_filtered$ni <- res_for_plot$ni[filtered_indices]
}
if (!is.null(res_for_plot$weights)) {
    res_for_plot_filtered$weights <- res_for_plot$weights[filtered_indices]
}

# データ行数を更新
res_for_plot_filtered$k <- length(filtered_indices)

# データフレームもフィルタリング
res_for_plot_filtered$data <- res_for_plot$data[filtered_indices, ]

# メインのforest plotを描画（フィルタ済みのres_for_plotを使用）
forest_sg_args <- list(
    x = res_for_plot_filtered,  # フィルタ済みのオブジェクト
    slab = dat_ordered_filtered$slab,
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