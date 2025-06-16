# Issue: `forest()` function does not have a `subset` argument

## 問題の概要
サブグループforest plot生成時に `forest()` 関数で `subset` 引数を使用しているが、metaforパッケージの `forest()` 関数は `subset` パラメータをサポートしていない。

## エラーメッセージ
```
Error: function does not have a `subset` argument
```

## 発生箇所
`templates/r_templates.py` の subgroup forest plot template:
```r
forest_sg_args <- list(
    x = res_for_plot, # 元の解析結果を使用
    subset = filtered_indices,     # ← この部分でエラー
    ...
)
```

## 原因
1. metaforの `forest.rma()` 関数は `subset` パラメータをサポートしていない
2. 修正時に `subset` パラメータを追加したが、実際には存在しない機能だった
3. 代わりに事前にデータをフィルタして新しいrmaオブジェクトを作成する必要がある

## 影響範囲
- サブグループforest plot生成が失敗する
- `forest_plot_subgroup_*.png` ファイルが生成されない
- Slackボットの解析が完了しない

## 解決策

### 1. `subset` パラメータを削除
```r
# 修正前（エラー）
forest_sg_args <- list(
    x = res_for_plot,
    subset = filtered_indices,  # ← 削除
    ...
)

# 修正後
forest_sg_args <- list(
    x = res_for_plot,
    # subsetパラメータを削除
    ...
)
```

### 2. 事前フィルタリングアプローチ
データを事前にフィルタして、サブグループ専用のrmaオブジェクトを作成:

```r
# サブグループデータの事前フィルタリング
subgroup_data <- dat_ordered_filtered[dat_ordered_filtered$subgroup_col == subgroup_level, ]

# サブグループ専用のrma解析
if (nrow(subgroup_data) > 1) {
    subgroup_res <- rma(yi, vi, data = subgroup_data, method = "REML")
    
    # forest plot生成
    forest(subgroup_res, ...)
}
```

### 3. 手動フィルタリングの復活（安全版）
slabベクトルの整合性を保ちながら手動フィルタリング:

```r
# 安全な手動フィルタリング
valid_indices <- which(!is.na(res_for_plot$yi) & !is.na(res_for_plot$vi))
filtered_res <- res_for_plot
filtered_res$yi <- res_for_plot$yi[valid_indices]
filtered_res$vi <- res_for_plot$vi[valid_indices]
filtered_res$k <- length(valid_indices)

# slabも同様にフィルタ
if (!is.null(res_for_plot$slab)) {
    filtered_res$slab <- res_for_plot$slab[valid_indices]
}

forest(filtered_res, ...)
```

## 優先度
**High** - サブグループ解析機能の中核部分が動作しない

## 修正実装計画
1. `subset` パラメータを即座に削除
2. 事前フィルタリングアプローチに変更
3. slabベクトル整合性の確保
4. テストで動作確認

## 関連ファイル
- `templates/r_templates.py` (line ~758)
- `test/generated_fixed_script.R` 
- `test/final_slab_test_script.R`

## テスト方法
```bash
cd /home/youkiti/meta-analysis-bot-release/tests
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "Regionでサブグループ解析をお願いします"
```

## 期待される修正後の動作
- subsetエラーが発生しない
- サブグループforest plotが正常に生成される
- `forest_plot_subgroup_*.png` ファイルが添付される