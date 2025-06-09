# Slackデバッグボット使用方法

## 概要
メタ解析ボットをテストするためのSlackアップロードボットです。CSVファイルをアップロードまたはコードブロックとして投稿し、メタ解析ボットの動作を検証できます。

## 必要な環境変数
`.env`ファイルに以下を設定済み：
```
SLACK_UPLOAD_BOT_TOKEN=xoxb-YOUR-SLACK-UPLOAD-BOT-TOKEN
SLACK_UPLOAD_CHANNEL_ID=CXXXXXXXXXX
```

## メタ解析ボットのユーザーIDを取得
```bash
# メタ解析ボットのユーザーIDを確認
curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  https://slack.com/api/auth.test | jq -r '.user_id'
```

## 使用例

### 1. サンプルCSVをファイルとしてアップロード
```bash
# 二値アウトカムデータの例
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example binary \
  --message "オッズ比で解析してください"

# 連続アウトカムデータの例
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example continuous \
  --message "標準化平均差で解析してください"

# ハザード比データの例
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example hazard \
  --message "ハザード比のメタ解析をお願いします"

# 比率データの例
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example proportion \
  --message "比率のメタ解析をしてください"
```

### 2. CSVをコードブロックとして投稿
```bash
# コードブロック形式で投稿
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example binary \
  --codeblock \
  --message "このデータを解析してください"
```

### 3. カスタムCSVファイルを使用
```bash
# 独自のCSVファイルをアップロード
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --file ./my_data.csv \
  --message "メタ回帰分析もお願いします"
```

### 4. 異なるチャンネルでテスト
```bash
# チャンネル名を指定
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --channel test-bot-2 \
  --example binary

# チャンネルIDを直接指定
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --channel C067XYZ123 \
  --example continuous
```

## テストシナリオ

### 基本的な動作確認
1. **メンション + ファイルアップロード** → ボットが起動し解析開始
2. **メンション + コードブロック** → ボットが起動し解析開始
3. **異なる効果量タイプ** → 適切な解析タイプを自動検出

### パラメータ収集の確認
```bash
# 最小限の情報で投稿（ボットが対話的にパラメータを収集）
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example binary

# 詳細な指示を含む投稿
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --example binary \
  --message "オッズ比でランダム効果モデルを使い、地域別のサブグループ解析も実施してください"
```

### エラーハンドリングの確認
```bash
# 不正なデータでテスト（ボットのエラーメッセージを確認）
echo "invalid,data\n1,2,3" > bad_data.csv
python3 test_slack_upload.py \
  --bot-id YOUR_BOT_ID_HERE \
  --file ./bad_data.csv
```

## トラブルシューティング

### ボットが反応しない場合
1. ボットIDが正しいか確認
2. ボットがチャンネルに招待されているか確認
3. Herokuログを確認: `heroku logs --tail`

### アップロードエラーの場合
- `not_in_channel`: アップロードボットをチャンネルに招待
- `invalid_auth`: トークンを確認
- `channel_not_found`: チャンネルIDを確認

## 注意事項
- **BOT_ID**: メタ解析ボットのユーザーID（例: YOUR_BOT_ID_HERE）を正しく指定
- **環境変数**: 本番のメタ解析ボットとは別のトークンを使用
- **チャンネル**: 両方のボットが参加している必要あり
