# Redis + Firestore ハイブリッドストレージ - GCP セットアップ手順

## 概要
Meta Analysis Bot を Redis (キャッシュ) + Firestore (永続化) のハイブリッドストレージで GCP Cloud Run にデプロイする手順です。

## 前提条件
- 基本的な GCP プロジェクトセットアップが完了していること (`deploy-setup.md` を参照)
- Cloud Run デプロイ設定が完了していること

## 1. Redis (Cloud Memorystore) の作成

### 1.1 Memorystore for Redis インスタンス作成
```bash
# プロジェクト変数設定
PROJECT_ID="your-project-id"
REGION="asia-northeast1" #東京の場合
REDIS_INSTANCE_NAME="chat-cache"

# Redis インスタンス作成 (Simple モード、1GiB)
gcloud redis instances create $REDIS_INSTANCE_NAME \
  --size=1 \
  --region=$REGION \
  --redis-version=redis_7_0 \
  --network=default \
  --redis-config maxmemory-policy=allkeys-lru \
  --project=$PROJECT_ID

# インスタンス情報確認
gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION
```

### 1.2 VPC コネクタ作成 (Cloud Run → Redis 接続用)
```bash
# VPC コネクタ作成
CONNECTOR_NAME="redis-connector"

gcloud compute networks vpc-access connectors create $CONNECTOR_NAME \
  --region=$REGION \
  --network=default \
  --range=10.8.0.0/28 \
  --project=$PROJECT_ID

# 作成確認
gcloud compute networks vpc-access connectors describe $CONNECTOR_NAME --region=$REGION
```

## 2. Firestore セットアップ

### 2.1 Firestore データベース作成
```bash
# Firestore Native モード有効化
# このコマンドはプロジェクトに初めてFirestoreデータベースを作成する場合に実行します。
# 既に存在する場合はスキップされます。
gcloud firestore databases create --region=$REGION --project=$PROJECT_ID

# インデックス設定 (会話履歴の効率的な取得用)
# 以下の複合インデックスは、Firestoreの自動インデックス作成機能や
# 単一フィールドインデックスでカバーされるため、明示的な作成は不要と判断されました。
# コマンド実行時に "this index is not necessary" というエラーが返される場合があります。
# 必要に応じて、GCPコンソールのFirestoreセクションでインデックスの状態を確認してください。
# gcloud firestore indexes composite create \
#   --collection-group=messages \
#   --field-config field-path=createdAt,order=ascending \
#   --field-config field-path=__name__,order=ascending \
#   --project=$PROJECT_ID
```

## 3. Cloud Run デプロイ設定更新

### 3.1 環境変数設定
```bash
# Redis 接続情報を Secret Manager に保存
# 注意: 以下のgcloud secrets createコマンドが "already exists" エラーになる場合は、
# 既にシークレットが存在するため、createコマンドをスキップし、続く versions add コマンドを実行してください。

# Redisホストの登録
$REDIS_HOST = $(gcloud redis instances describe $REDIS_INSTANCE_NAME --region=$REGION --project=$PROJECT_ID --format="value(host)")
gcloud secrets create redis-host --replication-policy=automatic --project=$PROJECT_ID
echo -n $REDIS_HOST | gcloud secrets versions add redis-host --data-file=- --project=$PROJECT_ID

# Redisポートの登録
gcloud secrets create redis-port --replication-policy=automatic --project=$PROJECT_ID
echo -n "6379" | gcloud secrets versions add redis-port --data-file=- --project=$PROJECT_ID

# RedisキャッシュTTLの登録
gcloud secrets create redis-cache-ttl --replication-policy=automatic --project=$PROJECT_ID
echo -n "300" | gcloud secrets versions add redis-cache-ttl --data-file=- --project=$PROJECT_ID

# ストレージバックエンド設定の登録
gcloud secrets create storage-backend --replication-policy=automatic --project=$PROJECT_ID
echo -n "hybrid" | gcloud secrets versions add storage-backend --data-file=- --project=$PROJECT_ID
```

### 3.2 Cloud Run デプロイ時の VPC コネクタ指定
デプロイ時に VPC コネクタを指定:
```bash
gcloud run deploy meta-analysis-bot \
  --source . \
  --region=$REGION \
  --vpc-connector=$CONNECTOR_NAME \
  --vpc-egress=private-ranges-only \
  --memory=1Gi \
  --set-env-vars=STORAGE_BACKEND=hybrid \
  --set-secrets=REDIS_HOST=redis-host:latest,REDIS_PORT=redis-port:latest,REDIS_CACHE_TTL=redis-cache-ttl:latest \
  --project=$PROJECT_ID
```

## 4. 動作確認

### 4.1 接続テスト
```bash
# Cloud Run ログでRedis接続確認
gcloud logs read "resource.type=cloud_run_revision" --project=$PROJECT_ID --limit=50

# 成功時のログ例:
# "HybridStorage initialized. Redis available: True, Firestore available: True"
```

### 4.2 キャッシュ動作確認
1. Slack でボットにメッセージ送信
2. 同じスレッドで再度メッセージ送信
3. ログで "Cache hit" が表示されることを確認

## 5. トラブルシューティング

### Redis 接続エラー
- VPC コネクタが正しく設定されているか確認
- Cloud Run の VPC egress 設定を確認
- Redis インスタンスのネットワーク設定を確認

### Firestore 接続エラー  
- サービスアカウントに Firestore 権限があるか確認
- プロジェクト ID が正しく設定されているか確認

## 6. メモリ設定推奨値

| コンポーネント | 推奨設定 | 理由 |
|---------------|----------|------|
| Cloud Run | 1GiB | Redis クライアント + Firestore クライアントのメモリ使用量 |
| Redis | 1GiB Simple | 最近の会話履歴 + 要約データのキャッシュ |

## 7. 運用時の注意点

- Redis はキャッシュ層なので、データ消失してもアプリケーションは動作継続
- Firestore が永続化層なので、こちらのバックアップが重要
- キャッシュ TTL (デフォルト 5分) は用途に応じて調整
