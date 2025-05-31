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

### HTTP Mode（Cloud Run対応）
- **HTTPエンドポイント**でSlackと通信
- Cloud Runなどのサーバーレス環境に最適
- 高いスケーラビリティ
- Event SubscriptionsのURL設定が必要

動作モードは環境変数`SOCKET_MODE`で制御できます（`true`: Socket Mode, `false`または未設定: HTTP Mode）。

## 機能

- ✅ Slackで共有されたCSVファイルを受信 (`MessageHandler`がイベントを捉え、`CsvProcessor`に処理を委譲)
- ✅ pandasとGemini APIを使用してCSV構造を分析 (`meta_analysis.py`の`analyze_csv`関数がCSVの基本情報抽出、メタ分析への適合性評価、列の役割マッピングを実施)
- ✅ 収集されたパラメータに基づき、Rのmetaforパッケージを使用してメタ解析を実行 (`meta_analysis.py`の`run_meta_analysis`関数が`RTemplateGenerator`を用いてRスクリプトを生成し、`subprocess`で実行。エラー時はGeminiによるデバッグ・再試行も実施)
- ✅ フォレストプロット、Rコード、およびGemini APIによる学術論文形式のテキストレポートをSlackチャンネルに返信 (`AnalysisExecutor`が結果ファイルをアップロードし、`ReportHandler`がテキストレポートを生成・投稿)
- ✅ **スレッド内会話コンテキストの維持** (`ThreadContextManager`による)
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
    - ストレージバックエンド対応（メモリ、Redis、DynamoDB、ファイル、Firestore）。

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
- Google Gemini API Key（オプション）

## セットアップ

このアプリケーションはDockerコンテナとしての実行を前提としています。

### 1. 前提条件

*   Dockerがインストールされていること。
*   （必要に応じて）Google Cloud SDKがインストールされ、設定済みであること（GCPデプロイの場合）。

### 2. 環境変数の準備

プロジェクトルートに`.env`ファイルを作成し、必要な環境変数を設定します。`.env.example`をコピーして編集してください。

```bash
cp .env.example .env
# .envファイルに必要な情報を記述
```

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
    *   インストールが完了すると、「Bot User OAuth Token」が表示されます（`xoxb-...`で始まる文字列）。このトークンをコピーし、`.env`ファイルの`SLACK_BOT_TOKEN`に設定します。

4.  **Signing Secretの取得:**
    *   アプリ管理画面の左側のナビゲーションから「Basic Information」を選択します。
    *   「App Credentials」セクションまでスクロールし、「Signing Secret」の横にある「Show」をクリックして表示されるシークレットをコピーします。
    *   これを`.env`ファイルの`SLACK_SIGNING_SECRET`に設定します。

5.  **Socket Modeの設定 (必要な場合):**
    *   Socket Modeを使用する場合（推奨）、アプリ管理画面の左側のナビゲーションから「Socket Mode」を選択し、「Enable Socket Mode」をオンにします。
    *   「App-Level Tokens」セクションで「Generate an app-level token and add scopes」をクリックします。
    *   トークン名を入力し、「connections:write」スコープを追加して「Generate」をクリックします。
    *   生成されたトークン（`xapp-...`で始まる文字列）をコピーし、`.env`ファイルの`SLACK_APP_TOKEN`に設定します。
    *   `.env`ファイルで`SOCKET_MODE=true`に設定します。

6.  **Event Subscriptionsの設定 (HTTPモードの場合):**
    *   Socket Modeを使用しない場合（`SOCKET_MODE=false`）、アプリ管理画面の左側のナビゲーションから「Event Subscriptions」を選択し、「Enable Events」をオンにします。
    *   「Request URL」に、ボットがSlackイベントを受信するエンドポイントのURL（例: `https://your-domain.com/slack/events`）を設定します。
    *   「Subscribe to bot events」セクションで、ボットが購読するイベント（例: `app_mention`, `message.channels`, `file_shared`など）を追加します。

最低限、以下の環境変数を設定する必要があります。

