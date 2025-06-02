# Heroku Redis Hobby Dev セットアップ手順

## 1. Redis Hobby Dev アドオンの追加

Heroku CLIを使用：
```bash
heroku addons:create heroku-redis:hobby-dev -a your-app-name
```

または、Herokuダッシュボードから：
1. アプリケーションのページを開く
2. "Resources" タブをクリック
3. "Add-ons" セクションで "Heroku Redis" を検索
4. "Hobby Dev - Free" プランを選択
5. "Submit Order Form" をクリック

## 2. 環境変数の確認

Redis追加後、自動的に `REDIS_URL` 環境変数が設定されます：

```bash
heroku config:get REDIS_URL -a your-app-name
```

出力例：
```
redis://h:password@host:port
```

## 3. デプロイ

変更をコミットしてプッシュ：
```bash
git add .
git commit -m "feat: Add Redis support for thread context storage"
git push heroku main
```

## 4. 動作確認

ログを確認：
```bash
heroku logs --tail -a your-app-name
```

以下のようなメッセージが表示されれば成功：
```
Redis接続: REDIS_URLを使用
Redis接続成功
Thread context manager initialized with storage_backend=redis
```

## 5. トラブルシューティング

### Redisに接続できない場合

1. アドオンが正しく追加されているか確認：
   ```bash
   heroku addons -a your-app-name
   ```

2. 環境変数が設定されているか確認：
   ```bash
   heroku config -a your-app-name | grep REDIS
   ```

3. 一時的にメモリストレージに戻す場合：
   ```bash
   heroku config:set STORAGE_BACKEND=memory -a your-app-name
   ```

### メモリ使用量の確認

Redis Hobby Devは25MBまで無料：
```bash
heroku redis:info -a your-app-name
```

## 注意事項

- Redis Hobby Devは永続化保証がありません（メンテナンス時にデータが失われる可能性）
- 本番環境では有料プランの検討を推奨
- 25MB制限に達した場合、古いキーが自動的に削除されます（LRU）