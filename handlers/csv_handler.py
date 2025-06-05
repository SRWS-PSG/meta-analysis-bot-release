import asyncio
import threading
import time
import logging
from slack_bolt import App
from core.metadata_manager import MetadataManager
from core.gemini_client import GeminiClient
from utils.slack_utils import create_unsuitable_csv_message, create_analysis_start_message
from utils.file_utils import download_slack_file_content_async # download_slack_file_content_async をインポート
from utils.conversation_state import get_or_create_state, save_state

logger = logging.getLogger(__name__)

def register_csv_handlers(app: App):
    """CSV関連のハンドラーを登録"""
    
    @app.event("file_shared")
    def handle_file_upload(body, client, event, logger):
        """ファイルアップロード時の処理"""
        logger.info(f"=== FILE_SHARED EVENT RECEIVED ===")
        logger.info(f"Event: {event}")
        file_info = event.get("file")
        
        if not file_info or not file_info.get("name", "").endswith(".csv"):
            logger.info(f"Not a CSV file or no file info. File name: {file_info.get('name', 'No file') if file_info else 'No file info'}")
            return
        
        logger.info(f"CSV file detected: {file_info.get('name')}")
        
        # 非同期でCSV分析を実行
        import threading
        
        def run_async_csv_processing():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(process_csv_async(
                file_info=file_info,
                channel_id=event["channel_id"],
                user_id=event["user_id"],
                client=client,
                logger=logger
            ))
            loop.close()
        
        thread = threading.Thread(target=run_async_csv_processing)
        thread.start()
        logger.info(f"Started thread for CSV processing: {thread.name}")

async def process_csv_text_async(csv_text, channel_id, user_id, thread_ts, client, logger):
    """テキスト形式のCSVデータを処理する"""
    try:
        logger.info(f"=== CSV TEXT PROCESSING STARTED ===")
        logger.info(f"Starting CSV text processing. Text size: {len(csv_text)} chars")
        logger.info(f"First 200 chars of CSV text: {csv_text[:200]}...")
        
        # Gemini APIでCSV分析
        logger.info("Creating GeminiClient instance...")
        gemini_client = GeminiClient()
        logger.info("Calling Gemini API to analyze CSV...")
        analysis_result = await gemini_client.analyze_csv(csv_text)
        logger.info(f"Gemini analysis result: is_suitable={analysis_result.get('is_suitable')}, reason={analysis_result.get('reason', 'N/A')[:100]}...")
        
        if not analysis_result.get("is_suitable", False):
            # メタ解析に適さない場合
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=create_unsuitable_csv_message(analysis_result.get('reason', '詳細不明'))
            )
            return
        
        # メタデータ作成
        job_id = MetadataManager.create_job_id()
        
        # 直接自然言語パラメータ収集を開始
        analysis_summary = create_analysis_start_message(analysis_result)
        
        response_message = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=analysis_summary
        )
        
        if response_message and response_message.get("ok"):
            msg_ts = response_message.get("ts")
            msg_channel = response_message.get("channel")

            # 会話状態を初期化
            state = get_or_create_state(thread_ts, channel_id)
            state.csv_analysis = analysis_result
            state.file_info = {
                "job_id": job_id,
                "csv_text": csv_text,
                "user_id": user_id,
                "original_filename": "data.csv"
            }
            # パラメータ収集状態に移行
            from utils.conversation_state import DialogState
            state.update_state(DialogState.ANALYSIS_PREFERENCE)
            save_state(state)
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
        error_details = str(e)
        
        if "GEMINI_API_KEY" in error_details:
            error_message += "\n⚠️ Gemini APIキーが設定されていません。"
        elif "APIError" in error_details or "api" in error_details.lower():
            error_message += f"\n⚠️ Gemini API エラー: {error_details}"
        elif "analyze" in error_details.lower():
            error_message += "\n⚠️ CSV分析中にエラーが発生しました。"
        else:
            error_message += f"\n⚠️ エラー詳細: {error_details}"
        
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=error_message
        )

async def process_csv_async(file_info, channel_id, user_id, client, logger, thread_ts=None):
    """CSVファイルの非同期分析処理"""
    start_time = time.time()
    try:
        logger.info(f"=== CSV FILE PROCESSING STARTED ===")
        logger.info(f"Starting CSV processing for file: {file_info.get('name', 'unknown')}")
        logger.info(f"File info keys: {list(file_info.keys())}")
        logger.info(f"Channel ID: {channel_id}, User ID: {user_id}, Thread TS: {thread_ts}")
        logger.info(f"Processing in thread: {threading.current_thread().name}")
        
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
        logger.info("Creating GeminiClient instance...")
        gemini_client = GeminiClient()
        logger.info("Calling Gemini API to analyze CSV...")
        analysis_result = await gemini_client.analyze_csv(csv_content)
        logger.info(f"Gemini analysis result: is_suitable={analysis_result.get('is_suitable')}, reason={analysis_result.get('reason', 'N/A')[:100]}...")
        
        if not analysis_result.get("is_suitable", False):
            # メタ解析に適さない場合
            message_kwargs = {
                "channel": channel_id,
                "text": create_unsuitable_csv_message(analysis_result.get('reason', '詳細不明'))
            }
            if thread_ts:
                message_kwargs["thread_ts"] = thread_ts
            client.chat_postMessage(**message_kwargs)
            return
        
        # メタデータ作成
        job_id = MetadataManager.create_job_id()
        
        # 直接自然言語パラメータ収集を開始
        analysis_summary = create_analysis_start_message(analysis_result)
        
        message_kwargs = {
            "channel": channel_id,
            "text": analysis_summary
        }
        if thread_ts:
            message_kwargs["thread_ts"] = thread_ts
        response_message = client.chat_postMessage(**message_kwargs)
        
        if response_message and response_message.get("ok"):
            msg_ts = response_message.get("ts")
            msg_channel = response_message.get("channel")

            # 会話状態を初期化
            effective_thread_ts = thread_ts if thread_ts else msg_ts
            state = get_or_create_state(effective_thread_ts, channel_id)
            state.csv_analysis = analysis_result
            state.file_info = {
                "job_id": job_id,
                "file_id": file_info["id"],
                "file_url": file_info["url_private_download"],
                "original_filename": file_info.get("name", "data.csv"),
                "user_id": user_id
            }
            # パラメータ収集状態に移行
            from utils.conversation_state import DialogState
            state.update_state(DialogState.ANALYSIS_PREFERENCE)
            save_state(state)
            logger.info(f"CSV分析完了、自然言語パラメータ収集を開始しました (Job ID: {job_id}) ts: {msg_ts}")
            logger.info(f"CSV processing completed successfully in {time.time() - start_time:.2f} seconds")
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
        elapsed_time = time.time() - start_time
        logger.error(f"CSV処理エラー after {elapsed_time:.2f} seconds: {e}", exc_info=True)
        
        # より詳細なエラー情報を提供
        error_message = "❌ CSVファイルの処理中にエラーが発生しました。"
        error_details = str(e)
        
        if "GEMINI_API_KEY" in error_details:
            error_message += "\n⚠️ Gemini APIキーが設定されていません。"
        elif "APIError" in error_details or "api" in error_details.lower():
            error_message += f"\n⚠️ Gemini API エラー: {error_details}"
        elif "download" in error_details.lower():
            error_message += "\n⚠️ ファイルのダウンロードに失敗しました。"
        elif "analyze" in error_details.lower():
            error_message += "\n⚠️ CSV分析中にエラーが発生しました。"
        else:
            error_message += f"\n⚠️ エラー詳細: {error_details}"
        
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
