import asyncio
from slack_bolt import App
from core.metadata_manager import MetadataManager
from core.gemini_client import GeminiClient
from utils.slack_utils import create_analysis_start_blocks, create_unsuitable_csv_blocks # create_unsuitable_csv_blocks をインポート
from utils.file_utils import download_slack_file_content_async # download_slack_file_content_async をインポート

def register_csv_handlers(app: App):
    """CSV関連のハンドラーを登録"""
    
    @app.event("file_shared")
    def handle_file_upload(body, client, event, logger):
        """ファイルアップロード時の処理"""
        file_info = event.get("file")
        
        if not file_info or not file_info.get("name", "").endswith(".csv"):
            return
        
        # 非同期でCSV分析を実行
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # イベントループが存在しない場合は新しく作成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.create_task(process_csv_async(
            file_info=file_info,
            channel_id=event["channel_id"],
            user_id=event["user_id"],
            client=client,
            logger=logger
        ))

async def process_csv_text_async(csv_text, channel_id, user_id, thread_ts, client, logger):
    """テキスト形式のCSVデータを処理する"""
    try:
        logger.info(f"Starting CSV text processing. Text size: {len(csv_text)} chars")
        logger.info(f"First 200 chars of CSV text: {csv_text[:200]}...")
        
        # Gemini APIでCSV分析
        gemini_client = GeminiClient()
        analysis_result = await gemini_client.analyze_csv(csv_text)
        logger.info(f"Gemini analysis result: is_suitable={analysis_result.get('is_suitable')}, reason={analysis_result.get('reason', 'N/A')[:100]}...")
        
        if not analysis_result.get("is_suitable", False):
            # メタ解析に適さない場合
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="❌ このCSVデータはメタ解析に適していないようです。",
                blocks=create_unsuitable_csv_blocks(analysis_result.get('reason', '詳細不明'))
            )
            return
        
        # メタデータ作成
        job_id = MetadataManager.create_job_id()
        
        response_message = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="📊 CSVデータを分析しました。メタ解析を開始しますか？",
            blocks=create_analysis_start_blocks(analysis_result)
        )
        
        if response_message and response_message.get("ok"):
            msg_ts = response_message.get("ts")
            msg_channel = response_message.get("channel")

            metadata_payload = {
                "job_id": job_id,
                "csv_analysis": analysis_result,
                "csv_text": csv_text,  # テキストデータを直接保存
                "stage": "awaiting_parameters",
                "user_id": user_id,
                "response_channel_id": msg_channel,
                "response_thread_ts": msg_ts
            }
            final_metadata = MetadataManager.create_metadata("csv_analyzed", metadata_payload)

            client.chat_update(
                channel=msg_channel,
                ts=msg_ts,
                metadata=final_metadata
            )
            logger.info(f"CSV text analysis result message (Job ID: {job_id}) にメタデータを付加しました。ts: {msg_ts}")
        else:
            logger.error(f"CSV text analysis result message投稿に失敗しました。Job ID: {job_id}")
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="❌ CSV分析結果の表示中にエラーが発生しました。"
            )
            return
        
    except Exception as e:
        logger.error(f"CSV text processing error: {e}", exc_info=True)
        
        # より詳細なエラー情報を提供
        error_message = "❌ CSVデータの処理中にエラーが発生しました。"
        if "GEMINI_API_KEY" in str(e):
            error_message += "\n⚠️ Gemini APIキーが設定されていません。"
        elif "analyze" in str(e).lower():
            error_message += "\n⚠️ CSV分析中にエラーが発生しました。"
        
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=error_message
        )

