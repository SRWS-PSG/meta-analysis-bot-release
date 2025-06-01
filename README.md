# メタ解析Slack Bot

Slackで共有されたCSVファイルからメタ解析を実行し、結果を返すボットです。
pairwise meta-analysis、サブグループ解析、メタ回帰分析に対応しています。

## 概要

このボットはSlackでアップロードされたCSVファイルを監視し、`mcp/meta_analysis.py`内の`analyze_csv`関数を用いてpandasとGemini APIによる初期分析（CSV構造分析、メタ解析への適合性評価、列の役割マッピング）を行います。その後、ユーザーとの対話を通じて収集されたパラメータに基づき、同モジュール内の`run_meta_analysis`関数が`RTemplateGenerator`を用いてRスクリプトを動的に生成し、Rのmetaforパッケージを使用してメタ解析を実行します。最終的に、プロット、Rコード、およびGemini APIによって生成された学術論文形式のテキストレポートをSlackチャンネルに返します。

## 使用方法

1. ボットが存在するSlackチャンネルでCSVファイルを共有
2. ボットはCSVを分析し、適切な列が見つかった場合にメタ解析を実行
3. ユーザーは自然な日本語で分析の意図を伝える
4. 結果はスレッド内に共有され、スレッド内で会話コンテキストが維持される（Heroku dyno再起動まで）

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

## 機能

- ✅ Slackで共有されたCSVファイルの受信と初期分析
- ✅ pandasとGemini APIによるCSV構造分析、メタ解析への適合性評価、列の役割マッピング
- ✅ ユーザーとの対話を通じた分析パラメータの収集
- ✅ Rのmetaforパッケージを使用したメタ解析の実行（ペアワイズ、サブグループ、メタ回帰対応）
- ✅ フォレストプロット、ファンネルプロット、バブルプロットの生成
- ✅ Rコード、およびGemini APIによる学術論文形式のテキストレポートの生成と返信
- ✅ スレッド内での会話コンテキスト維持（メモリベース）
- ✅ 非同期処理によるSlack APIの3秒タイムアウトルールへの対応
- ✅ Gemini APIを活用した高度な自然言語理解と処理
    - Function Callingによるパラメータ抽出
    - CSVの適合性分析と自動列マッピング
    - Rスクリプトエラーのデバッグ支援
    - 分析結果からの学術的な記述生成
- ✅ 強化された対話フロー（パラメータ抽出、不足時の質問生成、多層フォールバック戦略）
- ✅ テンプレートベースでの一貫した分析設定とRスクリプト生成
- ✅ データ互換性の自動検証
- ✅ エラー処理とGemini支援による再試行メカニズム
- ✅ 感度分析機能
- ✅ 効果量の自動検出（OR, RR, HR, SMD, MD等）
- ✅ 英語論文形式のMethods・Resultsセクション生成

## アーキテクチャ

システムは以下の主要コンポーネントで構成されています：

1. **メインアプリケーション (main.py)**
   - アプリケーションのエントリーポイント
   - Socket Mode/HTTP Modeの選択
   - Gunicorn用のWSGI アプリケーション定義

2. **Slack Bot (mcp/slack_bot.py)**
   - `MetaAnalysisBot`クラスのメインコンテナ
   - 各モジュールのインスタンス化とイベントハンドラーへの登録
   - アプリケーションの起動

3. **メッセージハンドラー (mcp/message_handlers.py)**
   - Slackの各種イベント（`app_mention`, `message`, `file_shared`）の処理
   - イベント内容に応じて適切な処理モジュールにディスパッチ
   - 一般的な質問への応答処理

4. **ダイアログ状態管理 (mcp/dialog_state_manager.py)**
   - ユーザーとの対話状態（ファイル待機中、パラメータ収集中など）を管理
   - 状態遷移ロジックを提供

5. **CSVプロセッサー (mcp/csv_processor.py)**
   - アップロードされたCSVファイルのダウンロードと非同期での初期分析
   - 分析結果（適合性、列情報、Geminiによる初期解釈など）をスレッドコンテキストに保存
   - 分析結果に応じた対話状態の遷移

6. **パラメータコレクター (mcp/parameter_collector.py)**
   - ユーザーのテキスト入力からメタアナリシスに必要なパラメータをGemini Function Callingで収集
   - 不足パラメータに関する質問を生成し、対話的に収集
   - 自動列マッピングとパラメータ検証

7. **分析エクゼキューター (mcp/analysis_executor.py)**
   - 収集されたパラメータに基づいてメタアナリシスジョブを非同期で実行
   - 分析ジョブの進捗と完了状態を監視
   - 分析結果（Rスクリプト、プロット、RDataファイルなど）のアップロード
   - レポート生成処理の呼び出し

8. **レポートハンドラー (mcp/report_handler.py)**
   - 分析結果とGemini APIを使用して学術論文形式のレポート（Methods, Resultsセクション）を生成
   - 感度分析結果の表示
   - 生成されたレポートをSlackに投稿

