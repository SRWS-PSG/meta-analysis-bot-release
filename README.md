# メタ解析Slack Bot

Slackで共有されたCSVファイルからメタ解析を実行し、学術論文形式のレポートを返すボットです。
Google Gemini AIによる自然言語対話で解析パラメータを収集し、R（metafor）を使用してpairwise meta-analysis、サブグループ解析、メタ回帰分析を実行します。
現状はpairwise meta-analysisのみに対応しています。

## 概要

このボットはSlackでアップロードされたCSVファイルを監視し、Gemini APIによる自然言語理解でCSV構造分析、メタ解析への適合性評価、列の役割マッピングを行います。ユーザーとの自然な日本語対話を通じてパラメータを収集し、`templates/r_templates.py`の`RTemplateGenerator`を用いてRスクリプトを動的に生成、Rのmetaforパッケージでメタ解析を実行します。最終的に、プロット（フォレスト・ファンネル・バブル）、Rコード、RDataファイル、およびGemini APIによるテキストレポート（Statistical Analysis・Resultsセクション）をSlackに返します。

## 使用方法

### 起動条件
- **メンション＋CSVファイル添付**: ボットが存在するSlackチャンネルでCSVファイルを共有し、@ボットでメンション
- **メンション＋CSVデータ（コードブロック）**: メンション付きメッセージ内にCSVデータをコードブロックで投稿
- **メンションのみ**: CSVファイル共有を依頼するメッセージが表示される

### 解析フロー
1. **CSV自動分析**: ボットがアップロードされたCSVを分析し、データ構造と効果量候補を検出
2. **自然言語パラメータ収集**: Gemini AIが日本語で対話しながら解析パラメータを収集（効果量、モデル、サブグループなど）
3. **メタ解析実行**: Rのmetaforパッケージを使用して非同期でメタ解析を実行
4. **結果返却**: フォレストプロット、Rコード、RDataファイル、学術論文形式のレポートをスレッド内に投稿

### 対話例
```
ユーザー: @bot [CSVファイル添付] オッズ比で解析してください
ボット: CSVファイルを分析しました！データセット概要：...
       解析パラメータを自然な日本語で教えてください
ユーザー: @bot ランダム効果モデルで、地域別のサブグループ解析もお願いします
ボット: 承知しました！解析を開始します...
       [解析完了後] フォレストプロット、Rコード、学術レポートを添付
```

## 動作モード

このボットは2つの動作モードに対応しています：

### Socket Mode（ローカル開発推奨）
- **WebSocket接続**でSlackと通信
- ファイアウォール内での動作が可能
- 設定が簡単（Event SubscriptionsのURL設定不要）
- 長時間接続を維持

### HTTP Mode（Herokuデプロイ推奨）
- **HTTPエンドポイント**でSlackと通信
- Heroku Eco dynosなどのサーバー環境に最適
- 高いスケーラビリティ
- Event SubscriptionsのURL設定が必要

動作モードは環境変数`SOCKET_MODE`で制御できます（`true`: Socket Mode (ローカル開発時), `false`または未設定: HTTP Mode (Herokuデプロイ時)）。

## プロジェクト構成