async def process_csv_async(file_info, channel_id, user_id, client, logger, thread_ts=None):
    """CSVファイルの非同期分析処理"""
    try:
        logger.info(f"Starting CSV processing for file: {file_info.get('name', 'unknown')}")
        logger.info(f"File info keys: {list(file_info.keys())}")
        
        # CSVダウンロード
        csv_content_bytes = await download_slack_file_content_async(
            file_url=file_info["url_private_download"], # プライベートダウンロードURLを使用
            bot_token=client.token
        )
        # ダウンロードしたバイト列をUTF-8でデコード（CSVが他のエンコーディングの可能性も考慮が必要）
        try:
            csv_content = csv_content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            logger.warning("UTF-8でのデコードに失敗。Shift-JISで試行します。")
            try:
                csv_content = csv_content_bytes.decode('shift_jis')
            except UnicodeDecodeError:
                logger.error("CSVファイルのデコードに失敗しました。")
                message_kwargs = {
                    "channel": channel_id,
                    "text": "❌ CSVファイルのエンコーディングが不明で処理できませんでした。"
                }
                if thread_ts:
                    message_kwargs["thread_ts"] = thread_ts
                client.chat_postMessage(**message_kwargs)
                return

        # Gemini APIでCSV分析
        logger.info(f"Analyzing CSV content with Gemini. Content size: {len(csv_content)} chars")
        gemini_client = GeminiClient()
        analysis_result = await gemini_client.analyze_csv(csv_content)
        logger.info(f"Gemini analysis result: is_suitable={analysis_result.get('is_suitable')}, reason={analysis_result.get('reason', 'N/A')[:100]}...")
        
        if not analysis_result.get("is_suitable", False):
            # メタ解析に適さない場合
            message_kwargs = {
                "channel": channel_id,
                "text": f"❌ このCSVファイルはメタ解析に適していないようです。", # 理由はBlockに含める
                "blocks": create_unsuitable_csv_blocks(analysis_result.get('reason', '詳細不明'))
            }
            if thread_ts:
                message_kwargs["thread_ts"] = thread_ts
            client.chat_postMessage(**message_kwargs)
            return
        
        # メタデータ作成
        job_id = MetadataManager.create_job_id()
        
        # メッセージ投稿前に metadata の準備 (ts を含めるため)
        # この時点では ts は不明なので、投稿後に更新するか、
        # parameter_handler側でbodyから取得する。
        # ここでは、投稿後に元のメッセージを特定できるように job_id を使うことを想定し、
        # parameter_handler側でモーダルを開く際に、元のメッセージの channel と ts を
        # private_metadata に含めるようにする。
        # そのため、csv_handler での metadata には channel_id と user_id を含めておく。
        # thread_ts はボタンが押されたメッセージのtsなので、parameter_handlerのactionのbodyから取得できる。

        # client.chat_postMessage の応答から ts を取得して metadata に追加する方が確実。
        message_kwargs = {
            "channel": channel_id,
            "text": "📊 CSVファイルを分析しました。メタ解析を開始しますか？",
            "blocks": create_analysis_start_blocks(analysis_result)
            # metadata は後で設定するか、parameter_handlerで参照する
        }
        if thread_ts:
            message_kwargs["thread_ts"] = thread_ts
        response_message = client.chat_postMessage(**message_kwargs)
        
        if response_message and response_message.get("ok"):
            msg_ts = response_message.get("ts")
            msg_channel = response_message.get("channel")

            metadata_payload = {
                "job_id": job_id,
                "csv_analysis": analysis_result,
                "file_id": file_info["id"],
                "file_url": file_info["url_private_download"], # ダウンロード用URL
                "original_filename": file_info.get("name", "data.csv"), # 元のファイル名も保存
                "stage": "awaiting_parameters",
                "user_id": user_id,
                "response_channel_id": msg_channel, # ボタンがあるメッセージのチャンネル
                "response_thread_ts": msg_ts       # ボタンがあるメッセージのTS (スレッドの起点)
            }
            final_metadata = MetadataManager.create_metadata("csv_analyzed", metadata_payload)

            # メタデータのみを更新 (Slack APIの制限により、メッセージ投稿と同時にはできない場合がある)
            # chat.update を使ってメタデータを付加する
            client.chat_update(
                channel=msg_channel,
                ts=msg_ts,
                metadata=final_metadata # metadata全体を渡す
            )
            logger.info(f"CSV分析結果メッセージ (Job ID: {job_id}) にメタデータを付加しました。ts: {msg_ts}")
        else:
            logger.error(f"CSV分析結果メッセージの投稿に失敗しました。Job ID: {job_id}")
            # エラー処理
            message_kwargs = {
                "channel": channel_id,
                "text": "❌ CSV分析結果の表示中にエラーが発生しました。"
            }
            if thread_ts:
                message_kwargs["thread_ts"] = thread_ts
            client.chat_postMessage(**message_kwargs)
            return
        
    except Exception as e:
        logger.error(f"CSV処理エラー: {e}", exc_info=True)
        
        # より詳細なエラー情報を提供
        error_message = "❌ CSVファイルの処理中にエラーが発生しました。"
        if "GEMINI_API_KEY" in str(e):
            error_message += "\n⚠️ Gemini APIキーが設定されていません。"
        elif "download" in str(e).lower():
            error_message += "\n⚠️ ファイルのダウンロードに失敗しました。"
        elif "analyze" in str(e).lower():
            error_message += "\n⚠️ CSV分析中にエラーが発生しました。"
        
        message_kwargs = {
            "channel": channel_id,
            "text": error_message
        }
        if thread_ts:
            message_kwargs["thread_ts"] = thread_ts
        client.chat_postMessage(**message_kwargs)

# download_slack_file のような関数は utils/file_utils.py に実装することを推奨
# async def download_slack_file(url: str, token: str) -> str:
#     import aiohttp
#     headers = {"Authorization": f"Bearer {token}"}
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url, headers=headers) as response:
#             response.raise_for_status()
#             return await response.text() # または .read() でバイト列
