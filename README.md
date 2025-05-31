# メタ解析Slack Bot

Slackで共有されたCSVファイルからメタ解析を実行し、結果を返すボットです。
現在はpairwise meta-analysisのみに対応しています。

## 概要

このボットはSlackでアップロードされたCSVファイルを監視し、`mcp/meta_analysis.py`内の`analyze_csv`関数を用いてpandasとGemini APIによる初期分析（CSV構造分析、メタ分析への適合性評価、列の役割マッピング）を行います。その後、ユーザーとの対話を通じて収集されたパラメータに基づき、同モジュール内の`run_meta_analysis`関数が`RTemplateGenerator`を用いてRスクリプトを動的に生成し、Rのmetaforパッケージを使用してメタ解析を実行します。最終的に、プロット、Rコード、およびGemini APIによって生成された学術論文形式のテキストレポートをSlackチャンネルに返します。

## 使用方法

1. ボットが存在するSlackチャンネルでCSVファイルを共有
2. ボットはCSVを分析し、適切な列が見つかった場合にメタ解析を実行
3. ユーザーは自然な日本語で分析の意図を伝える
4. 結果はスレッド内に共有され、スレッド内で会話コンテキストが維持される(インスタンスが維持される間だけ)

## 動作モード

このボットは2つの動作モードに対応しています：

### Socket Mode（ローカル開発推奨）
- **WebSocket接続**でSlackと通信
- ファイアウォール内での動作が可能
- 設定が簡単（Event SubscriptionsのURL設定不要）
- 長時間接続を維持

### HTTP Mode（Herokuデプロイ推奨）
- **HTTPエンドポイント**でSlackと通信
- Herokuなどのサーバーレス環境に最適
- 高いスケーラビリティ
- Event SubscriptionsのURL設定が必要 (Herokuデプロイ時は通常不要、Herokuが自動でルーティング)

動作モードは環境変数`SOCKET_MODE`で制御できます（`true`: Socket Mode (ローカル開発時), `false`または未設定: HTTP Mode (Herokuデプロイ時)）。

## 機能

- ✅ Slackで共有されたCSVファイルを受信 (`MessageHandler`がイベントを捉え、`CsvProcessor`に処理を委譲)
- ✅ pandasとGemini APIを使用してCSV構造を分析 (`meta_analysis.py`の`analyze_csv`関数がCSVの基本情報抽出、メタ分析への適合性評価、列の役割マッピングを実施)
- ✅ 収集されたパラメータに基づき、Rのmetaforパッケージを使用してメタ解析を実行 (`meta_analysis.py`の`run_meta_analysis`関数が`RTemplateGenerator`を用いてRスクリプトを生成し、`subprocess`で実行。エラー時はGeminiによるデバッグ・再試行も実施)
- ✅ フォレストプロット、Rコード、およびGemini APIによる学術論文形式のテキストレポートをSlackチャンネルに返信 (`AnalysisExecutor`が結果ファイルをアップロードし、`ReportHandler`がテキストレポートを生成・投稿)
- ✅ **スレッド内会話コンテキストの維持** (`ThreadContextManager`による。Herokuでは主にメモリ上で維持)
- 🚧 **複数の分析タイプ（ペアワイズ、サブグループ、メタ回帰など）** (基本的な対話フローは実装済み、Rスクリプト生成の高度化は進行中)
- ✅ **非同期処理によるSlackの3秒ルール対応** (`CsvProcessor`によるCSV分析、`AnalysisExecutor`によるメタ分析実行など)
- ✅ **Geminiを活用した自然言語理解**
  - `ParameterCollector`がユーザーの自然言語入力から効果量、モデルタイプ、サブグループ列などを抽出 (`gemini_utils.py`の`extract_parameters_from_user_input`利用)
  - `meta_analysis.py`の`analyze_csv`がCSV適合性分析と列マッピングを実施 (`gemini_utils.py`の`analyze_csv_compatibility_with_mcp_prompts`, `map_csv_columns_to_meta_analysis_roles`利用)
  - `meta_analysis.py`の`run_meta_analysis`がRスクリプトエラーのデバッグを実施 (`gemini_utils.py`の`regenerate_r_script_with_gemini_debugging`利用)
  - `ReportHandler`が分析結果から学術的な記述を生成 (`gemini_utils.py`の`generate_academic_writing_suggestion`利用)
