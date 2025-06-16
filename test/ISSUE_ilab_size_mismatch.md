# Issue: ilab argument does not correspond to the size of the original dataset

## 問題の概要
サブグループforest plot生成時に `ilab` データのサイズが `res_for_plot_filtered` オブジェクトのサイズと一致せず、サイズ不整合エラーが発生する。

## エラーメッセージ
```
Error: ilab argument does not correspond to the size of the original dataset
```

## 発生箇所
`templates/r_templates.py` のサブグループforest plotテンプレート:

### 問題のコード
```r
# ilab_data_main は dat_ordered_filtered から作成（フィルタなし）
treatment_display_main <- paste(dat_ordered_filtered[[ai_col_main]], "/", dat_ordered_filtered[[n1i_col_main]], sep="")
control_display_main <- paste(dat_ordered_filtered[[ci_col_main]], "/", dat_ordered_filtered[[n2i_col_main]], sep="")
ilab_data_main <- cbind(treatment_display_main, control_display_main)

# しかし forest plot では filtered_indices でフィルタされたデータを使用
res_for_plot_filtered$yi <- res_for_plot_model_name$yi[filtered_indices]
res_for_plot_filtered$slab <- res_for_plot_model_name$slab[filtered_indices]

# 🚨 サイズ不整合: 
# ilab_data_main のサイズ = nrow(dat_ordered_filtered)
# res_for_plot_filtered のサイズ = length(filtered_indices)

forest_sg_args$ilab <- ilab_data_main  # ← ここでエラー
```

## 原因分析
1. **ilab_data_main**: `dat_ordered_filtered` 全体から作成される
2. **res_for_plot_filtered**: `filtered_indices` でフィルタされる
3. **サイズ不一致**: 両者のサイズが異なる場合がある
4. **フィルタ忘れ**: `ilab_data_main` に同じフィルタリングが適用されていない

## 影響範囲
- サブグループforest plot生成が失敗
- `forest_plot_subgroup_*.png` ファイルが生成されない
- 「Treatment/Control」列の表示ができない

## 解決策

### 1. ilab データのフィルタリング追加
```r
# res_for_plot_filtered の作成後、ilab_data_main も同様にフィルタ
if (!is.null(ilab_data_main)) {
    ilab_data_main <- ilab_data_main[filtered_indices, , drop=FALSE]
    print(paste("DEBUG: Filtered ilab_data_main to", nrow(ilab_data_main), "rows"))
}
```

### 2. サイズ検証の追加
```r
# サイズ整合性の確認
if (!is.null(ilab_data_main) && nrow(ilab_data_main) != res_for_plot_filtered$k) {
    print(paste("WARNING: ilab size mismatch. Setting ilab to NULL"))
    print(paste("  ilab rows:", nrow(ilab_data_main)))
    print(paste("  res_for_plot k:", res_for_plot_filtered$k))
    ilab_data_main <- NULL
    ilab_xpos_main <- NULL
    ilab_lab_main <- NULL
}
```

### 3. 条件付き ilab 設定
```r
# ilab が NULL でない場合のみ forest に追加
if (!is.null(ilab_data_main)) {
    forest_sg_args$ilab <- ilab_data_main
    forest_sg_args$ilab.xpos <- ilab_xpos_main
    forest_sg_args$ilab.lab <- ilab_lab_main
}
```

## 修正実装場所
**ファイル**: `templates/r_templates.py`
**行番号**: 約600行目（res_for_plot_filtered作成後）

### 修正前
```r
# データフレームもフィルタリング
res_for_plot_filtered$data <- {res_for_plot_model_name}$data[filtered_indices, ]

# ここに修正コードを追加
```

### 修正後
```r
# データフレームもフィルタリング
res_for_plot_filtered$data <- {res_for_plot_model_name}$data[filtered_indices, ]

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
```

## 優先度
**High** - サブグループ解析の表示機能に影響

## テスト方法
```bash
cd /home/youkiti/meta-analysis-bot-release/tests
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "Regionでサブグループ解析をお願いします"
```

## 期待される修正後の動作
- ilab サイズ不整合エラーが発生しない
- サブグループforest plotが正常に生成される
- Treatment/Control 列が適切に表示される
- `forest_plot_subgroup_*.png` ファイルが正常に添付される