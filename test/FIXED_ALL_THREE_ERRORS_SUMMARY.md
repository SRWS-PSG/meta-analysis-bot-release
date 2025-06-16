# 修正完了: サブグループforest plot生成の3つのエラー

## 概要
サブグループforest plot生成時に発生していた3つの関連エラーをすべて修正しました。

## 修正されたエラー

### ✅ 1. slab length mismatch エラー
**エラー**: `length of the slab argument does not correspond to the size of the original dataset`

**原因**: 
- metaforの`escalc()`および`rma.mh()`関数がNA値や条件に基づいて内部的に行を削除
- slab引数としてベクトルを渡していたため、元データとサイズが不一致

**修正**: 
- `slab_param_string`の使用を停止
- `slab=slab`として列名参照に変更
- `templates/r_templates.py:77-111`で修正済み

### ✅ 2. subset parameter エラー  
**エラー**: `forest function does not have a 'subset' argument`

**原因**:
- `forest()`関数に存在しない`subset`引数を使用していた
- フィルタリングされたデータとsubset引数の併用で混乱

**修正**:
- `subset = filtered_indices`の使用を停止
- 事前にフィルタリングした`res_for_plot_filtered`を直接使用
- `templates/r_templates.py:641`で修正済み

### ✅ 3. ilab size mismatch エラー
**エラー**: `ilab argument does not correspond to the size of the original dataset`

**原因**:
- `ilab_data_main`が元データサイズで作成される
- `res_for_plot_filtered`がフィルタリング済みでサイズが異なる
- ilab引数のフィルタリングを忘れていた

**修正**:
- `ilab_data_main`にも同じ`filtered_indices`を適用
- サイズ検証とフォールバック処理を追加
- `templates/r_templates.py:604-616`で修正済み

## 修正内容の詳細

### コード変更箇所

#### 1. escalc()テンプレート修正
```r
# 修正前
dat <- escalc(measure="{measure}", ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, slab={slab_param_string})

# 修正後  
dat <- escalc(measure="{measure}", ai={ai}, bi={bi}, ci={ci}, di={di}, data=dat, slab=slab)
```

#### 2. forest()サブグループプロット修正
```r
# 修正前
forest_sg_args <- list(
    x = res_for_plot,
    subset = filtered_indices,  # ← エラーの原因
    ...
)

# 修正後
forest_sg_args <- list(
    x = res_for_plot_filtered,  # フィルタ済みデータを直接使用
    ...
)
```

#### 3. ilab_data_mainフィルタリング追加
```r
# 新規追加: ilab_data_mainも同様にフィルタリング
if (!is.null(ilab_data_main)) {
    ilab_data_main <- ilab_data_main[filtered_indices, , drop=FALSE]
    print(paste("DEBUG: Filtered ilab_data_main to", nrow(ilab_data_main), "rows"))
    
    # サイズ検証
    if (nrow(ilab_data_main) != res_for_plot_filtered$k) {
        print("WARNING: ilab size still mismatched after filtering, disabling ilab")
        ilab_data_main <- NULL
        ilab_xpos_main <- NULL  
        ilab_lab_main <- NULL
    }
}
```

## テスト結果

### 包括的テストの実行
```bash
cd /home/youkiti/meta-analysis-bot-release
python3 test/test_ilab_fix_comprehensive.py
```

**結果**: 🎉 全ての修正が正常に適用されました！
- ✅ slab length mismatch エラー修正: OK
- ✅ subset parameter エラー修正: OK  
- ✅ ilab size mismatch エラー修正: OK
- ✅ サブグループforest plot生成準備完了

### Slackボットテスト推奨コマンド
```bash
cd /home/youkiti/meta-analysis-bot-release/tests
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "Regionでサブグループ解析をお願いします"
```

## 期待される動作
1. **エラーなし**: 3つのエラーがすべて解消され、サブグループforest plotが正常生成される
2. **データ整合性**: slab、ilab、plot dataのサイズがすべて一致
3. **除外処理**: 研究数が少ないサブグループは適切に除外される
4. **デバッグ情報**: 各段階でのデータサイズがログ出力される

## 影響範囲
- **二値アウトカム解析**: OR、RR、RD、PETO
- **サブグループ解析**: 任意のカテゴリ変数でのサブグループ化
- **forest plot**: メイン図とサブグループ図の両方
- **Treatment/Control列**: 適切に表示される

## デバッグ情報の確認
修正後は以下のログが表示されます：
```
DEBUG: Filtered ilab_data_main to X rows
DEBUG: res_for_plot_filtered k: X
DEBUG: Using pre-filtered data for forest plot - no subset parameter needed
```

## 今後の保守
- 新しい効果量タイプ追加時は、同様のフィルタリングパターンを適用
- メタパッケージ更新時は、このパターンの互換性を確認
- テストケースは`test_ilab_fix_comprehensive.py`で包括的にカバー

## 関連ファイル
- **修正ファイル**: `templates/r_templates.py`
- **テストファイル**: `test/test_ilab_fix_comprehensive.py`  
- **テストスクリプト**: `test/comprehensive_fix_test_script.R`
- **問題解析**: `test/ISSUE_ilab_size_mismatch.md`
- **個別修正**: `test/FIXED_subset_argument_summary.md`

**修正完了日**: 2025-06-16  
**修正者**: Claude Code  
**テスト環境**: Ubuntu 22.04, R 4.x, metafor package