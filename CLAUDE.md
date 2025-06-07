# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
If you want to execute "sudo" commands, please ask user to execute. 

## Project Overview

This is a Meta-Analysis Slack Bot that performs statistical meta-analyses on CSV files shared in Slack channels. It uses Google Gemini AI for natural language processing (Japanese) and generates academic-quality reports in English using R's metafor package. The app is deployed in heroku.

## お願い
- テスト、デバッグのために使うコードは、すべて test/ の中に入れてレポジトリを汚さないこと。あと、test/ 内のreadmeに何をするファイルなのかの説明を入れること
- secretは.envに入れる。ハードコードはしない。
- herokuへのデプロイには5分かかる

## ボットが満たすべき要件

### 起動条件
- ボットが存在するSlackチャンネルでCSVファイルを共有+メンションで起動
- メンション+CSVデータをコードブロックで投稿しても起動
- メンションのみだと起動するがCSV共有をユーザーに依頼する
- CSV共有のみだと起動しない（file_sharedイベントは監視しない）

### 機能要件
- ボットはCSVを分析し、適切な列が見つかった場合にメタ解析を実行
- 列が適切であるか、ユーザーが何をしたいかはGemini APIを使いながらユーザーと対話してコンテキストをうめる
- コンテキストが十分に溜まったら、その内容で良いか、ユーザーに承認をもらってからメタ解析を実行
- すべてチャット内で完結させて、別のページへの遷移はしない
- コード、実行結果の図、結果を保持したRDataは添付でSlackへ、地の文で簡単な解析結果
- そのあとに解釈レポートを地の文で提供
- 結果はスレッド内に共有され、スレッド内で会話コンテキストが維持される
- **パラメータ収集はGemini AIが対話的に行い、キーワードマッチングは使用しない**
- **Geminiが会話の文脈を理解し、必要な情報が揃うまで適切な質問を続ける**
- **Gemini Function Callingを使用してパラメータを構造化データとして抽出**
- **CSV列の自動マッピング（効果量タイプの自動検出を含む）**
- **ログ変換データの自動検出**
- 十分なコンテキストがそろったら、それを元にRのコードを作り、実行
- 戻り値の図、データを返す
- **英語の学術論文形式（Methods (statistical analysis)・Results）のレポートを生成**
- **レポートの日本版も提供**
- **解析環境情報（Rバージョン、metaforバージョン）の記録**

### 対応する解析タイプ
- **二値アウトカム**: OR (オッズ比)、RR (リスク比)、RD (リスク差)、PETO
- **連続アウトカム**: SMD (標準化平均差)、MD (平均差)、ROM (平均比)
- **ハザード比**: HR（ログ変換データの自動検出対応）
- **単一比率**: PLO、PR、PAS、PFT、PRAW
- **発生率**: IR (incidence rate)、IRLN、IRS、IRFT
- **相関**: COR（相関係数）
- **事前計算された効果量**: yi (分散vi付き)
- **サブグループ解析**（統計的検定付き）
- **メタ回帰**（複数のモデレータ対応）
- **感度分析**（フィルタリング条件付き）

### エラーハンドリング
- CSV形式不正時は日本語でユーザーに通知
- R実行エラー時はGemini AIによる自動デバッグ（最大3回リトライ）
- **エラーパターンマッチングによる具体的な修正提案**
- **指数バックオフによるリトライ機構**
- Slackの3秒タイムアウトに対応する非同期処理
- 解析失敗時は詳細なエラーメッセージを日本語で提供
- **異なるエラータイプに応じた専用エラーハンドラー**

### セキュリティ・権限要件
- Slackワークスペースのメンバーであれば誰でも利用可能
- プライベートチャンネルでも動作（ボットが招待されている場合）
- 環境変数による認証情報の保護
- 一時ファイルは処理後に自動削除

