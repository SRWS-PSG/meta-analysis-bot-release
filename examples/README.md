# サンプルファイル

このディレクトリには、メタ解析ボットのテスト用のサンプルファイルが含まれています。

## 対応ファイル形式

ボットは以下のファイル形式に対応しています：
- **CSV** ファイル (.csv)
- **Excel** ファイル (.xlsx, .xls)

## CSVファイル

### example_meta_data.csv
基本的な事前計算済み効果量データ：
- `study`: 研究の名前または識別子
- `yi`: 効果量（effect size）
- `vi`: 分散（variance）
- `n`: サンプルサイズ

### example_binary_meta_dataset.csv
二値アウトカムのメタ解析用データ：
- `Study`: 研究名
- `Intervention_Events`: 介入群のイベント数
- `Intervention_Total`: 介入群の総数
- `Control_Events`: 対照群のイベント数
- `Control_Total`: 対照群の総数

### example_continuous_meta_dataset.csv
連続アウトカムのメタ解析用データ：
- `Study`: 研究名
- `Intervention_Mean`: 介入群の平均値
- `Intervention_SD`: 介入群の標準偏差
- `Intervention_N`: 介入群のサンプルサイズ
- `Control_Mean`: 対照群の平均値
- `Control_SD`: 対照群の標準偏差
- `Control_N`: 対照群のサンプルサイズ

## XLSXファイル

### example_binary_meta_dataset.xlsx
二値アウトカム用のExcelファイル（CSVと同じ構造）

### example_continuous_meta_dataset.xlsx
連続アウトカム用のExcelファイル（CSVと同じ構造）

### example_pre_calculated_effect_sizes.xlsx
事前計算済み効果量用のExcelファイル：
- `Study`: 研究名
- `Effect_Size`: 効果量
- `Standard_Error`: 標準誤差
- `Sample_Size`: サンプルサイズ

## 使用方法

1. いずれかのファイルをSlackチャンネルにアップロード
2. ボットをメンション (@botname)
3. ボットが自動的にファイルを検出・処理し、メタ解析を実行

ボットは自動的にファイル形式を検出し、XLSXファイルを内部的にCSV形式に変換して処理します。