```
.
├── main.py                 # エントリーポイント
├── requirements.txt        # Python依存関係
├── init.R                  # R初期化スクリプト
├── Dockerfile             # Docker設定（ローカル開発用）
├── Procfile               # Heroku設定
├── README.md              # プロジェクト概要（本ファイル）
├── CLAUDE.md              # Claude AI開発ガイドライン
├── LICENSE                # ライセンス情報
│
├── core/                  # コア機能
│   ├── gemini_client.py   # Gemini API統合
│   ├── metadata_manager.py # メタデータ管理
│   └── r_executor.py      # R実行エンジン
│
├── handlers/              # Slackイベントハンドラー
│   ├── analysis_handler.py
│   ├── csv_handler.py
│   ├── mention_handler.py
│   ├── parameter_handler.py
│   └── report_handler.py
│
├── mcp_legacy/            # レガシー実装（移行中）
│   ├── slack_bot.py       # メインボットロジック
│   ├── gemini_utils.py    # Gemini統合ユーティリティ
│   └── ...
│
├── utils/                 # ユーティリティ
│   ├── conversation_state.py
│   ├── gemini_dialogue.py
│   └── slack_utils.py
│
├── templates/             # Rテンプレート
│   └── r_templates.py
│
├── docs/                  # 追加ドキュメント
│   ├── DEBUG_SLACK_BOT.md
│   ├── REDIS_SETUP.md
│   └── TEST_PLAN.md
│
├── scripts/               # ユーティリティスクリプト
│   ├── add_redis.sh
│   ├── add_redis_direct.sh
│   └── install_heroku_wsl.sh
│
├── tests/                 # テストスイート
│   ├── test_slack_upload.py
│   ├── test_gemini.py
│   └── ...
│
└── examples/              # サンプルCSVファイル
    ├── example_binary_meta_dataset.csv
    └── ...
```

## 機能

### コア機能
- ✅ **CSV自動分析**: Gemini AIによるデータ構造分析、適合性評価、列の自動マッピング
- ✅ **自然言語対話**: 日本語でのパラメータ収集、文脈理解、適切な質問生成
- ✅ **多様な効果量対応**: OR, RR, RD, HR, SMD, MD, PLO, IR, COR, 事前計算済み効果量
- ✅ **OR/CI自動変換**: オッズ比・リスク比と信頼区間から対数スケールへの自動変換（新機能）
- ✅ **ゼロセル対応**: Mantel-Haenszel法による補正なし解析、自動感度解析（新機能）
- ✅ **高度な解析機能**: サブグループ解析、メタ回帰、感度分析
- ✅ **学術レポート生成**: 英語論文形式（Statistical Analysis・Resultsセクション）+ 日本語併記

### 技術機能
- ✅ **非同期処理**: Slack 3秒タイムアウト対応、バックグラウンド解析実行
- ✅ **エラー処理**: Gemini AIによるRスクリプト自動デバッグ（最大3回リトライ）
- ✅ **プロット生成**: 動的サイズ調整、Events/Total表示、合計行付きフォレストプロット
- ✅ **ファイル出力**: Rスクリプト、フォレスト/ファンネル/バブルプロット、RDataファイル
- ✅ **スレッド対話**: 会話コンテキスト維持、メンション必須、状態管理

### 対応データ形式
- **二値アウトカム**: イベント数/総数（OR, RR, RD, PETO）
- **OR/RRと信頼区間**: 自動的にlnOR/lnRRとSEに変換（新機能）
- **連続アウトカム**: 平均値/標準偏差/サンプルサイズ（SMD, MD, ROM）
- **ハザード比**: ログ変換済みデータの自動検出
- **単一群比率**: イベント数/総数（PLO, PR, PAS, PFT, PRAW）
- **発生率**: イベント数/観察時間（IR, IRLN, IRS, IRFT）
- **相関**: 相関係数/サンプルサイズ（COR）
- **事前計算済み**: 効果量yi/分散vi

## アーキテクチャ

システムは以下の主要コンポーネントで構成されています：

### 1. エントリーポイント
- **main.py**: Socket Mode/HTTP Modeの選択、Slack Boltアプリケーション起動

### 2. コアモジュール (core/)
- **gemini_client.py**: Gemini API統合クライアント、CSV分析・パラメータ抽出・レポート生成
- **metadata_manager.py**: Slackメッセージメタデータの管理とペイロード処理
- **r_executor.py**: R実行エンジン、metaforによるメタ解析実行、エラーハンドリング

### 3. イベントハンドラー (handlers/)
- **mention_handler.py**: @ボットメンション処理、CSV検出、状態振り分け
- **csv_handler.py**: CSVファイル分析、Gemini APIによる適合性評価
- **parameter_handler.py**: 自然言語パラメータ収集、Gemini対話管理
- **analysis_handler.py**: メタ解析実行、結果ファイルアップロード
- **report_handler.py**: 学術レポート生成、Gemini解釈処理