9. **メタ解析エンジン (mcp/meta_analysis.py)**
   - CSVファイルのダウンロード
   - pandasとGemini APIを用いたCSV内容の分析と列の役割マッピング
   - Rスクリプトの動的生成（`RTemplateGenerator`利用）
   - R (metafor) を使用したメタ解析の実行
   - 結果ファイル（プロット、RData、構造化JSON）の生成
   - エラー時のGeminiデバッグ
   - Slackへのファイルアップロードユーティリティ

10. **Rテンプレートジェネレーター (mcp/r_template_generator.py)**
    - 分析パラメータに応じたRスクリプトの動的生成
    - テンプレートベースの一貫したRコード生成
    - プロット生成とJSONサマリー出力の管理

11. **スレッドコンテキスト管理 (mcp/thread_context.py)**
    - スレッドごとの会話履歴、データ状態、分析状態の管理
    - Heroku環境ではメモリベースストレージを使用（dyno再起動で揮発）
    - 結果はSlackに投稿されるため、永続的なストレージは不要

12. **非同期処理 (mcp/async_processing.py)**
    - 時間のかかるタスクのバックグラウンド実行
    - Slack APIの3秒タイムアウトルールへの対応

13. **AIユーティリティ (mcp/gemini_utils.py)**
    - Function Callingによるパラメータ抽出
    - CSV適合性分析と列マッピング
    - Rスクリプトエラーのデバッグ
    - 学術的な記述生成

14. **エラー処理 (mcp/error_handling.py)**
    - アプリケーション全体のエラーハンドリング
    - Rスクリプト実行エラーのデバッグ支援

15. **プロンプト管理 (mcp/prompt_manager.py)**
    - 分析テンプレートの管理とカスタマイズ

## 要件

- Python 3.12+
- metaforパッケージを含むR
- Slack API認証情報
- Google Gemini API Key

## セットアップ

このアプリケーションはDockerコンテナとしての実行を前提としています。

### 1. 前提条件

- Docker Desktopがインストールされていること
- Gitがインストールされていること
- Heroku CLIがインストールされていること
- VS Code（推奨、拡張機能：Heroku Extension, GitHub Actions, PowerShell）

### 2. 環境変数の準備 (ローカル開発用)

ローカル開発用に、プロジェクトルートに`.env`ファイルを作成し、必要な環境変数を設定します。`.env.example`をコピーして編集してください。

```bash
cp .env.example .env
# .envファイルに必要な情報を記述
```

Herokuデプロイ時は、これらの変数をHerokuのConfig Varsに設定します。

### 2.1. Slack Botの設定

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

### 3. ローカル環境での実行 (Docker使用)

#### a. Dockerイメージのビルド

```bash
docker build -t meta-analysis-bot .
```

#### b. Dockerコンテナの実行

**通常の実行 (ローカル開発用):**

```bash
docker run --env-file .env meta-analysis-bot
```

**デバッグモード (ローカルのコード変更を即時反映):**

開発中にローカルのコード変更をコンテナに即座に反映させたい場合は、ボリュームマウントを使用します。

- **Windows PowerShell:**
  ```powershell
  docker run -it --env-file .env -v "${PWD}:/app" meta-analysis-bot
  ```
- **Windows コマンドプロンプト:**
  ```cmd
  docker run -it --env-file .env -v "%cd%:/app" meta-analysis-bot
  ```
- **Linux/Mac:**
  ```bash
  docker run -it --env-file .env -v $(pwd):/app meta-analysis-bot
  ```

### 4. Herokuへのデプロイ

このアプリケーションはHerokuのEco Dynosプランでの運用を想定しています。

#### 4.1. Heroku側の準備

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

#### 4.2. GitHub側の準備

1. **Secretsの登録**:
   - リポジトリの Settings → Secrets and variables → Actions で、以下のリポジトリシークレットを登録します
     - `HEROKU_API_KEY`: HerokuのAPIキー
     - `HEROKU_APP_NAME`: Herokuアプリ名

2. **Secret Scanning & Push Protectionの有効化**:
   - リポジトリの Settings → Code security and analysis で有効化します

#### 4.3. デプロイの実行

変更をGitHubにプッシュし、`main`ブランチにマージすると、GitHub Actionsが起動し、Herokuへのデプロイが実行されます。

### 5. Herokuでの運用 (低アクセス想定)

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
- `GEMINI_MODEL_NAME`: 使用するGeminiモデル (デフォルト: gemini-2.5-flash-preview-05-20)
- `MAX_HISTORY_LENGTH`: 会話履歴の最大保持件数 (デフォルト: 20)
- `R_EXECUTABLE_PATH`: Rscriptの実行パス (Dockerコンテナ内では通常不要)
- `PORT`: HTTPモード時のポート番号 (Herokuが自動設定)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.