- ✅ **強化された対話フロー**
  - `ParameterCollector`がGeminiによるパラメータ抽出と不足時の質問生成により、自然な対話を実現
  - 多層フォールバック戦略（Gemini→手動ダイアログ→基本テンプレート）
  - 常に詳細レポート＋AI解釈付きで出力を統一
- ✅ **MCPツールとの統合強化** (現在は直接的なMCPツール連携よりもGemini API活用が主)
  - テンプレート管理システムによる一貫した分析設定 (`RTemplateGenerator`によるRスクリプト生成)
  - データ互換性の自動検証機能 (`analyze_csv`による適合性評価)
- ✅ **エラー処理と再試行メカニズム** (`run_meta_analysis`内でのRスクリプト実行時のGeminiデバッグとリトライ、一般的なエラーハンドリング)

## アーキテクチャ

システムは以下の主要コンポーネントで構成されています：

1. **メインアプリケーション (main.py)**
   - アプリケーションのエントリーポイント
   - Botの初期化と起動

2. **Slack Bot (mcp/slack_bot.py)**
   - `MetaAnalysisBot`クラスのメインコンテナ。
   - 各モジュール（`MessageHandler`, `CsvProcessor`, `ParameterCollector`, `AnalysisExecutor`, `ReportHandler`など）のインスタンス化とイベントハンドラ（`MessageHandler`経由）への登録。
   - アプリケーションの起動。

3. **メッセージハンドラー (mcp/message_handlers.py)**
   - Slackの各種イベント（`app_mention`, `message`, `file_shared`）の処理。
   - イベント内容に応じて適切な処理モジュール（`CsvProcessor`の`process_csv_file`メソッド、`ParameterCollector`の`handle_analysis_preference_dialog`メソッドなど）にディスパッチ。
   - 一般的な質問への応答処理。

4. **ダイアログ状態管理 (mcp/dialog_state_manager.py)**
   - ユーザーとの対話状態（ファイル待機中、パラメータ収集中など）を管理。
   - 状態遷移ロジックを提供。

5. **CSVプロセッサー (mcp/csv_processor.py)**
   - アップロードされたCSVファイルのダウンロードと非同期での初期分析 (`meta_analysis.py`の`analyze_csv`関数を呼び出し)。
   - 分析結果（適合性、列情報、Geminiによる初期解釈など）をスレッドコンテキストに保存。
   - 分析結果に応じて`DialogStateManager`を介して対話状態を遷移。

6. **パラメータコレクター (mcp/parameter_collector.py)**
   - ユーザーのテキスト入力からメタアナリシスに必要なパラメータ（効果量、モデルタイプ、データ列マッピングなど）をGemini APIを活用して収集。
   - `gemini_utils.py`の`extract_parameters_from_user_input`を利用。
   - 不足パラメータに関する質問を生成し、対話的に収集。

7. **分析エクゼキューター (mcp/analysis_executor.py)**
   - 収集されたパラメータに基づいてメタアナリシスジョブを非同期で実行 (`meta_analysis.py`の`run_meta_analysis`関数を呼び出し)。
   - 分析ジョブの進捗と完了状態を監視。
   - 分析結果（Rスクリプト、プロット、RDataファイルなど）のアップロード (`meta_analysis.py`の`upload_file_to_slack`利用)。
   - レポート生成処理の呼び出し (`ReportHandler`へ)。

8. **レポートハンドラー (mcp/report_handler.py)**
   - `AnalysisExecutor`から呼び出され、分析結果（主に構造化されたJSONデータ）とGemini API (`gemini_utils.py`の`generate_academic_writing_suggestion`) を使用して、学術論文形式のレポート（Methods, Resultsセクション）を生成。
   - 生成されたレポートをSlackに投稿。

