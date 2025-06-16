# Test Directory

This directory contains test scripts and debugging tools for the Meta-Analysis Bot.

## Test Files

### test_subgroup_column_fix.py
**Purpose**: Tests the fix for subgroup analysis with special characters in column names
- Verifies R variable name generation with special characters
- Tests column name cleaning and matching
- Validates JSON output structure
- Tests Slack message display with proper column names

### test_subgroup_exclusion_fix.py
**Purpose**: Tests the subgroup exclusion logic for small subgroups
- Verifies that subgroups with n≤1 are excluded from forest plots
- Tests exclusion information is properly recorded
- Validates that analysis continues with remaining valid subgroups

### test_r_template_fixes.py
**Purpose**: General R template generation tests
- Tests various effect size types
- Validates plot generation
- Tests error handling in R scripts

## Debug Tools

### SUBGROUP_FIX_SUMMARY.md
Documentation of the column name handling fix implemented on 2025-06-14

## Running Tests

```bash
# Run individual test
python test/test_subgroup_column_fix.py

# Run all tests (if test runner implemented)
python -m pytest test/
```

## 新規追加テストファイル (2025-06-16)

### slab エラー修正関連

#### `slab_error_fix_proposal.py`
**概要**: `"length of the slab argument does not correspond to the size of the original dataset"` エラーの修正提案
**機能**:
- エラーの根本原因分析
- 修正アプローチの詳細説明
- 修正されたRテンプレート例の生成

#### `fixed_subgroup_slab_template.py`
**概要**: 修正版サブグループforest plotテンプレート
**主な修正点**:
1. slabベクトルの手動操作を廃止
2. 列名参照による自動処理に統一  
3. フィルタリング処理の簡素化
4. metafor関数の内部データ処理に依存

#### `test_slab_fix.py`
**概要**: 修正されたslabエラー対応のテスト
**テスト内容**:
1. 修正されたテンプレートでのRスクリプト生成
2. 実際のCSVデータでの動作確認
3. サブグループ解析でのslabエラーの解消確認

**実行方法**:
```bash
cd /home/youkiti/meta-analysis-bot-release
python3 test/test_slab_fix.py
```

#### `generated_fixed_script.R`
**概要**: テストで生成された修正済みRスクリプト
**確認ポイント**:
- 119行目: `escalc(..., slab=slab)` - 列名参照
- 132行目: `rma.mh(..., slab=slab)` - 列名参照  
- 318行目: `forest()` - slab明示的指定なし（自動処理）

## 修正内容サマリー

### 問題の正体
```
length of the slab argument does not correspond to the size of the original dataset
```

このエラーは、metaforパッケージの`escalc()`や`rma.mh()`関数で以下の状況で発生:
1. **データ行削除**: NA値や両群ゼロ行が内部で自動削除される
2. **slabベクトル不整合**: 元のslab長さがフィルタ後のデータと一致しない
3. **参照方式の違い**: `slab=study_id`（列名参照）vs `slab=dat$study_id`（ベクトル参照）

### 修正内容

#### 1. テンプレートファイル修正 (`templates/r_templates.py`)

**escalc_binary テンプレート (79-80行目)**:
```r
# 修正前
dat <- escalc(..., data=dat{slab_param_string})

# 修正後  
dat <- escalc(..., data=dat, slab={slab_column})
```

**rma.mh テンプレート (89-91行目)**:
```r
# 修正前
res <- rma.mh(..., data=dat, measure="{measure}", add=0, to="none", drop00=TRUE, correct=TRUE)

# 修正後
res <- rma.mh(..., data=dat, measure="{measure}", add=0, to="none", drop00=TRUE, correct=TRUE, slab={slab_column})
```

**メインforest plot (285-288行目)**:
```r
# 修正前
forest_args <- list(
    x = res_for_plot,
    slab = dat$slab,

# 修正後
forest_args <- list(  
    x = res_for_plot,
    # slabはres_for_plotに既に含まれているため明示的指定不要
```

#### 2. テンプレート生成器修正

**_generate_escalc_code メソッド (1140-1144行目)**:
```python
# 修正前
escalc_call = self._safe_format(
    self.templates["escalc_binary"],
    measure=measure, ai=ai_col, bi=actual_bi_col,
    ci=ci_col, di=actual_di_col, slab_param_string=slab_param_string
)

# 修正後
escalc_call = self._safe_format(
    self.templates["escalc_binary"], 
    measure=measure, ai=ai_col, bi=actual_bi_col,
    ci=ci_col, di=actual_di_col, slab_column="slab"
)
```

### 修正効果
1. **slabベクトル長さ不整合エラーの解消**: 列名参照により自動的にデータサイズに調整
2. **サブグループ解析の安定化**: フィルタリング処理でもslab整合性を維持
3. **コードの簡素化**: 手動slabベクトル操作の削除により可読性向上

### テスト結果
- ✅ escalc(): slabが列名参照に修正済み
- ✅ rma.mh(): slabが列名参照に修正済み  
- ✅ forest(): slab明示的指定削除済み
- ✅ 問題のあるslabベクトル操作削除済み

この修正により `"length of the slab argument does not correspond to the size of the original dataset"` エラーが解消されます。

## Adding New Tests

When adding new test files:
1. Create the test file in this directory
2. Add a description to this README
3. Include clear documentation of what the test validates
4. Use descriptive function names and comments