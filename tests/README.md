# テスト・デバッグファイル説明

このディレクトリには、メタ解析ボットのテストとデバッグ用のファイルが含まれています。

## 対話テスト・デバッグファイル

### `test_version_info_debug.py`
- **目的**: バージョン情報（R version、metafor version）が解釈レポートに正しく表示されるかをテスト
- **使用方法**: `python3 test_version_info_debug.py`
- **機能**: CSVファイルをアップロード、解析実行、最終レポートでバージョン情報の有無を確認

### `test_slack_upload.py`
- **目的**: test-messengerボットを使用してCSVファイル+メンションを投稿し、meta-analysis-botの応答をテスト
- **使用方法**: `python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example binary --message "オッズ比で解析してください"`
- **機能**: examplesディレクトリのCSVファイルを自動アップロード、メンション付きメッセージ送信

### `send_message.py`
- **目的**: 特定チャンネル・スレッドにメッセージを送信（対話テスト用）
- **使用方法**: `python3 send_message.py --message "応答メッセージ" --thread "スレッドTS"`
- **機能**: ユーザー応答をシミュレートして対話フローをテスト

### `debug_channel_messages.py`
- **目的**: 指定チャンネルのメッセージ履歴を確認し、ボットの応答状況をデバッグ
- **使用方法**: `python3 debug_channel_messages.py` または `python3 debug_channel_messages.py --wait 10`
- **機能**: ボット応答を待機（デフォルト30秒）してから、過去1時間のメンション・ボット応答を表示、対話状況を分析
- **オプション**: `--wait N` でボット応答待機時間をN秒に変更可能

### `check_channels.py`
- **目的**: ボットのチャンネル参加状況と権限を確認
- **使用方法**: `python3 check_channels.py`
- **機能**: アクセス可能チャンネル一覧、権限エラーの診断

## 単体テストファイル

### `test_csv_processing.py`
- **目的**: CSV処理機能の単体テスト
- **機能**: CSV読み込み、列検出、データ形式検証

### `test_gemini.py`
- **目的**: Gemini AI統合のテスト
- **機能**: API接続、パラメータ抽出、応答解析

### `test_r_template_generation.py`
- **目的**: Rスクリプト生成機能のテスト
- **機能**: 各解析タイプのテンプレート生成、パラメータマッピング

### `test_analysis_execution.py`
- **目的**: 解析実行プロセスのテスト
- **機能**: 非同期処理、エラーハンドリング、結果処理

### `test_state_management.py`
- **目的**: 会話状態管理のテスト
- **機能**: Redis/メモリ状態の保存・復元、タイムアウト

### `test_natural_language_collection.py`
- **目的**: 自然言語パラメータ収集のテスト
- **機能**: Gemini対話フロー、パラメータ抽出精度

### `test_error_handling.py`
- **目的**: エラーハンドリングとリトライ機構のテスト
- **機能**: 各種エラーパターンの処理、自動修正

## 詳細デバッグファイル

### `comprehensive_r_test.py`
- **目的**: R実行環境の包括的テスト
- **機能**: metaforパッケージ、全解析タイプの動作確認

### `detailed_test_r_template.py`
- **目的**: Rテンプレート生成の詳細テスト
- **機能**: 各効果量タイプ、複雑なパラメータ組み合わせ

### `debug_event_structure.py`
- **目的**: Slackイベント構造のデバッグ
- **機能**: 受信イベントの詳細ログ、構造解析

### `debug_heroku.py`
- **目的**: Heroku環境固有問題のデバッグ
- **機能**: 環境変数、ログ、メモリ使用量確認

### `test_startup_conditions.py`
- **目的**: アプリ起動条件のテスト
- **機能**: 各種起動シナリオ、初期化プロセス

### `test_metadata_manager.py`
- **目的**: メタデータ管理機能のテスト
- **機能**: Slackメッセージのメタデータ処理

## 実行方法

### 単発テスト
```bash
# 対話テスト（最も重要）
python3 tests/test_slack_upload.py --bot-id YOUR_BOT_ID --example binary
python3 tests/send_message.py --message "@YOUR_BOT_ID はい、お願いします" --thread "スレッドTS"

# デバッグ
python3 tests/debug_channel_messages.py
python3 tests/check_channels.py
```

### 包括テスト
```bash
# 全単体テスト実行
cd tests && python3 -m pytest *.py

# 特定機能のテスト
python3 tests/test_gemini.py
python3 tests/comprehensive_r_test.py
```

## 注意事項

- 本番環境への影響を避けるため、テストは専用のテストチャンネルで実行
- APIキーなどの機密情報は`.env`ファイルから読み込み
- テスト実行前に必要な環境変数が設定されていることを確認
- 長時間実行されるテストは適切にタイムアウト設定を行う