9. **メタ解析エンジン (mcp/meta_analysis.py)**
   - CSVファイルのダウンロード (`download_file`)。
   - pandasとGemini APIを用いたCSV内容の分析と列の役割マッピング (`analyze_csv`)。
   - Rスクリプトの動的生成 (`RTemplateGenerator`利用)。
   - R (metafor) を使用したメタ解析の実行 (`subprocess`経由、`run_meta_analysis`内)。
   - 結果ファイル（プロット、RData、構造化JSON）の生成。
   - エラー時のGeminiデバッグ (`regenerate_r_script_with_gemini_debugging`利用)。
   - Slackへのファイルアップロードユーティリティ (`upload_file_to_slack`)。
   - 一時ファイルの管理とクリーンアップ (`cleanup_temp_files`)。

10. **Rテンプレートジェネレーター (mcp/r_template_generator.py)**
    - `meta_analysis.py`の`run_meta_analysis`関数が、このジェネレータを使用して分析パラメータに応じたRスクリプトを動的に生成。

11. **スレッドコンテキスト管理 (mcp/thread_context.py)**
    - スレッドごとの会話履歴、データ状態、分析状態の永続化。
    - Heroku環境では、dynoの再起動で揮発するメモリ上のストレージ (`STORAGE_BACKEND=memory`) を使用します。結果はSlackに投稿されるため、永続的なストレージは不要です。

12. **非同期処理 (mcp/async_processing.py)**
    - 時間のかかるタスク（`CsvProcessor`によるCSV解析、`AnalysisExecutor`によるメタ解析）のバックグラウンド実行。
    - Slack APIの3秒タイムアウトルールへの対応。

13. **AIユーティリティ (mcp/gemini_utils.py, mcp/openai_utils.py)**
    - `ParameterCollector`がユーザー入力からパラメータを抽出 (`extract_parameters_from_user_input`)。
    - `meta_analysis.py`がCSV適合性分析と列マッピング (`analyze_csv_compatibility_with_mcp_prompts`, `map_csv_columns_to_meta_analysis_roles`)、およびRスクリプトエラーのデバッグ (`regenerate_r_script_with_gemini_debugging`) に利用。
    - `ReportHandler`が分析結果から学術的な記述を生成 (`generate_academic_writing_suggestion`)。
    - (旧) メタ解析結果の解釈と要約、ユーザー回答の解析と分析手法の自動選択など。

14. **エラー処理 (mcp/error_handling.py)**
    - アプリケーション全体のエラーハンドリング。
    - `run_meta_analysis`内でのRスクリプト実行エラーのデバッグ支援 (`gemini_utils.py`連携)。

15. **ユーザー対話 (mcp/user_interaction.py)**
    - （レガシー）分析タイプやパラメータ設定のための対話型ダイアログ管理。現在は主にParameterCollectorが担当。

16. **プロンプト管理 (mcp/prompt_manager.py)**
    - （将来的な拡張用）分析テンプレートの管理とカスタマイズ。

## 要件

- Python 3.8+
- metaforパッケージを含むR
- Slack API認証情報
- Google Gemini API Key

## セットアップ

このアプリケーションはDockerコンテナとしての実行を前提としています。

### 1. 前提条件

*   Docker Desktopがインストールされていること。
*   Gitがインストールされていること。
*   Heroku CLIがインストールされていること。
*   VS Code（推奨、拡張機能：Heroku Extension, GitHub Actions, PowerShell）

### 2. 環境変数の準備 (ローカル開発用)

ローカル開発用に、プロジェクトルートに`.env`ファイルを作成し、必要な環境変数を設定します。`.env.example`をコピーして編集してください。

```bash
cp .env.example .env
# .envファイルに必要な情報を記述
```
Herokuデプロイ時は、これらの変数をHerokuのConfig Varsに設定します。

### 2.1. Slack Botの設定

Slack Botをセットアップするには、以下の手順に従ってください。