### パフォーマンス要件
- ファイルサイズ制限: 明示的な制限なし（メモリ依存）
- 同時実行可能な解析数: 5（ThreadPoolExecutorのデフォルト）
- レスポンス時間: 初回応答は3秒以内、解析完了は非同期

### データ保持
- コンテキスト保持期間: 48時間（環境変数で設定可能）
- 会話履歴: 最大20メッセージ（環境変数で設定可能）
- **非同期ジョブのステータス追跡**
- ストレージバックエンド（`STORAGE_BACKEND`環境変数で設定）:
  - Redis（デフォルト）: 永続的、`REDIS_URL`環境変数で接続
  - Memory: Dyno再起動まで（Heroku Eco Dynos向け）
  - File: Dyno再起動まで（/tmpは一時的）
  - DynamoDB: 永続的、AWSクレデンシャル必要



## Essential Commands

### Local Development
```bash
# Build and run with Docker
docker build -t meta-analysis-bot .
docker run --env-file .env meta-analysis-bot

# Run without Docker
python main.py

# Install Python dependencies
pip install -r requirements.txt
```

### Docker Debugging
```bash
# Find container ID
docker ps -a

# View logs
docker logs [CONTAINER_ID]

# List files inside container
docker exec [CONTAINER_ID] ls -la /app/

# Copy files from container
docker cp [CONTAINER_ID]:/app/filename.ext ./filename.ext
```

### Testing & Development
```bash
# 対話型テスト（推奨）
cd tests/
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "オッズ比で解析してください"

# ユーザー応答をシミュレート（ボットの質問に対して）
python3 send_message.py --message "<@U08TKJ1JQ77> はい、ランダム効果モデルでお願いします" --thread "スレッドTS"

# 対話状況の確認（30秒待機後にボット応答を確認）
python3 debug_channel_messages.py

# 待機時間を短縮する場合
python3 debug_channel_messages.py --wait 10

# チャンネル参加状況の確認
python3 check_channels.py

# Manual testing steps:
# 1. test_slack_upload.py でCSVファイル+メンションを投稿
# 2. ボットの応答を確認（CSV分析結果と最初の質問）
# 3. send_message.py でユーザー応答をシミュレート
# 4. 対話が完了するまで継続
# 5. 最終的な解析結果とレポート生成を確認
```

## Natural Language Parameter Collection

The bot uses Gemini AI for intelligent parameter collection through natural conversation:

### How it works
1. **No Button UI**: After CSV analysis, the bot immediately starts a natural language conversation
2. **Context-Aware Dialogue**: Gemini maintains conversation history and understands context
3. **Continuous Collection**: Gemini continues asking questions until all required parameters are collected
4. **No Keyword Matching**: The system doesn't rely on simple keyword matching - it understands intent

### Key Components
- `utils/gemini_dialogue.py`: Orchestrates the Gemini-driven conversation
- `utils/conversation_state.py`: Maintains thread-specific conversation state
- `handlers/parameter_handler.py`: Handles message events and coordinates with Gemini

### Example Flow
```
User: @bot [uploads CSV]
Bot: CSVファイルを分析しました！
     データセット概要:
     • 研究数: 15件
     • 効果量候補: Intervention_Events, Control_Events (二値アウトカム)
     • 推奨効果量: OR（オッズ比）
     • サブグループ候補: Region, Year
     
     解析パラメータを自然な日本語で教えてください。例：「オッズ比でランダム効果モデルを使って解析して」

User: オッズ比で、地域別のサブグループ解析もお願い
Bot: 承知しました！オッズ比で解析し、地域別のサブグループ解析も行います。
     統計モデルはランダム効果モデルと固定効果モデルのどちらを使用しますか？

User: ランダムで
Bot: ランダム効果モデルで解析を行います。
     
     収集したパラメータ:
     • 効果量: OR（オッズ比）
     • モデル: ランダム効果モデル（REML）
     • サブグループ: Region
     
     解析を開始します...

[数秒後]
Bot: 📊 メタ解析が完了しました！
     
     【解析結果サマリー】
     • 統合オッズ比: 1.45 (95% CI: 1.12-1.88), p=0.005
     • 異質性: I²=45.2%, Q-test p=0.032
     • サブグループ解析: 地域間で有意差あり (p=0.018)
     
     [ファイル添付: forest_plot.png, funnel_plot.png, analysis.R, results.RData]
```

