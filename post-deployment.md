# Meta Analysis Bot - デプロイ後運用ガイド

このドキュメントは、GCP Cloud RunにMeta Analysis Botをデプロイした後の運用手順を説明します。

## 事前準備: gcloud認証とプロジェクト設定

### gcloudログイン

```powershell
# GCPアカウントにログイン
gcloud auth login
```

### プロジェクト設定

```powershell
# プロジェクトIDを設定（your-project-idは実際のプロジェクトIDに置き換え）
gcloud config set project your-project-id

# 設定確認
gcloud config list
```

**注意事項:**
- 初回実行時はブラウザが開いてGoogleアカウントでの認証が必要です
- プロジェクトIDは機密情報のため、ドキュメントには実際のIDを記載せず、実行時に適切なIDに置き換えてください

## 1. デプロイ完了後の確認

### Cloud Runサービスの確認

#### サービス一覧と状態の確認
```powershell
# デプロイされたサービスの確認
gcloud run services list --region=asia-northeast1

# 特定サービスの詳細確認
gcloud run services describe python-app --region=asia-northeast1
```

#### サービスURLの取得
```powershell
# サービスURLを取得
gcloud run services describe python-app --region=asia-northeast1 --format='value(status.url)'
```

#### 健康状態の確認
```powershell
# サービスの最新リビジョン確認
gcloud run revisions list --service=python-app --region=asia-northeast1 --limit=5

# サービスのメトリクス確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app" --limit=10 --format=json
```

### GitHub Actions デプロイ結果の確認

1. **GitHub リポジトリ**のActionsタブでデプロイ状況を確認
2. **最新のワークフロー実行**をクリックしてログを確認
3. **Deploy ステップ**が緑色（成功）になっていることを確認

デプロイ失敗時は以下を確認：
- GitHub Secrets の設定（GCP_PROJECT, GCP_WIF_PROVIDER, GCP_WIF_SERVICE_ACCOUNT）
- Workload Identity の権限設定
- Secret Manager の app-env シークレット

## 2. Slack Bot設定の最終調整

### HTTPモード設定（推奨）

Cloud Runではイベント駆動型のHTTPモードが推奨されます。

#### 1. Slack App設定でEvent Subscriptionsを有効化