1.  **Slack Appの作成:**
    *   Slack APIのウェブサイト ([https://api.slack.com/apps](https://api.slack.com/apps)) にアクセスします。
    *   「Create New App」をクリックし、「From scratch」を選択します。
    *   アプリ名（例: `MetaAnalysisBot`）と、ボットを開発・テストするSlackワークスペースを指定し、「Create App」をクリックします。

2.  **必要な権限 (Scopes) の設定:**
    *   作成したアプリの管理画面に移動し、左側のナビゲーションから「OAuth & Permissions」を選択します。
    *   「Bot Token Scopes」セクションまでスクロールし、「Add an OAuth Scope」をクリックして以下の権限を追加します。
        *   `app_mentions:read`
        *   `channels:history`
        *   `chat:write`
        *   `files:read`
        *   `groups:history`
        *   `im:history`
        *   `mpim:history`
        *   `users:read`

3.  **Bot User OAuth Tokenの取得とインストール:**
    *   「OAuth & Permissions」ページの上部にある「Install to Workspace」ボタンをクリックし、アプリをワークスペースにインストールします。
    *   インストールが完了すると、「Bot User OAuth Token」が表示されます（`xoxb-...`で始まる文字列）。このトークンをコピーし、ローカル開発時は`.env`ファイルの`SLACK_BOT_TOKEN`に、Herokuデプロイ時はConfig Varsに設定します。

4.  **Signing Secretの取得:**
    *   アプリ管理画面の左側のナビゲーションから「Basic Information」を選択します。
    *   「App Credentials」セクションまでスクロールし、「Signing Secret」の横にある「Show」をクリックして表示されるシークレットをコピーします。
    *   これをローカル開発時は`.env`ファイルの`SLACK_SIGNING_SECRET`に、Herokuデプロイ時はConfig Varsに設定します。

5.  **Socket Modeの設定 (ローカル開発時):**
    *   ローカル開発でSocket Modeを使用する場合、アプリ管理画面の左側のナビゲーションから「Socket Mode」を選択し、「Enable Socket Mode」をオンにします。
    *   「App-Level Tokens」セクションで「Generate an app-level token and add scopes」をクリックします。
    *   トークン名を入力し、「connections:write」スコープを追加して「Generate」をクリックします。
    *   生成されたトークン（`xapp-...`で始まる文字列）をコピーし、`.env`ファイルの`SLACK_APP_TOKEN`に設定します。
    *   `.env`ファイルで`SOCKET_MODE=true`に設定します。
    *   **Herokuデプロイ時はHTTP Mode (`SOCKET_MODE=false`または未設定) を使用するため、この設定は不要です。**

6.  **Event Subscriptionsの設定 (HTTPモードの場合):**
    *   Herokuデプロイ時 (HTTP Mode) は、HerokuがリクエストURLを自動的に提供するため、通常この設定は不要です。ローカルでHTTP Modeをテストする場合に設定します。
    *   Socket Modeを使用しない場合（`SOCKET_MODE=false`）、アプリ管理画面の左側のナビゲーションから「Event Subscriptions」を選択し、「Enable Events」をオンにします。
    *   「Request URL」に、ボットがSlackイベントを受信するエンドポイントのURL（例: `https://your-ngrok-url.io/slack/events`）を設定します。
    *   「Subscribe to bot events」セクションで、ボットが購読するイベント（例: `app_mention`, `message.channels`, `file_shared`など）を追加します。

Herokuデプロイ時にConfig Varsに設定が必要な主な環境変数:

*   `SLACK_BOT_TOKEN`: Slackボットのトークン (必須)
*   `SLACK_SIGNING_SECRET`: Slackアプリの署名シークレット (必須)
*   `SOCKET_MODE`: `false` (または未設定。HerokuではHTTPモードを使用)
*   `STORAGE_BACKEND`: `memory` (Herokuではメモリ上のストレージを使用。結果はSlackに投稿されるため永続化不要)
*   `GEMINI_API_KEY`: Gemini APIを使用する場合のAPIキー (必須)
*   `GEMINI_MODEL_NAME`: 使用するGeminiモデル名 (オプション、デフォルト: `gemini-2.5-flash-preview-05-20`)
*   `R_EXECUTABLE_PATH`: Rscriptの実行パス (オプション。Dockerコンテナ内では通常不要。)

ローカル開発時は上記に加え、Socket Mode利用時に`SLACK_APP_TOKEN`も`.env`ファイルに設定します。

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

*   **Windows PowerShell:**
    ```powershell
    docker run -it --env-file .env -v "${PWD}:/app" meta-analysis-bot
    ```
    または、絶対パスを指定:
    ```powershell
    docker run -it --env-file .env -v "C:\Users\youki\codes\meta-analysis-bot:/app" meta-analysis-bot
    ```
*   **Windows コマンドプロンプト:**
    ```cmd
    docker run -it --env-file .env -v "%cd%:/app" meta-analysis-bot
    ```
*   **Linux/Mac:**
    ```bash
    docker run -it --env-file .env -v $(pwd):/app meta-analysis-bot
    ```

**docker-composeを使用する場合 (ローカル開発用):**

`docker-compose.yml` をプロジェクトルートに作成します。

```bash
docker-compose up --build
```

### 4. Herokuへのデプロイ

このアプリケーションはHerokuのEco Dynosプランでの運用を想定しています。

#### 4.1. Heroku側の準備

1.  **Eco Dynosプランへの加入**:
    *   Herokuダッシュボードの Account → Billing → Eco Dynos から加入します (月$5で1000 dyno-hours)。
2.  **アプリの新規作成**:
    *   Herokuダッシュボードで新しいアプリを作成し、アプリ名 (`HEROKU_APP_NAME`) を控えます。
3.  **API Keyの発行**:
    *   Account → API Key からAPIキーを発行し、コピーしておきます。これはGitHub ActionsのSecret (`HEROKU_API_KEY`) として使用します。
4.  **Config Varsの登録**:
    *   作成したアプリの Settings → Config Vars で、以下の環境変数を設定します。
        *   `SLACK_BOT_TOKEN`
        *   `SLACK_SIGNING_SECRET`
        *   `GEMINI_API_KEY`
        *   `SOCKET_MODE=false` (または未設定)
        *   `STORAGE_BACKEND=memory`
        *   その他必要なAPIキーなど。
    *   `.env`ファイルの内容をここに登録します。公開リポジトリに`.env`ファイルをコミットしないでください。

#### 4.2. GitHub側の準備

1.  **Secretsの登録**:
    *   リポジトリの Settings → Secrets and variables → Actions で、以下の2つのリポジトリシークレットを登録します。
        *   `HEROKU_API_KEY`: 4.1.3で取得したHeroku APIキー。
        *   `HEROKU_APP_NAME`: 4.1.2で控えたHerokuアプリ名。
2.  **Secret Scanning & Push Protectionの有効化**:
    *   リポジトリの Settings → Code security and analysis で、Secret scanning と Push protection を有効化します。
3.  **.gitignoreの確認**:
    *   `.gitignore`に`.env`, `*.key`, `__pycache__/`などが含まれていることを確認し、機密情報や不要なファイルがコミットされないようにします。

#### 4.3. ローカルリポジトリの準備とDockerfileの修正

1.  **リポジトリの取得とブランチ作成**:
    ```powershell
    git clone https://github.com/SRWS-PSG/meta-analysis-bot-release.git # あなたのリポジトリURLに置き換えてください
    cd meta-analysis-bot-release
    git checkout -b feature/heroku-setup
    ```
2.  **Dockerfileの修正**:
    Herokuルーターは割り当てられた`$PORT`に60秒以内にバインドするアプリのみを生存とみなします。そのため、`Dockerfile`の`CMD`命令を以下のように修正します。
    ```dockerfile
    # (既存のDockerfileの内容)
    # CMD ["python", "main.py"] # ← このような行を修正または置換
    CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:${PORT:-8000}"]
    ```
    `app:server`の部分は、お使いのPython Webフレームワーク（Flask, FastAPIなど）のエントリーポイントに合わせてください。`main.py`が直接gunicornで起動できる場合は、`main:app`のようになることもあります。現在の`main.py`がFlaskアプリを`app`という名前でインスタンス化していることを想定しています。

#### 4.4. Heroku CLIでの設定と初回コミット

1.  **Heroku CLIでの操作**:
    ```powershell
    heroku login              # ブラウザで認証
    heroku container:login
    heroku git:remote -a YOUR_HEROKU_APP_NAME # YOUR_HEROKU_APP_NAMEを実際のアプリ名に置き換え
    heroku stack:set container      # スタックをDocker運用に変更
    heroku ps:type web=eco          # dynoタイプをecoに設定
    ```
2.  **コミット**:
    ```powershell
    git add Dockerfile .gitignore # Dockerfileの変更と.gitignoreを確認してadd
    git commit -m "feat: Configure for Heroku deployment, update Dockerfile for $PORT"
    ```
    必要に応じて他の変更ファイルもコミットしてください。

#### 4.5. GitHub Actionsによる自動デプロイの設定

プロジェクトのルートに`.github/workflows/deploy-heroku.yml`というファイル名で以下のワークフローを作成します。

```yaml
name: Deploy to Heroku (Eco)

on:
  push:
    branches:
      - main # mainブランチへのpushで発火。開発ブランチ名に合わせてください。
  workflow_dispatch: # 手動実行も可能にする

env:
  HEROKU_APP_NAME: ${{ secrets.HEROKU_APP_NAME }}
  REGISTRY_IMAGE: registry.heroku.com/${{ secrets.HEROKU_APP_NAME }}/web

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up QEMU (for multi-platform builds if needed)
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Heroku Container Registry
        run: echo "${{ secrets.HEROKU_API_KEY }}" | docker login --username=_ --password-stdin registry.heroku.com

      - name: Build and push Docker image
        run: |
          docker build --platform linux/amd64 -t $REGISTRY_IMAGE .
          docker push $REGISTRY_IMAGE
        # Apple Silicon (arm64) などで開発している場合、Heroku (amd64) 用に --platform linux/amd64 を指定

      - name: Release image to Heroku
        run: heroku container:release web --app $HEROKU_APP_NAME
        env:
          HEROKU_API_KEY: ${{ secrets.HEROKU_API_KEY }}
```

このワークフローは、指定したブランチ（例: `main`）にプッシュされると自動的に実行され、Dockerイメージをビルドし、Herokuコンテナレジストリにプッシュ後、新しいイメージをリリースします。

#### 4.6. デプロイの実行

変更をGitHubにプッシュします。

```powershell
git push origin feature/heroku-setup
```
プルリクエストを作成し、`main`ブランチ（またはワークフローで指定したブランチ）にマージすると、GitHub Actionsが起動し、Herokuへのデプロイが実行されます。

### 5. Herokuでの運用 (低アクセス想定)

*   **スリープ仕様**: Eco dynoは30分間通信がないと自動的にスリープします。再度アクセスがあると約5～10秒で再起動します。低コスト運用のため、監視Pingなどは設定しません。
*   **Dyno Hoursの確認**: `heroku ps -a YOUR_HEROKU_APP_NAME`でdynoの状態や使用時間を確認できます。月末に残りが少ない場合は、`heroku ps:scale web=0 -a YOUR_HEROKU_APP_NAME`でdynoを停止し、プール超過を防ぎます。
*   **ログ確認**: `heroku logs --tail -a YOUR_HEROKU_APP_NAME`でリアルタイムログを確認できます。
*   **コード更新**: ローカルでコードを修正し、コミットしてGitHubにプッシュすると、GitHub Actionsが自動的に再デプロイします。
*   **一時的な作業**: `heroku run bash -a YOUR_HEROKU_APP_NAME`でワンオフのdynoを起動し、データベースマイグレーションなどの一時的なコマンドを実行できます（本プロジェクトではDBを使用しないため、主にデバッグ用途）。

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