## Architecture

The bot follows an event-driven architecture:

1. **Entry Point**: `main.py` - Handles both HTTP mode (Heroku) and Socket mode (local)
2. **Core Orchestrator**: `mcp/slack_bot.py` - Manages component lifecycle
3. **Key Components**:
   - `message_handlers.py`: Routes Slack events
   - `csv_processor.py`: Analyzes CSV compatibility with Gemini
   - `parameter_collector.py`: Extracts parameters from Japanese text
   - `analysis_executor.py`: Runs R scripts asynchronously
   - `report_generator.py`: Creates academic reports

## Critical Implementation Details

### Security
- This is an OPEN repository - NEVER commit secrets
- All credentials must be in `.env` file (gitignored)
- Environment variables: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`, `GEMINI_API_KEY`

### Gemini Function Calling Pattern
When implementing Gemini function calling with enums, avoid None values:
```python
# WRONG - causes pydantic validation errors
class AnalysisType(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SENSITIVITY = "sensitivity_analysis"
    NONE = None  # Don't do this!

# CORRECT
class AnalysisType(str, Enum):
    META_ANALYSIS = "meta_analysis"
    SENSITIVITY = "sensitivity_analysis"
    NOT_SPECIFIED = "not_specified"
```

### Async Processing
The bot uses `AsyncAnalysisRunner` to handle Slack's 3-second timeout:
- Initial response sent immediately
- Analysis runs in background
- Results posted to thread when complete

### State Management
- Uses `ThreadContextManager` for conversation persistence
- Dialog states managed by `DialogStateManager`:
  - `waiting_for_file`: CSVファイル待機中
  - `processing_file`: CSVファイル処理中
  - `analysis_preference`: パラメータ収集中
  - `analysis_running`: 解析実行中
  - `post_analysis`: 解析完了後
- Storage backend configurable via `STORAGE_BACKEND` env var:
  - `redis` (default): Persistent storage with Redis
  - `memory`: In-memory storage (ephemeral)
  - `file`: File-based storage (uses /tmp on Heroku, ephemeral)
  - `dynamodb`: AWS DynamoDB (persistent)

### R Script Generation
Templates in `r_template_generator.py` support:
- Binary outcomes (OR, RR, RD, PETO)
- Continuous outcomes (SMD, MD, ROM)
- Proportions (PLO, PR, PAS, PFT, PRAW)
- Incidence rates (IR, IRLN, IRS, IRFT)
- Hazard ratios with log transformation detection
- Correlations (COR)
- Pre-calculated effect sizes (yi/vi)
- Subgroup analysis with statistical tests (Q-test)
- Meta-regression with multiple moderators
- Dynamic plot sizing based on study count
- Comprehensive JSON output with all statistics
- Multiple plot types (forest, funnel, bubble)

## Common Development Tasks

### Adding New Analysis Types
1. Update `AnalysisType` enum in `parameter_collector.py`
2. Add R template in `r_template_generator.py`
3. Update Gemini prompts in `prompts.json`
4. Test with example CSV in `examples/`

### Debugging R Script Errors
The bot uses Gemini for self-debugging:
1. R errors are captured in `analysis_executor.py`
2. Sent to Gemini with script and data context
3. Gemini suggests fixes which are automatically applied
4. Maximum 3 retry attempts

### Modifying Gemini Prompts
All prompts stored in `mcp/cache/prompts.json`:
- `csv_analysis`: Initial CSV compatibility check
- `parameter_extraction`: Extract parameters from Japanese
- `r_script_debugging`: Fix R script errors
- `report_generation`: Create academic reports

## Deployment Notes

### Heroku (Production)
- Uses HTTP mode with event subscriptions
- Requires public URL for Slack events: `https://<app-name>.herokuapp.com/slack/events`
- Configure buildpacks: `heroku/python` and `r`
- Set all environment variables in Heroku dashboard
- Add Redis addon: `heroku addons:create heroku-redis:hobby-dev`
- Redis URL automatically set as `REDIS_URL` env var
- **Note**: For Heroku Eco Dynos, recommend `STORAGE_BACKEND=memory` to avoid Redis costs
- **R buildpack**: Automatically installs R and metafor package
- **Temporary files**: Use `/tmp/` directory (cleared on dyno restart)

#### デプロイ手順
```bash
# Herokuにデプロイ（変更を反映するには必須）
git add .
git commit -m "Your commit message"
git push heroku main

# GitHubへのプッシュ（バックアップ・バージョン管理用）
git push origin main

# ログを確認
heroku logs --tail

# 環境変数の確認
heroku config
```

**重要**: コード変更を本番環境に反映するには、Githubへのpushが必要です。

### Local Development
- Uses Socket Mode (no public URL needed)
- Set `SLACK_APP_TOKEN` in `.env`
- Easier for testing and debugging

## Testing Guide

### 対話型テストの実行手順

#### 1. 初期セットアップ
```bash
cd tests/
# 環境変数が設定されていることを確認
python3 check_channels.py
```

#### 2. 基本的な対話テスト
```bash
# Step 1: CSVファイル+メンションを投稿（test-messengerボット使用）
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "オッズ比で解析してください"

# Step 2: ボットの応答確認（meta-analysis-botからの質問）
python3 debug_channel_messages.py

# Step 3: ユーザー応答をシミュレート（スレッド内でメンション必須）
python3 send_message.py --message "<@U08TKJ1JQ77> はい、ランダム効果モデルでお願いします" --thread "THREAD_TS_FROM_STEP1"

# Step 4: 対話継続（必要に応じて繰り返し）
python3 send_message.py --message "<@U08TKJ1JQ77> 地域別のサブグループ解析もお願いします" --thread "THREAD_TS"

# Step 5: 最終結果確認
python3 debug_channel_messages.py
```

#### 3. 異なる解析タイプのテスト
```bash
# 連続アウトカムデータ
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example continuous --message "標準化平均差で解析してください"

# 比率データ
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example proportion --message "比率データの解析をお願いします"

# ハザード比データ
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example hazard_ratio --message "ハザード比で解析してください"
```

#### 4. 複雑な対話シナリオのテスト
```bash
# 曖昧な要求のテスト
python3 test_slack_upload.py --bot-id U08TKJ1JQ77 --example binary --message "普通に解析して"
# → ボットが適切な質問を生成するかテスト

# 段階的な要求変更のテスト
python3 send_message.py --message "<@U08TKJ1JQ77> やっぱり固定効果モデルで" --thread "THREAD_TS"
# → 途中での変更要求に対応するかテスト
```

### 起動条件のテスト

1. **メンション＋CSVファイル添付**
   ```
   @bot [CSVファイルを添付]
   → ✅ ボットが起動し、CSV分析を開始
   ```

2. **メンション＋CSVデータ（コードブロック）**
   ````
   @bot
   ```
   Study,Effect_Size,SE
   Study1,0.5,0.1
   Study2,0.8,0.15
   ```
   ````
   → ✅ ボットが起動し、CSV分析を開始

3. **メンションのみ**
   ```
   @bot
   → ✅ ボットが起動し、CSV共有を依頼
   ```

4. **CSV共有のみ（メンションなし）**
   ```
   [CSVファイルを添付]
   → ❌ ボットは起動しない（仕様通り）
   ```

### 対話テストの確認ポイント

#### ✅ 正常動作の確認項目
1. **初回応答**: CSV分析結果が3秒以内に投稿される
2. **質問生成**: データに適した質問が日本語で投稿される  
3. **文脈理解**: ユーザーの曖昧な回答を適切に解釈する
4. **対話継続**: 必要な情報が揃うまで質問を続ける
5. **パラメータ確認**: 収集した情報を最終確認する
6. **解析実行**: 承認後に解析が非同期で開始される
7. **結果投稿**: 図、コード、レポートが添付される

#### 🔍 デバッグが必要な症状
1. **ボット無応答**: test-messengerの投稿に全く反応しない
2. **スレッド対話失敗**: スレッド内メンションに応答しない
3. **対話ループ**: 同じ質問を繰り返す
4. **パラメータ未抽出**: ユーザー応答を理解できない
5. **解析未開始**: パラメータ収集後に解析が始まらない

#### 🛠️ デバッグ手順
```bash
# 1. Herokuログでエラー確認
heroku logs --tail --app=meta-analysis-bot | grep -E "(ERROR|Exception|Failed)"

# 2. 会話状態の確認
heroku logs --app=meta-analysis-bot | grep -E "(conversation.*state|DialogState)" | tail -10

# 3. 非同期ジョブの状況確認
heroku logs --app=meta-analysis-bot | grep -E "(Job ID|parameter.*collection)" | tail -10

# 4. Gemini API呼び出しの確認
heroku logs --app=meta-analysis-bot | grep -E "(Gemini|Function.*call)" | tail -10
```

### トラブルシューティング

1. **CSVデータが検出されない場合**
   - rich_textブロックでコードブロックとして投稿されているか確認
   - 最低2行以上、2列以上のデータが必要
   - カンマ、タブ、または複数スペースで区切られている必要がある

2. **ボットが反応しない場合**
   - Herokuログで`App mention received`が記録されているか確認
   - ボットがチャンネルに招待されているか確認
   - 環境変数が正しく設定されているか確認

3. **エラーが発生する場合**
   ```bash
   # Herokuログで詳細を確認
   heroku logs --tail --app=your-app-name
   
   # 特定の時間帯のログを確認
   heroku logs --since "2024-01-01T00:00:00Z" --until "2024-01-01T01:00:00Z"
   ```

## Advanced AI Features

### Gemini AI Integration
The bot leverages Google Gemini AI for sophisticated natural language processing:

1. **CSV Analysis & Column Mapping**
   - Automatic detection of meta-analysis compatible columns
   - Intelligent mapping of CSV columns to metafor parameters
   - Effect size type auto-detection from column names
   - Log transformation detection for hazard ratios

2. **Parameter Collection**
   - Continuous dialogue using Gemini Function Calling
   - Context-aware conversation management
   - No reliance on keyword matching
   - Structured parameter extraction to Pydantic models

3. **R Script Generation & Debugging**
   - Dynamic R script generation based on parameters
   - Self-debugging with error pattern recognition
   - Up to 3 automatic retry attempts with fixes
   - Comprehensive error analysis and resolution

4. **Report Generation**
   - Academic paper format (Methods & Results sections)
   - Bilingual output (English primary, Japanese summary)
   - Statistical interpretation and clinical significance
   - Analysis environment documentation

5. **Advanced Features**
   - Multi-turn conversation with context retention
   - Handling of ambiguous user inputs
   - Intelligent question generation for missing parameters
   - Support for complex analysis requests

## Important Patterns

### Error Handling
- All user-facing errors in Japanese
- Technical errors logged in English
- Gemini-assisted debugging for R scripts

### File Processing
- CSV files downloaded from Slack to `/tmp/`
- Cleaned up after processing
- Local paths used directly (no GCS upload)

### Thread Management
- All bot responses in threads
- Context maintained per thread
- Avoids infinite loops with bot message detection

## CSV読み込み〜解析実施までの修正履歴とアンチパターン

### 2025年6月6日の修正内容

#### 1. 解析結果の表示でN/A値が表示される問題
**問題**: メタ解析完了後、結果サマリーで統合効果量や信頼区間が "N/A" と表示される
```
**【解析結果サマリー】**
• 統合効果量: N/A
• 95%信頼区間: N/A - N/A
• 異質性: I²=N/A%
• 研究数: N/A件
```

**原因**: `utils/slack_utils.py`の`create_analysis_result_message`関数でRスクリプトの出力フィールド名との不整合

**Rスクリプトの実際の出力**:
```json
{
  "overall_analysis": {
    "k": 10,
    "estimate": 1.45,
    "ci_lb": 1.12,
    "ci_ub": 1.88,
    "I2": 45.2
  }
}
```

**修正**: 正しいフィールド名の使用 (`utils/slack_utils.py:97-133`)
```python
# Before (間違い)
pooled_effect = summary.get('pooled_effect', summary.get('estimate', 'N/A'))
ci_lower = summary.get('ci_lower', summary.get('ci_lb', 'N/A'))
num_studies = summary.get('num_studies', 'N/A')

# After (修正済み)
pooled_effect = summary.get('estimate', 'N/A')  # Rが出力する実際のフィールド名
ci_lower = summary.get('ci_lb', 'N/A')          # Rが出力する実際のフィールド名  
num_studies = summary.get('k', 'N/A')           # Rが出力する実際のフィールド名
```

**コミット**: fb57b9a (2025-01-06)

#### 2. CSV列検出で効果量候補が「検出されませんでした」と表示される問題
**問題**: CSV分析で研究数は正確に検出されるが、効果量候補列や分散候補列が「検出されませんでした」と表示される
```
• 研究数: 10件
• 効果量候補列: 検出されませんでした  ← 問題
• 分散/SE候補列: 検出されませんでした  ← 問題
• 研究ID候補列: Study
• 推奨効果量: OR
```

**原因**: Geminiのプロンプトが不十分で、二値アウトカムデータ（イベント数/総数）を適切に識別できていなかった

**CSV実際のデータ例**:
```csv
Study,Intervention_Events,Intervention_Total,Control_Events,Control_Total
Study 1,15,48,10,52
Study 2,22,55,18,58
```

**修正**: 
1. Geminiプロンプトを改善して詳細なデータタイプ識別を実装
2. 二値・連続・事前計算済みデータを明確に分類
3. 新しい列分類システムの導入

**修正後のGeminiプロンプト** (`core/gemini_client.py:55-70`):
```json
"detected_columns": {
  "binary_intervention_events": ["介入群のイベント数列"],
  "binary_control_events": ["対照群のイベント数列"],
  "binary_intervention_total": ["介入群の総数列"],
  "binary_control_total": ["対照群の総数列"],
  "effect_size_candidates": ["事前計算済み効果量列"],
  "variance_candidates": ["分散/標準誤差列"]
}
```

**表示の改善** (`utils/slack_utils.py:22-48`):
```python
# データタイプ別に候補を表示
if binary_intervention_events:
    data_type_info.append(f"二値アウトカム: {', '.join(binary_candidates)}")
if effect_candidates:
    data_type_info.append(f"事前計算済み効果量: {', '.join(effect_candidates)}")
```

**コミット**: 4dfb6bb (2025-01-06)

#### 3. Redis SSL証明書エラー
**問題**: Heroku RedisのSSL接続で証明書検証エラーが発生
```
Failed to initialize Redis: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

**原因**: Heroku Redisは自己署名証明書を使用しており、デフォルトのRedis接続では検証に失敗する

**修正**: `utils/conversation_state.py`でSSL証明書検証をバイパス
```python
if redis_url.startswith('rediss://'):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    _storage_backend = redis.from_url(
        redis_url, 
        decode_responses=True,
        ssl_cert_reqs=None,
        ssl_check_hostname=False
    )
```

#### 2. 関数インポートエラー
**問題**: `handle_natural_language_parameters`関数がインポートできない
```
cannot import name 'handle_natural_language_parameters' from 'handlers.parameter_handler'
```

**原因**: 関数が別の関数内に定義されていたため、モジュールレベルでインポートできなかった

**修正**: `handlers/parameter_handler.py`で関数をモジュールレベルに移動

#### 3. DialogState列挙型の比較エラー
**問題**: 会話状態の比較で文字列と列挙型を混在させていた
```python
# 誤り
if state.state == "analysis_preference":

# 正しい
from utils.conversation_state import DialogState
if state.state == DialogState.ANALYSIS_PREFERENCE:
```

#### 4. Slack 3秒タイムアウト対応
**問題**: Slackイベントハンドラーが即座にACKを返さず、タイムアウトが発生

**修正**: すべてのイベントハンドラーに`ack()`を追加
```python
@app.event("message")
def handle_direct_message(body, event, client, logger, ack):
    ack()  # 即座にACKを返す
    # 処理を続行...
```

#### 5. スレッドメッセージ検出の改善
**問題**: DMまたは直接返信のみを処理し、スレッド内の他のメッセージを無視していた

**修正**: スレッド参加者のメッセージも処理するようロジックを拡張
```python
has_thread_ts = "thread_ts" in event
if channel_type == "im" or is_thread_message or has_thread_ts:
```

### デバッグに関して
別にSLACK_UPLOAD_BOT_TOKEN,SLACK_UPLOAD_CHANNEL_IDで指定されたボットを作っているので、それをSlack API経由で投稿して、実際のmeta-analysis-botがうまく動いているかを検証できるようにする

### テストファイルの詳細
全てのテスト・デバッグファイルは`tests/`ディレクトリに整理されており、詳細な説明は`tests/README.md`を参照。

#### 主要テストツール
- **test_slack_upload.py**: CSVファイル+メンション投稿（test-messengerボット使用）
- **send_message.py**: ユーザー応答シミュレート（スレッド内メンション対応）  
- **debug_channel_messages.py**: チャンネル履歴確認とボット応答状況の診断
- **check_channels.py**: ボットのチャンネル参加状況と権限確認

#### 環境変数要件
```bash
# .envファイルに以下を設定
SLACK_BOT_TOKEN=xoxb-meta-analysis-bot-token
SLACK_UPLOAD_BOT_TOKEN=xoxb-test-messenger-token  
SLACK_UPLOAD_CHANNEL_ID=C066EQ49QVD
GEMINI_API_KEY=your-gemini-key
```


### アンチパターン集

1. **ストレージバックエンドの不一致**
   - ❌ `STORAGE_BACKEND=memory`なのにRedis URLを設定
   - ✅ Redis使用時は`STORAGE_BACKEND=redis`に設定

2. **非同期処理の誤り**
   - ❌ Slackイベントで時間のかかる処理を同期的に実行
   - ✅ 即座に`ack()`して、重い処理は非同期で実行

3. **型の不一致**
   - ❌ 列挙型と文字列を直接比較
   - ✅ 適切な型変換または列挙型を使用した比較

4. **関数のスコープ**
   - ❌ インポートが必要な関数を別の関数内に定義
   - ✅ モジュールレベルで関数を定義

5. **SSL接続の処理**
   - ❌ Heroku Redisの自己署名証明書をデフォルト設定で接続
   - ✅ SSL証明書検証を適切に設定

### 今後の開発時の注意点

1. **ログの重要性**: エラー発生時は必ず`heroku logs --tail`で詳細を確認
2. **環境変数の確認**: `heroku config`で設定値の整合性を確認
3. **イベントハンドラー**: 必ず最初に`ack()`を呼び出す
4. **型の一貫性**: 列挙型を使用する場合は全体で統一
5. **Redis接続**: Heroku RedisはSSL必須、証明書検証の設定が必要