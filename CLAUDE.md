# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
If you want to execute "sudo" commands, please ask user to execute. 

## Project Overview

This is a Meta-Analysis Slack Bot that performs statistical meta-analyses on CSV files shared in Slack channels. It uses Google Gemini AI for natural language processing (Japanese) and generates academic-quality reports in English using R's metafor package. The app is deployed in heroku.

## 満たすべき要件

### 起動条件
- ボットが存在するSlackチャンネルでCSVファイルを共有+メンションで起動
- メンションのみだと起動するがCSV共有をユーザーに依頼する
- CSV共有のみだと起動しない

### 機能要件
- ボットはCSVを分析し、適切な列が見つかった場合にメタ解析を実行
- すべてチャット内で完結させて、別のページへの遷移はしない
- コード、実行結果の図、結果を保持したRDataは添付でSlackへ、地の文で簡単な解析結果
- そのあとに解釈レポートを地の文で提供
- ユーザーは自然な日本語で分析の意図を伝える
- 結果はスレッド内に共有され、スレッド内で会話コンテキストが維持される

### 対応する解析タイプ
- **二値アウトカム**: OR (オッズ比)、RR (リスク比)、RD (リスク差)、PETO
- **連続アウトカム**: SMD (標準化平均差)、MD (平均差)、ROM (平均比)
- **ハザード比**: HR
- **単一比率**: proportion
- **発生率**: IR (incidence rate)
- **相関**: COR
- **事前計算された効果量**: yi (分散vi付き)
- **サブグループ解析**と**メタ回帰**のサポート

### エラーハンドリング
- CSV形式不正時は日本語でユーザーに通知
- R実行エラー時はGemini AIによる自動デバッグ（最大3回リトライ）
- Slackの3秒タイムアウトに対応する非同期処理
- 解析失敗時は詳細なエラーメッセージを日本語で提供

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
- ストレージバックエンド:
  - Redis（推奨）: 永続的
  - Memory: Dyno再起動まで
  - File: Dyno再起動まで（/tmpは一時的）
  - DynamoDB/Firestore: 永続的



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
# No automated tests exist - test manually by:
# 1. Upload CSV file to Slack channel with bot mention
# 2. Follow Japanese prompts to configure analysis
# 3. Verify forest plot and report generation
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
- Dialog states managed by `DialogStateManager`
- Storage backend configurable via `STORAGE_BACKEND` env var:
  - `redis` (default): Persistent storage with Redis
  - `memory`: In-memory storage (ephemeral)
  - `file`: File-based storage (uses /tmp on Heroku, ephemeral)

### R Script Generation
Templates in `r_template_generator.py` support:
- Binary outcomes (OR, RR, RD)
- Continuous outcomes (SMD, MD)
- Proportions (PRAW, PLN, PAS, etc.)
- Pre-calculated effect sizes
- Subgroup analysis and meta-regression

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
- Requires public URL for Slack events
- Configure buildpacks: `heroku/python` and `r`
- Set all environment variables in Heroku dashboard
- Add Redis addon: `heroku addons:create heroku-redis:hobby-dev`
- Redis URL automatically set as `REDIS_URL` env var

#### デプロイ手順
```bash
# Herokuにデプロイ
git add .
git commit -m "Your commit message"
git push heroku main

# ログを確認
heroku logs --tail

# 環境変数の確認
heroku config
```

### Local Development
- Uses Socket Mode (no public URL needed)
- Set `SLACK_APP_TOKEN` in `.env`
- Easier for testing and debugging

## Testing Guide

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