1. [Slack API Apps](https://api.slack.com/apps) にアクセス
2. 対象のアプリを選択
3. 「Socket Mode」がオフになっていることを確認
3. 左側ナビゲーション「Event Subscriptions」をクリック
4. 「Enable Events」をONに設定
5. 「Request URL」に Cloud Run サービスURL + `/slack/events` を設定:
   ```
   https://python-app-xxxxxxxxx-an.a.run.app/slack/events
   ```

#### 2. Subscribe to bot events の設定

以下のイベントを追加：
- `app_mention`
- `message.channels`
- `message.groups`
- `message.im`
- `message.mpim`
- `file_shared`

#### 3. URL検証の確認

Slack が Request URL を検証できることを確認。検証に失敗する場合：
- Cloud Run サービスが正常に起動していることを確認
- `--allow-unauthenticated` フラグが設定されていることを確認
- Slack App の Signing Secret が正しく設定されていることを確認

### Socket Modeを継続する場合

Socket Mode を継続する場合はGCPのSecret Managerの環境変数で `socket_mode=true` に設定し、Event Subscriptions は無効のままにします。

## 3. 動作テスト

### 基本疎通確認

#### Slack Botの応答テスト
1. Botを含むSlackチャンネルに移動
2. `@ボットの名前 こんにちは` とメンション
3. Botからの応答があることを確認


### メタ解析機能テスト

#### 1. サンプルCSVでのテスト
1. `examples/` フォルダ内のサンプルCSVファイルをSlackチャンネルにアップロード
2. Botが自動的にCSV分析を開始することを確認
3. 分析結果とレポートが返されることを確認

#### 2. 完全な分析フローのテスト
1. 新しいCSVファイルをアップロード
2. Botとの対話でパラメータを設定
3. メタ解析の実行と結果出力を確認

#### 3. エラーハンドリングの確認
- 不正なCSVファイル（メタ解析に不適切なデータ）をアップロード
- Botが適切なエラーメッセージを返すことを確認

## 4. ログ監視とデバッグ

### Cloud Loggingの活用

#### リアルタイムログの確認
```powershell
# リアルタイムでログをストリーミング
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=python-app" --format=json

# 過去1時間のログを取得
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND timestamp>=2025-01-01T00:00:00Z" --limit=50
```

#### エラーログのフィルタリング
```powershell
# エラーレベルのログのみ表示
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND severity>=ERROR" --limit=20

# 特定の時間範囲のログ
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND timestamp>=\"$(date -d '1 hour ago' -Iseconds)\"" --limit=30
```

#### アプリケーション固有のログ
```powershell
# Slack関連のログ
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND textPayload:\"slack\"" --limit=10

# メタ解析関連のログ
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND textPayload:\"meta_analysis\"" --limit=10
```

### よくあるエラーパターンと対処法

#### 1. Slack API認証エラー
```
Error: slack_sdk.errors.SlackApiError: The request to the Slack API failed.
```
**対処法:**
- Secret Manager の `app-env` でSlackトークンを確認
- Slack App の権限（Scopes）を再確認
- Bot が正しいワークスペースにインストールされているか確認

#### 2. Gemini API制限エラー
```
Error: google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded
```
**対処法:**
- Gemini API の使用量とクォータを確認
- 一時的に使用を控えて制限解除を待つ
- 必要に応じてクォータ増加を申請

#### 3. R実行エラー
```
Error: subprocess.CalledProcessError: Command 'Rscript' returned non-zero exit status
```
**対処法:**
- Dockerコンテナ内のR環境を確認
- 必要なRパッケージ（metafor等）がインストールされているか確認
- CSVデータの形式とR解析コードの整合性を確認

#### 4. メモリ不足エラー
```
Error: Container failed to allocate memory
```
**対処法:**
```powershell
# Cloud Run サービスのメモリ制限を増加
gcloud run services update python-app --memory=2Gi --region=asia-northeast1
```

## 5. 日常運用

### 環境変数の更新

#### Secret Manager での更新手順
```powershell
# 現在のシークレット確認
gcloud secrets versions list app-env

# 新しい .env ファイルでシークレットを更新
gcloud secrets versions add app-env --data-file=.env

# サービスを再起動して新しい環境変数を反映
gcloud run services update python-app --region=asia-northeast1
```

#### よく更新される環境変数
- `SLACK_BOT_TOKEN`: Slackトークンの更新
- `GEMINI_API_KEY`: Gemini APIキーの更新
- `STORAGE_BACKEND`: ストレージバックエンドの変更
- `SOCKET_MODE`: 動作モードの切り替え

### パフォーマンス監視

#### リソース使用量の確認
```powershell
# Cloud Run サービスのメトリクス確認（過去1時間）
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app" --format=json | grep -E "(memory|cpu|request)"
```

#### レスポンス時間の監視
- GCP Console の Cloud Run セクションでメトリクスを確認
- 「リクエスト数」「レスポンス時間」「エラー率」を監視

#### スケーリング設定の調整
```powershell
# 最小・最大インスタンス数の調整
gcloud run services update python-app \
  --min-instances=1 \
  --max-instances=5 \
  --region=asia-northeast1

# CPU・メモリ制限の調整
gcloud run services update python-app \
  --cpu=2 \
  --memory=4Gi \
  --region=asia-northeast1
```

### コスト最適化

#### 使用状況の確認
```powershell
# 過去24時間のリクエスト数確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND httpRequest.requestMethod:POST" --format="table(timestamp,httpRequest.requestUrl)" --limit=100
```

#### アイドル時の最適化
- `--min-instances=0` に設定してアイドル時のコストを削減
- ただし、初回リクエスト時のコールドスタート時間が発生

## 6. トラブルシューティング

### デバッグ手順

#### 1. サービス状態の確認
```powershell
# サービスの現在状態
gcloud run services describe python-app --region=asia-northeast1 --format="value(status.conditions[0].type,status.conditions[0].status,status.conditions[0].message)"
```

#### 2. 最新のエラーログ確認
```powershell
# 最新のエラー10件
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND severity>=ERROR" --limit=10 --format=json
```

#### 3. コンテナログの詳細確認
```powershell
# 特定時間範囲のログ詳細
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=python-app AND timestamp>=\"$(date -d '10 minutes ago' -Iseconds)\"" --format=json
```

### FAQ集

#### Q: Botが応答しない
**A:** 以下を順番に確認：
1. Cloud Run サービスが起動しているか
2. Slack App の Event Subscriptions が正しく設定されているか
3. 最新のエラーログを確認
4. Slack トークンの有効性を確認

#### Q: メタ解析が実行されない
**A:** 以下を確認：
1. CSVファイルの形式がメタ解析に適しているか
2. Gemini API の使用制限に引っかかっていないか
3. R環境とmetaforパッケージの動作確認
4. 一時ファイルの作成権限があるか

#### Q: レスポンスが遅い
**A:** 以下を試行：
1. Cloud Run のCPU・メモリ制限を増加
2. `--min-instances` を1以上に設定してコールドスタートを回避
3. 大きなCSVファイルの場合は分割を提案
4. ログで処理時間のボトルネックを特定

#### Q: 費用が予想より高い
**A:** 以下で最適化：
1. `--min-instances=0` に設定
2. 不要なログレベルを削減
3. CPU・メモリ設定を最適化
4. 使用頻度の低い時間帯の制限を検討

### 緊急時対応

#### サービス停止
```powershell
# 緊急時のサービス停止
gcloud run services update python-app --region=asia-northeast1 --max-instances=0
```

#### ロールバック
```powershell
# 前のリビジョンに戻す
gcloud run services update python-app --region=asia-northeast1 --to-revisions=PREVIOUS_REVISION_NAME
```

#### 設定の初期化
```powershell
# サービスを削除して再デプロイ
gcloud run services delete python-app --region=asia-northeast1
# その後、GitHub Actions で再デプロイ
```

## 補足情報

### 関連ドキュメント
- [README.md](README.md): アプリケーション概要
- [deploy-setup.md](deploy-setup.md): 初期デプロイ手順
- [GCP Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [Slack API ドキュメント](https://api.slack.com/)

### サポート
- **GitHub Issues**: バグ報告・機能要望
- **ログ分析**: Cloud Logging でのトラブルシューティング
- **ステータス確認**: `gcloud run services describe` でのサービス状態確認

このガイドを参考に、Meta Analysis Bot の安定した運用を行ってください。
