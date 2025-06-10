# サンプルファイル

このディレクトリには、メタ解析ボットのテスト用のサンプルファイルが含まれています。

## データ形式別サンプル

### 二値アウトカム（2×2表形式）
- **example_binary_meta_dataset.csv**: イベント数/総数形式の二値アウトカムデータ
  - 効果量: OR, RR, RD, PETO
  - 列: Study, Intervention_Events, Intervention_Total, Control_Events, Control_Total

### OR/RRと信頼区間形式（新機能）
- **example_or_ci_meta_dataset.csv**: オッズ比と信頼区間のデータ
  - 効果量: OR（自動的にlnORとSEに変換）
  - 列: Study, Author, Year, OR, CI_Lower, CI_Upper, Region, Quality
  
- **example_rr_ci_meta_dataset.csv**: リスク比と信頼区間のデータ
  - 効果量: RR（自動的にlnRRとSEに変換）
  - 列: Study, Author, Year, RR, Lower_CI, Upper_CI, Treatment_Type, Sample_Size

### 連続アウトカム
- **example_continuous_meta_dataset.csv**: 平均値と標準偏差のデータ
  - 効果量: SMD, MD, ROM
  - 列: Study, n1i, n2i, m1i, m2i, sd1i, sd2i

### ハザード比
- **example_hazard_ratio_meta_dataset.csv**: 対数ハザード比と標準誤差
  - 効果量: HR（対数変換済み）
  - 列: Study, log_hr, se_log_hr

### 単一群比率
- **example_proportion_meta_dataset.csv**: イベント数と総数
  - 効果量: PLO, PR, PAS, PFT, PRAW
  - 列: Study, Events, Total

### 事前計算済み効果量
- **example_meta_data.csv**: 効果量と分散が事前計算済み
  - 効果量: yi（任意の効果量）
  - 列: study, yi, vi, n

### メタ回帰用データ
- **example_meta_regression_data.csv**: メタ回帰分析用のモデレーター変数付き
  - 効果量: SMD
  - 列: Study, yi, vi,年度, 地域, 平均年齢（モデレーター）

## 使用方法

これらのサンプルファイルは、`tests/test_slack_upload.py`で使用できます：

```bash
# OR + CI形式のテスト
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example or_ci --message "オッズ比で解析してください"

# RR + CI形式のテスト  
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example rr_ci --message "リスク比で解析してください"

# 二値アウトカムのテスト
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example binary --message "オッズ比で解析してください"

# 連続アウトカムのテスト
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example continuous --message "標準化平均差で解析してください"
```

新しいOR/CI機能では、ORと信頼区間の列が自動的に検出され、Rスクリプト内で対数スケールに変換されます。
