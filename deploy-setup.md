# Meta Analysis Bot - GCP Cloud Run デプロイ手順書（3層SA設計）

このドキュメントは、Meta Analysis BotをGCP Cloud Runに自動デプロイCI/CDパイプラインと共にセットアップする手順を説明します。

## 事前準備

1.  **Google Cloud SDK (gcloud CLI) のインストール**: [インストールガイド](https://cloud.google.com/sdk/docs/install)
2.  **GitHub リポジトリ**: アプリケーションのコードがホストされていること。
3.  **必要な認証情報**:
    *   Slack Bot Token
    *   Slack Signing Secret
    *   Slack App Token (Socket Mode用)
    *   Gemini API Key

## アーキテクチャ概要

### 3層サービスアカウント設計
1. **GitHub Actions SA** (`github-deployer@PROJECT_ID.iam.gserviceaccount.com`)
   - GitHub OIDC認証とCloud Run管理を担当
   - 必要最小限の権限のみ保持

2. **Cloud Build SA** (`PROJECT_NUMBER@cloudbuild.gserviceaccount.com`)
   - ビルドとデプロイプロセスを実行
   - ストレージとビルド関連権限を保持

3. **Cloud Run Runtime SA** (`app-runtime@PROJECT_ID.iam.gserviceaccount.com`)
   - アプリケーション実行時の権限
   - Secret Manager等、アプリが必要とする最小権限のみ

### 権限チェーン
```
GitHub Actions SA → Cloud Build SA → Cloud Run Runtime SA
     (Act As)           (Act As)
```



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
- ただし、Win環境でのやり方であることに注意

## ⚠️ Windows環境での注意事項
1. **PowerShellを使用してください** (コマンドプロンプトではなく)
2. **gcloudコマンドのパス問題** が発生する可能性があります
   - 実行中にgcloudが見つからなくなった場合は、フルパスで実行してください
   - 標準的なパス: `C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd`
   - 使用例: `& "C:\Users\[ユーザー名]\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" [コマンド]`
3. **変数の持続性** - PowerShellセッション中に変数が失われる場合があるため、必要に応じて再設定してください

```powershell

#
################################################################################
# 0. まず一度だけ手入力する変数
################################################################################
# ① GCP プロジェクト ID
$PROJECT_ID="your-project-id"

# ② デプロイ用リージョン（例: 東京）
$REGION="asia-northeast1"

# ③ GitHub リポジトリ (owner/repo)
$REPO="SRWS-PSG/meta-analysis-bot-release"

# ④ Service Account 名
$SA_NAME="github-deployer"
$RUNTIME_SA_NAME="app-runtime"

# ⑤ Workload Identity Pool / Provider 名
$POOL_ID="github-pool"
$PROVIDER_ID="github"

# ⑥ Cloud Storage Bucket 名 (グローバルに一意な名前)
# 例: $PROJECT_ID + "-meta-analysis-bot-files"
$GCS_BUCKET_NAME="your-gcs-bucket-name" 
################################################################################

# プロジェクトを選択 (gcloud init 済みなら不要)
gcloud config set project $PROJECT_ID

# 数値の PROJECT_NUMBER を取得して変数に入れる
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"

# サービスアカウントのメールアドレス設定
$SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$RUNTIME_SA_EMAIL="$RUNTIME_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
$CLOUDBUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

echo "GitHub SA: $SA_EMAIL"
echo "Runtime SA: $RUNTIME_SA_EMAIL"
echo "Cloud Build SA: $CLOUDBUILD_SA"

# 1. 必須 API を有効化
gcloud services enable run.googleapis.com `
                       cloudbuild.googleapis.com `
                       artifactregistry.googleapis.com `
                       cloudresourcemanager.googleapis.com `
                       secretmanager.googleapis.com `
                       iam.googleapis.com `
                       logging.googleapis.com `
                       storage.googleapis.com ` # Cloud Storage API を追加
                       firestore.googleapis.com # Firestore API を追加

# 1.1 Firestore データベース作成 (API有効化後、SA権限設定前を推奨)
# リージョンは Cloud Run と同じものを指定してください (例: $REGION 変数)
# 1 プロジェクトに1つ作成可能。既に存在する場合はスキップされます。
# 注意: 無料枠利用の場合でも、Blazeプランへのアップグレードが求められることがあります。課金は超過分のみです。
gcloud firestore databases create --location=$REGION --project=$PROJECT_ID

# 1.2 Google Cloud Storage バケット作成
# バケット名はグローバルに一意である必要があります。
# リージョンはCloud Runと同じリージョンを指定することを推奨します。
# Uniform bucket-level access を有効にすることを推奨します。
gcloud storage buckets create gs://$GCS_BUCKET_NAME --project=$PROJECT_ID --location=$REGION --uniform-bucket-level-access

## Redis及び関連設定について
Redis (Cloud Memorystore) の設定、VPCコネクタの作成、およびCloud Runデプロイ時の関連設定については、別途 `gcp-redis-firestore-setup.md` を参照してください。

# 2. サービス アカウント作成
# GitHub Actions用SA
gcloud iam service-accounts create $SA_NAME `
    --description="GitHub Actions deployer" `
    --display-name="GitHub Actions deployer"

# Cloud Run Runtime用SA
gcloud iam service-accounts create $RUNTIME_SA_NAME `
    --description="Cloud Run runtime service account" `
    --display-name="App Runtime SA"

# 3. GitHub Actions SA 権限設定
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/run.sourceDeveloper"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/serviceusage.serviceUsageConsumer"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/storage.admin"

# 4. Cloud Build SA 権限設定
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/run.developer"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/storage.admin"

# 5. Runtime SA 権限設定
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$RUNTIME_SA_EMAIL" `
  --role="roles/secretmanager.secretAccessor"

# Firestoreへのアクセス権限をRuntime SAに付与
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$RUNTIME_SA_EMAIL" `
  --role="roles/datastore.user"

# Cloud Storageバケットへのアクセス権限をRuntime SAに付与
# roles/storage.objectAdmin はオブジェクトの読み書き削除が可能
# roles/storage.objectCreator (書き込み) と roles/storage.objectViewer (読み取り) に分離も可能
gcloud storage buckets add-iam-policy-binding gs://$GCS_BUCKET_NAME `
  --member="serviceAccount:$RUNTIME_SA_EMAIL" `
  --role="roles/storage.objectAdmin"

# 6. Act As 権限設定（重要）
# GitHub SA → Runtime SA
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SA_EMAIL `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/iam.serviceAccountUser"

# Cloud Build SA → Runtime SA
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SA_EMAIL `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/iam.serviceAccountUser"

# 7. Secret Manager に .env を登録 (.env がカレントにある前提)
gcloud secrets create app-env --replication-policy=automatic
gcloud secrets versions add app-env --data-file=.env

# 8. Workload Identity Pool & Provider を作る
gcloud iam workload-identity-pools create $POOL_ID `
  --project=$PROJECT_ID --location=global `
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc $PROVIDER_ID `
  --project=$PROJECT_ID --location=global `
  --workload-identity-pool=$POOL_ID `
  --display-name="GitHub Provider" `
  --issuer-uri="https://token.actions.githubusercontent.com" `
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" `
  --attribute-condition="attribute.repository=='$REPO'"

# 9. Workload Identity 権限設定
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL `
  --role="roles/iam.workloadIdentityUser" `
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$REPO"

# 10. Provider のフルリソース名を取得
$PROVIDER_RESOURCE = gcloud iam workload-identity-pools providers describe $PROVIDER_ID `
    --project=$PROJECT_ID --location=global --workload-identity-pool=$POOL_ID `
    --format='value(name)'

echo "==============================================="
echo "🔑 GCP_PROJECT: $PROJECT_ID"
echo "🔑 GCP_WIF_PROVIDER: $PROVIDER_RESOURCE"
echo "🔑 GCP_WIF_SERVICE_ACCOUNT: $SA_EMAIL"
echo "これを GitHub Secrets に登録してください。"
echo "-----------------------------------------------"

echo "✅ 3層SA構成でのセットアップ完了!"

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
$PROJECT_NUMBER="your-project-number"
$POOL_ID="github-pool"
$PROVIDER_ID="github"
$SA_EMAIL="github-deployer@$PROJECT_ID.iam.gserviceaccount.com"
$RUNTIME_SA_EMAIL="app-runtime@$PROJECT_ID.iam.gserviceaccount.com"
$CLOUDBUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"
```

### ⚠️ iam.serviceAccounts.actAs権限エラー対処法（重要）
GitHub ActionsでCloud Runデプロイ時に以下のエラーが発生する場合：
```
ERROR: PERMISSION_DENIED: User does not have permission to access service account
ERROR: Permission 'iam.serviceAccounts.actAs' denied
```

**原因**: GitHub SAがCloud Build SAまたはRuntime SAを「Act As」する権限が不足している

**解決策**:
```powershell
# GitHub SA → Runtime SA Act As権限
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SA_EMAIL `
  --member="serviceAccount:$SA_EMAIL" `
  --role="roles/iam.serviceAccountUser"

# Cloud Build SA → Runtime SA Act As権限
gcloud iam service-accounts add-iam-policy-binding $RUNTIME_SA_EMAIL `
  --member="serviceAccount:$CLOUDBUILD_SA" `
  --role="roles/iam.serviceAccountUser"
```

### ⚠️ API有効化エラー対処法
必要なAPIが有効化されていない場合：
```powershell
# 必須APIの一括有効化
gcloud services enable run.googleapis.com `
                       cloudbuild.googleapis.com `
                       artifactregistry.googleapis.com `
                       cloudresourcemanager.googleapis.com
```

### ⚠️ Workload Identity権限エラー対処法
GitHub ActionsでCloud Runデプロイ時に以下のエラーが発生する場合：
```
Permission 'iam.serviceAccounts.getAccessToken' denied
```

**原因**: Workload Identity権限が正しく設定されていない

**解決策**:
1. 現在の権限設定を確認
```powershell
gcloud iam service-accounts get-iam-policy $SA_EMAIL
```

2. 権限が空または不足している場合は再設定
```powershell
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL `
  --role="roles/iam.workloadIdentityUser" `
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL_ID/attribute.repository/$REPO"
```

### 設定確認コマンド
```powershell
# 現在のプロジェクト確認
gcloud config list project

# GitHub SA権限確認
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:$SA_EMAIL"

# Cloud Build SA権限確認
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:$CLOUDBUILD_SA"

# Runtime SA権限確認
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.members:$RUNTIME_SA_EMAIL"

# Act As権限確認
gcloud iam service-accounts get-iam-policy $RUNTIME_SA_EMAIL

# Secret Manager確認
gcloud secrets list --filter="name:app-env"
```

## GitHub 側の設定

### GitHub Secrets設定
リポジトリ → Settings → Secrets and variables → Actions

以下 3 つを New repository secret で追加:

| Name | Value |
|------|-------|
| `GCP_PROJECT` | あなたのプロジェクトID |
| `GCP_WIF_PROVIDER` | 上で echo した projects/…/providers/github |
| `GCP_WIF_SERVICE_ACCOUNT` | github-deployer@your-project-id.iam.gserviceaccount.com |
| `GCS_BUCKET_NAME` | 上で設定した `$GCS_BUCKET_NAME` の値 |

### ワークフロー設定
`.github/workflows/deploy.yml` は以下の構成になります：

```yaml
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
        workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
        service_account: ${{ secrets.GCP_WIF_SERVICE_ACCOUNT }}

    - uses: google-github-actions/setup-gcloud@v2

    - name: Set GCP Project
      run: gcloud config set project ${{ secrets.GCP_PROJECT }}

    - name: Deploy
      run: |
        gcloud run deploy python-app \
          --region=asia-northeast1 \
          --source=. \
          --service-account=app-runtime@${{ secrets.GCP_PROJECT }}.iam.gserviceaccount.com \
          # GCS_BUCKET_NAME 環境変数はGCPコンソール等から手動で設定してください (SecretManager gcs_bucket_name の値を参照)。
          # app-env (.envファイルの内容) もCloudRun環境では使用しない方針のため、マウント設定を削除。
          # 必要な変数は個別に環境変数として設定するか、個別のシークレットとして管理してください。
          --min-instances=0 \
          --max-instances=10 \
          --allow-unauthenticated
```

## 🎯 完了
クリック操作ゼロ で GCP 側の準備が完了。

あとは git push するだけで GitHub Actions → GCP Cloud Run へ自動デプロイされます。

### 3層SA設計の利点
1. **セキュリティ**: 各SAが必要最小限の権限のみ保持
2. **責任分離**: デプロイ権限、ビルド権限、実行権限を分離
3. **監査性**: 各段階での権限行使が明確に追跡可能
4. **保守性**: 権限の変更・追加が局所化される