*   `SLACK_BOT_TOKEN`: Slackボットのトークン (必須)
*   `SLACK_SIGNING_SECRET`: Slackアプリの署名シークレット (必須)
*   `SLACK_APP_TOKEN`: Socket Modeを使用する場合のSlackアプリトークン (Socket Mode利用時必須)
*   `SOCKET_MODE`: `true` (Socket Modeを使用する場合) または `false` (デフォルト: `false`、HTTPモード)
*   `STORAGE_BACKEND`: コンテキスト保存先。`memory` (デフォルト), `redis`, `dynamodb`, `file`, `firestore` のいずれか。
    *   `STORAGE_BACKEND=redis` の場合:
        *   `REDIS_HOST`: Redisサーバーのホスト名 (デフォルト: `localhost`)
        *   `REDIS_PORT`: Redisサーバーのポート番号 (デフォルト: `6379`)
        *   `REDIS_DB`: Redisデータベース番号 (デフォルト: `0`)
        *   `REDIS_PASSWORD`: Redisのパスワード (デフォルト: なし)
    *   `STORAGE_BACKEND=dynamodb` の場合:
        *   `DYNAMODB_TABLE`: 使用するDynamoDBテーブル名 (デフォルト: `slack_thread_contexts`)
        *   AWS認証情報 (例: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` など) がboto3によって解決可能である必要があります。
    *   `STORAGE_BACKEND=firestore` の場合:
        *   GCPプロジェクトIDが設定されている必要があります。通常、`GOOGLE_CLOUD_PROJECT` 環境変数が利用されるか、`gcloud auth application-default login` で認証されたプロジェクトが使用されます。
        *   Cloud RunなどのGCP環境で実行する場合、実行サービスアカウントにFirestoreへの読み書き権限 (`roles/datastore.user` など) が必要です。
        *   **`GCS_BUCKET_NAME`**: Firestoreストレージバックエンドでファイル（CSV、プロット画像、RDataなど）を永続化するために使用するGoogle Cloud Storageバケットの名前 (必須)。バケットは事前に作成し、Cloud Runの実行サービスアカウントに適切な読み書き権限 (`roles/storage.objectAdmin` または `roles/storage.objectCreator` と `roles/storage.objectViewer`) を付与しておく必要があります。
    *   `file`の場合:
        * 立ち上げているサーバー内に保持します。
*   `GEMINI_API_KEY`: Gemini APIを使用する場合のAPIキー (必須)
*   `GEMINI_MODEL_NAME`: 使用するGeminiモデル名 (オプション、デフォルト: `gemini-2.5-flash-preview-05-20`)
*   `R_EXECUTABLE_PATH`: Rscriptの実行パス (オプション。Dockerコンテナ内では通常不要。ホストOSで直接Rスクリプトを実行する場合や、システムパス上に `Rscript` がない場合に指定)

### ストレージバックエンドの詳細設定

#### Firestoreの高度な設定
```bash
# Firestoreサブコレクション機能（推奨）
FIRESTORE_USE_SUBCOLLECTION="true"  # デフォルト: true（Firestoreバックエンド使用時）

# 履歴保持件数の設定
MAX_HISTORY_LENGTH="20"  # デフォルト: 20件

# 古いメッセージの自動クリーンアップ（オプション）
ENABLE_AUTO_CLEANUP="true"  # デフォルト: false
AUTO_CLEANUP_KEEP_COUNT="100"  # 保持するメッセージ数
```

### 3. ローカル環境での実行 (Docker使用)

#### a. Dockerイメージのビルド

```bash
docker build -t meta-analysis-bot .
```

#### b. Dockerコンテナの実行

**通常の実行:**

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

**docker-composeを使用する場合:**

`docker-compose.yml` をプロジェクトルートに作成します (内容は既存のものを流用)。

```bash
docker-compose up --build
```

### 4. Google Cloud Platform (GCP) へのデプロイ

GCP Cloud Runへのデプロイ手順の詳細は[deploy-setup.md](deploy-setup.md)を参照してください。
この手順書には、以下のGCPリソース設定に関するコマンドも含まれています（または追記が必要です）。

*   **Google Cloud Storage (GCS) バケットの作成**: アプリケーションがCSVファイルや分析結果（プロット、RDataなど）を保存するためのGCSバケット。
*   **サービスアカウント権限の設定**:
    *   Cloud Runのランタイムサービスアカウントに対するFirestoreデータベースへのアクセス権限。
    *   Cloud Runのランタイムサービスアカウントに対する上記GCSバケットへの読み書き権限。
*   **環境変数の設定**:
    *   Cloud Runサービスに `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `GEMINI_API_KEY` などの基本的な環境変数。
    *   `STORAGE_BACKEND="firestore"` を設定。
    *   `GCS_BUCKET_NAME` に作成したGCSバケット名を設定。

### 5. デプロイ後の運用

詳細は[post-deployment.md](post-deployment.md)



## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
