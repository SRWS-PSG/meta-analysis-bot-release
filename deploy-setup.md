# Meta Analysis Bot - GCP Cloud Run デプロイ手順書

このドキュメントは、Meta Analysis BotをGCP Cloud Runに自動デプロイCI/CDパイプラインと共にセットアップする手順を説明します。

## 事前準備

1.  **Google Cloud SDK (gcloud CLI) のインストール**: [インストールガイド](https://cloud.google.com/sdk/docs/install)
2.  **GitHub リポジトリ**: アプリケーションのコードがホストされていること。
3.  **必要な認証情報**:
    *   Slack Bot Token
    *   Slack Signing Secret
    *   Slack App Token (Socket Mode用)
    *   Gemini API Key

## 手順




### 1. GCPプロジェクトのセットアップ(ユーザーが手でやる)
1. GCP プロジェクトを作成
ブラウザで https://console.cloud.google.com/ にログインし、右上の「プロジェクト選択」をクリック。

ダイアログの右上 ［新しいプロジェクト］ を押す。

「プロジェクト名」を入力（あとで変更可）し、請求先アカウントと組織／フォルダを確認して ［作成］。

右上の通知ベル → 「プロジェクトが作成されました」をクリックして新プロジェクトに切り替わったことを確認。

プロジェクト ID（例: my-app-123456）は後の GitHub Secrets で使うのでメモしておく。

2. 課金を有効化
左側ナビ ［お支払い］ → ［アカウント管理］。

「リンクされていません」と表示されていれば ［課金アカウントをリンク］ → 使用するクレジットカードを選択 → ［設定］。

テーブルが「リンク済み」になれば完了。


# 以降はターミナルで実行可能なので、Claudeに依頼すると良い

## ⚠️ Windows環境での注意事項
1. **PowerShellを使用してください** (コマンドプロンプトではなく)
2. **gcloudコマンドのパス問題** が発生する可能性があります
   - 実行中にgcloudが見つからなくなった場合は、フルパスで実行してください
   - 標準的なパス: `C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd`
   - 使用例: `& "C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" [コマンド]`
3. **変数の持続性** - PowerShellセッション中に変数が失われる場合があるため、必要に応じて再設定してください

```

#
################################################################################
# 0. まず一度だけ手入力する変数
###############################################################################
# ① GCP プロジェクト ID
export PROJECT_ID="your-project-id"

# ② デプロイ用リージョン（例: 東京）
export REGION="asia-northeast1"

# ③ GitHub リポジトリ (owner/repo)
export REPO="SRWS-PSG/meta-analysis-bot-release"
export REPO_OWNER="$(echo $REPO | cut -d/ -f1)"

# ④ Service Account 名
export SA_NAME="github-deployer"

# ⑤ Workload Identity Pool / Provider 名
export POOL_ID="github-pool"
export PROVIDER_ID="github"
################################################################################

# プロジェクトを選択 (gcloud init 済みなら不要)
gcloud config set project $PROJECT_ID

# 数値の PROJECT_NUMBER を取得して変数に入れる
export PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')"

# 1. 必要 API をオン
gcloud services enable run.googleapis.com \
                       cloudbuild.googleapis.com \
                       secretmanager.googleapis.com \
                       iam.googleapis.com

# 2. サービス アカウント作成 & 権限付与
gcloud iam service-accounts create $SA_NAME \
    --description="GitHub Actions deployer" \
    --display-name="GitHub Actions deployer"

SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudbuild.builds.editor"

# 3. Secret Manager に .env を登録 (.env がカレントにある前提)
gcloud secrets create app-env --replication-policy=automatic
gcloud secrets versions add app-env --data-file=.env

# 4. Workload Identity Pool & Provider を作る
gcloud iam workload-identity-pools create $POOL_ID \
  --project=$PROJECT_ID --location=global \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID \
  --project=$PROJECT_ID --location=global \
  --workload-identity-pool=$POOL_ID \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="attribute.repository=='$REPO'"

# 5. Provider から SA を impersonate できるようバインド
# 修正: 失敗しにくい構文を使用してWorkload Identity権限を設定
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$REPO"

# 設定確認: Workload Identity権限が正しく設定されたかチェック
echo "⏳ Workload Identity権限設定を確認中..."
gcloud iam service-accounts get-iam-policy $SA_EMAIL

# Provider のフルリソース名を控えておく（GitHub Secrets に入れる値）
export PROVIDER_RESOURCE="$(gcloud iam workload-identity-pools providers describe $PROVIDER_ID \
    --project=$PROJECT_ID --location=global --workload-identity-pool=$POOL_ID \
    --format='value(name)')"

echo "==============================================="
echo "🔑 GCP_PROJECT: $PROJECT_ID"
echo "🔑 workload_identity_provider: $PROVIDER_RESOURCE"
echo "🔑 service_account: $SA_EMAIL"
echo "これを GitHub Secrets に登録してください。"
echo "-----------------------------------------------"

# 6. (任意) Cloud Run に初回デプロイ（以降は GitHub Actions が自動実行）
# gcloud run deploy python-app \
#   --source=. --region=$REGION \
#   --service-account=$SA_EMAIL \
#   --set-secrets="/secrets/.env=app-env:latest" \
#   --add-volume="name=secret-vol,secret=app-env" \
#   --add-volume-mount="volume=secret-vol,mount-path=/secrets"

echo "✅ ターミナルだけでのセットアップ完了!"

```

## 🔧 トラブルシューティング

### gcloudコマンドが見つからない場合
```powershell
# パスの確認
where.exe gcloud

# 見つからない場合はフルパスで実行
& "C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" --version

# または環境変数を再設定
$env:PATH += ";C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"
```

### 変数が失われた場合
```powershell
# 主要変数の再設定 (PowerShellの場合)
$PROJECT_ID="your-project-id"
$POOL_ID="github-pool"  # 注意: 実際に作成したプール名を使用（エラーが出た場合はgithub-pool-2等）
$PROVIDER_ID="github"
$SA_EMAIL="github-deployer@$PROJECT_ID.iam.gserviceaccount.com"
```

### Workload Identity Pool作成でALREADY_EXISTSエラーが出る場合
- 削除状態のプールが残っている可能性があります
- 別の名前（例: `github-pool-2`, `github-pool-3`）を使用してください
- または30日後に自動削除されるまで待つ必要があります

### PowerShellでのコマンド実行時の注意
- 長いコマンドではバックスラッシュ（`\`）の代わりにバッククォート（`` ` ``）を使用
- 変数参照は `$変数名` の形式を使用
- 実行時に権限エラーが出る場合は管理者権限でPowerShellを起動

### ⚠️ Workload Identity権限エラー対処法（重要）
GitHub ActionsでCloud Runデプロイ時に以下のエラーが発生する場合：
```
Permission 'iam.serviceAccounts.getAccessToken' denied
```

**原因**: Workload Identity権限が正しく設定されていない

**解決策**:
1. 現在の権限設定を確認
```bash
gcloud iam service-accounts get-iam-policy $SA_EMAIL
```

2. 権限が空または不足している場合は再設定
```bash
# リポジトリ全体からのアクセスを許可
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$REPO"
```

3. GitHub Secrets の値を確認
- `GCP_WIF_PROVIDER`: プロバイダーのフルパスが設定されているか
- `GCP_WIF_SERVICE_ACCOUNT`: サービスアカウントのメールアドレスが正確か

### 設定確認コマンド
```bash
# 現在のプロジェクト確認
gcloud config list project

# Workload Identity Pool確認
gcloud iam workload-identity-pools list --location=global

# プロバイダー確認
gcloud iam workload-identity-pools providers list --workload-identity-pool=$POOL_ID --location=global

# サービスアカウント権限確認
gcloud iam service-accounts get-iam-policy $SA_EMAIL

# Secret Manager確認
gcloud secrets list --filter="name:app-env"
```

次にやる GitHub 側の最小設定
リポジトリ → Settings → Secrets and variables → Actions

以下 3 つを New repository secret で追加

Name	Value
GCP_PROJECT	my-gcp-project
GCP_WORKLOAD_IDENTITY_PROVIDER	上で echo した projects/…/providers/github
GCP_SERVICE_ACCOUNT	github-deployer@my-gcp-project.iam.gserviceaccount.com

.github/workflows/deploy.yml 例（超シンプル）

```yaml
コピーする
編集する
name: Deploy to Cloud Run
on: [push]

jobs:
  deploy:
    permissions:
      id-token: write
      contents: read
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - id: auth
      uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
        service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

    - uses: google-github-actions/setup-gcloud@v2

    - name: Deploy
      run: |
        gcloud run deploy python-app \
          --region=asia-northeast1 \
          --source=. \
          --service-account=${{ secrets.GCP_SERVICE_ACCOUNT }} \
          --set-secrets="/secrets/.env=app-env:latest" \
          --add-volume="name=secret-vol,secret=app-env" \
          --add-volume-mount="volume=secret-vol,mount-path=/secrets"

```
これで終わり
クリック操作ゼロ で GCP 側の準備が完了。

あとは git push するだけで GitHub Actions → GCP Cloud Run へ自動デプロイされます。