### 4. テンプレート管理 (templates/)
- **r_templates.py**: RTemplateGenerator、動的Rスクリプト生成、プロット管理

### 5. ユーティリティ (utils/)
- **conversation_state.py**: 会話状態管理、Redis/メモリストレージ、対話フロー制御
- **slack_utils.py**: Slackメッセージ生成、ファイルアップロード、UI作成
- **file_utils.py**: ファイル管理、一時ディレクトリ操作、ダウンロード処理
- **parameter_extraction.py**: パラメータ抽出ロジック
- **gemini_dialogue.py**: Gemini対話管理（レガシー）

### 6. データフロー
```
CSV添付+メンション → mention_handler → csv_handler → Gemini分析
                                      ↓
parameter_handler ← Gemini対話 ← ユーザー応答検出
         ↓
analysis_handler → R実行 → プロット生成 → ファイルアップロード
         ↓
report_handler → Gemini解釈 → 学術レポート → Slack投稿
```

## 要件

- Python 3.12+
- metaforパッケージを含むR
- Slack API認証情報
- Google Gemini API Key

## セットアップ

### 1. 前提条件

- **Python 3.12+** がインストールされていること
- **R (4.0+)** とmetaforパッケージがインストールされていること  
- **Git** がインストールされていること
- **Heroku CLI** がインストールされていること（デプロイ時）

### 2. ローカル環境セットアップ

#### a. リポジトリのクローン
```bash
git clone https://github.com/your-username/meta-analysis-bot-release.git
cd meta-analysis-bot-release
```

#### b. Python依存関係のインストール
```bash
pip install -r requirements.txt
```

#### c. R環境のセットアップ
Rとmetaforパッケージが必要です：
```r
# Rコンソールで実行
install.packages("metafor")
install.packages("jsonlite")
```

#### d. 環境変数の設定
プロジェクトルートに`.env`ファイルを作成し、必要な環境変数を設定します：

```bash
# .envファイル例
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
GEMINI_API_KEY=your-gemini-api-key
SOCKET_MODE=true  # ローカル開発時
SLACK_APP_TOKEN=xapp-your-app-token  # Socket Mode使用時

# テスト用環境変数（テスト実行時に必要）
SLACK_UPLOAD_BOT_TOKEN=xoxb-test-messenger-token
SLACK_UPLOAD_CHANNEL_ID=C123456789  # テスト用チャンネルID
META_ANALYSIS_BOT_ID=U123456789     # メタ解析ボットのユーザーID
```

### 3. Slack Botの設定

Slack Botをセットアップするには、以下の手順に従ってください。

1. **Slack Appの作成:**
   - Slack APIのウェブサイト ([https://api.slack.com/apps](https://api.slack.com/apps)) にアクセスします
   - 「Create New App」をクリックし、「From scratch」を選択します
   - アプリ名（例: `MetaAnalysisBot`）と、ボットを開発・テストするSlackワークスペースを指定し、「Create App」をクリックします

2. **必要な権限 (Scopes) の設定:**
   - 作成したアプリの管理画面に移動し、左側のナビゲーションから「OAuth & Permissions」を選択します
   - 「Bot Token Scopes」セクションまでスクロールし、「Add an OAuth Scope」をクリックして以下の権限を追加します
     - `app_mentions:read`
     - `channels:history`
     - `chat:write`
     - `files:read`
     - `groups:history`
     - `im:history`
     - `mpim:history`
     - `users:read`

3. **Bot User OAuth Tokenの取得とインストール:**
   - 「OAuth & Permissions」ページの上部にある「Install to Workspace」ボタンをクリックし、アプリをワークスペースにインストールします
   - インストールが完了すると、「Bot User OAuth Token」が表示されます（`xoxb-...`で始まる文字列）
   - このトークンをコピーし、ローカル開発時は`.env`ファイルの`SLACK_BOT_TOKEN`に、Herokuデプロイ時はConfig Varsに設定します

4. **Signing Secretの取得:**
   - アプリ管理画面の左側のナビゲーションから「Basic Information」を選択します
   - 「App Credentials」セクションまでスクロールし、「Signing Secret」の横にある「Show」をクリックして表示されるシークレットをコピーします
   - これをローカル開発時は`.env`ファイルの`SLACK_SIGNING_SECRET`に、Herokuデプロイ時はConfig Varsに設定します

5. **Socket Modeの設定 (ローカル開発時):**
   - ローカル開発でSocket Modeを使用する場合、アプリ管理画面の左側のナビゲーションから「Socket Mode」を選択し、「Enable Socket Mode」をオンにします
   - 「App-Level Tokens」セクションで「Generate an app-level token and add scopes」をクリックします
   - トークン名を入力し、「connections:write」スコープを追加して「Generate」をクリックします
   - 生成されたトークン（`xapp-...`で始まる文字列）をコピーし、`.env`ファイルの`SLACK_APP_TOKEN`に設定します
   - `.env`ファイルで`SOCKET_MODE=true`に設定します
   - **Herokuデプロイ時はHTTP Mode (`SOCKET_MODE=false`または未設定) を使用するため、この設定は不要です**

6. **Event Subscriptionsの設定 (HTTPモードの場合):**
   - HerokuにデプロイしてHTTP Mode (`SOCKET_MODE=false`または未設定) を使用する場合、Slack Appの管理画面でEvent Subscriptionsの設定が必要です
   - アプリ管理画面の左側のナビゲーションから「Event Subscriptions」を選択し、「Enable Events」をオンにします
   - 「Request URL」に、HerokuアプリケーションのイベントエンドポイントURLを設定します。これは通常、 `https://<YOUR_HEROKU_APP_NAME>.herokuapp.com/slack/events` という形式になります
   - 「Subscribe to bot events」セクションで、ボットが購読するイベント（例: `app_mention`, `message.channels`, `file_shared`など）を追加します

### 4. ローカル環境での実行

環境変数を設定した後、以下のコマンドでボットを起動できます：

```bash
# 直接実行
python main.py

# または環境変数を指定して実行
SOCKET_MODE=true python main.py
```

Socket Modeを使用する場合、ボットは自動的にSlackに接続し、メンションやファイル共有イベントを監視します。

### 5. Herokuへのデプロイ

このアプリケーションはHerokuのEco Dynosプランでの運用を想定しています。

#### 5.1. Heroku側の準備

1. **Eco Dynosプランへの加入**:
   - Herokuダッシュボードの Account → Billing → Eco Dynos から加入します (月$5で1000 dyno-hours)

2. **アプリの新規作成**:
   - Herokuダッシュボードで新しいアプリを作成し、アプリ名 (`HEROKU_APP_NAME`) を控えます

3. **API Keyの発行**:
   - Account → API Key からAPIキーを発行し、コピーしておきます（GitHub ActionsのSecret用）

4. **Config Varsの登録**:
   - 作成したアプリの Settings → Config Vars で、以下の環境変数を設定します
     - `SLACK_BOT_TOKEN`
     - `SLACK_SIGNING_SECRET`
     - `GEMINI_API_KEY`
     - `SOCKET_MODE=false` (または未設定)
     - `STORAGE_BACKEND=memory`
     - その他必要なAPIキーなど

#### 5.2. GitHub側の準備

1. **Secretsの登録**:
   - リポジトリの Settings → Secrets and variables → Actions で、以下のリポジトリシークレットを登録します
     - `HEROKU_API_KEY`: HerokuのAPIキー
     - `HEROKU_APP_NAME`: Herokuアプリ名

2. **Secret Scanning & Push Protectionの有効化**:
   - リポジトリの Settings → Code security and analysis で有効化します

#### 5.3. デプロイの実行

変更をGitHubにプッシュし、`main`ブランチにマージすると、GitHub Actionsが起動し、Herokuへのデプロイが実行されます。

### 6. Herokuでの運用 (低アクセス想定)

- **スリープ仕様**: Eco dynoは30分間通信がないと自動的にスリープします。再度アクセスがあると約5～10秒で再起動します
- **Dyno Hoursの確認**: `heroku ps -a YOUR_HEROKU_APP_NAME`でdynoの状態や使用時間を確認できます
- **ログ確認**: `heroku logs --tail -a YOUR_HEROKU_APP_NAME`でリアルタイムログを確認できます
- **コード更新**: ローカルでコードを修正し、コミットしてGitHubにプッシュすると、GitHub Actionsが自動的に再デプロイします

## 主要な環境変数

### 必須変数

- `SLACK_BOT_TOKEN`: Slackボットのトークン
- `SLACK_SIGNING_SECRET`: Slackアプリの署名シークレット
- `GEMINI_API_KEY`: Gemini APIキー

### オプション変数

- `SOCKET_MODE`: Socket Modeの有効化 (true/false、デフォルト: false)
- `SLACK_APP_TOKEN`: Socket Mode使用時のアプリレベルトークン
- `STORAGE_BACKEND`: ストレージバックエンド (memory、デフォルト: memory)
- `GEMINI_MODEL_NAME`: 使用するGeminiモデル (デフォルト: gemini-1.5-flash)
- `MAX_HISTORY_LENGTH`: 会話履歴の最大保持件数 (デフォルト: 20)
- `R_EXECUTABLE_PATH`: Rscriptの実行パス (Dockerコンテナ内では通常不要)
- `PORT`: HTTPモード時のポート番号 (Herokuが自動設定)

## テスト・デバッグ

### 対話テスト方法

`tests/`ディレクトリには包括的なテストツールが用意されています。

**注意**: テストコマンドの`YOUR_BOT_ID`は、実際のボットのSlack User IDに置き換えてください。Slack APIの`auth.test`やボットのプロフィールから確認できます。

#### 1. 基本的な対話テスト
```bash
cd tests/
# Step 1: CSVファイル+メンションを投稿（test-messengerボット使用）
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example binary --message "オッズ比で解析してください"

# Step 2: ボットの応答確認
python3 debug_channel_messages.py

# Step 3: ユーザー応答をシミュレート（スレッド内でメンション必須）
python3 send_message.py --message "<@YOUR_BOT_ID> はい、ランダム効果モデルでお願いします" --thread "THREAD_TS"

# Step 4: 最終結果確認
python3 debug_channel_messages.py
```

#### 2. 異なる解析タイプのテスト
```bash
# 連続アウトカムデータ
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example continuous --message "標準化平均差で解析してください"

# 比率データ
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example proportion --message "比率データの解析をお願いします"

# ハザード比データ
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example hazard_ratio --message "ハザード比で解析してください"

# ゼロセルデータ（Mantel-Haenszel法のテスト）
python3 test_slack_upload.py --bot-id YOUR_BOT_ID --example zero_cells --message "ゼロセルがあるデータでMantel-Haenszel法をお願いします"
```

#### 3. バージョン情報テスト
```bash
# R version、metafor versionの表示確認
python3 test_version_info_debug.py
```

### デバッグ手順

#### Herokuログ確認
```bash
# リアルタイムログ
heroku logs --tail --app=meta-analysis-bot

# エラーログのみ
heroku logs --app=meta-analysis-bot | grep -E "(ERROR|Exception|Failed)"

# 特定時間のログ
heroku logs --since "2024-01-01T00:00:00Z" --until "2024-01-01T01:00:00Z" --app=meta-analysis-bot
```

#### 起動条件の確認
- ✅ **メンション＋CSVファイル添付**: ボット起動、CSV分析開始
- ✅ **メンション＋CSVコードブロック**: ボット起動、CSV分析開始  
- ✅ **メンションのみ**: ボット起動、CSV共有依頼
- ❌ **CSV共有のみ（メンションなし）**: ボット起動しない（仕様通り）

詳細な使用方法は`tests/README.md`を参照してください。

## 謝辞

本プロジェクトは、JSPS科研費 25K13585「大規模言語モデルが加速するエビデンスの統合」の助成を受けて開発されました。
- 研究課題番号: 25K13585
- 研究課題詳細: https://kaken.nii.ac.jp/ja/grant/KAKENHI-PROJECT-25K13585/

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.