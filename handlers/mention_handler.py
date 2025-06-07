"""
Mentionハンドラー

ボットへのメンションやダイレクトメッセージを処理します。
"""
import logging
import re
import threading
import json
import os
import signal
import atexit
import time
from slack_bolt import App
from mcp_legacy.async_processing import AsyncJobManager

logger = logging.getLogger(__name__)

# グローバルジョブマネージャー
_job_manager = None

def get_job_manager():
    """ジョブマネージャーのシングルトンを取得"""
    global _job_manager
    if _job_manager is None:
        _job_manager = AsyncJobManager(max_workers=int(os.environ.get('MAX_CSV_WORKERS', '5')))
        # グレースフルシャットダウンの設定
        atexit.register(shutdown_job_manager)
    return _job_manager

def shutdown_job_manager():
    """ジョブマネージャーをシャットダウン"""
    global _job_manager
    if _job_manager:
        logger.info("Shutting down job manager...")
        _job_manager.executor.shutdown(wait=True, cancel_futures=False)
        logger.info("Job manager shutdown complete")

def _contains_csv_data(text: str) -> bool:
    """テキスト内にCSVデータが含まれているかチェック"""
    logger.info(f"CSV detection check for text: {text[:200]}...")  # 最初の200文字をログ
    
    lines = text.strip().split('\n')
    logger.info(f"Split into {len(lines)} lines")
    
    if len(lines) < 2:
        logger.info("Less than 2 lines, not CSV")
        return False
    
    # ファイル名らしき行は除外 (.csv で終わる行)
    non_filename_lines = [line for line in lines if not line.strip().endswith('.csv')]
    
    # 複数行あり、カンマ区切りのデータが含まれているかチェック
    csv_like_lines = 0
    for i, line in enumerate(non_filename_lines):
        line = line.strip()
        if not line:  # 空行をスキップ
            continue
            
        # より幅広い区切り文字を検出
        # 複数の連続スペースを区切り文字として検出
        has_separator = (',' in line or 
                        '\t' in line or 
                        re.search(r'\s{2,}', line) or  # 2つ以上の連続スペース
                        re.search(r'\s+\d+\s+', line))  # 数字を囲むスペース
        
        if has_separator:
            # 最低でも2つの列があるかチェック
            if '\t' in line:
                parts = line.split('\t')
            elif ',' in line:
                parts = line.split(',')
            else:
                # 複数スペースで分割
                parts = re.split(r'\s{2,}', line)
                if len(parts) == 1:  # 2つ以上のスペースで分割できない場合、単一スペースも試す
                    parts = line.split()
            
            parts = [p.strip() for p in parts if p.strip()]  # 空要素を除去
            
            if len(parts) >= 2:
                csv_like_lines += 1
                logger.info(f"Line {i+1} has {len(parts)} parts: {parts[:3]}...")  # 最初の3要素をログ
    
    threshold = max(2, len(non_filename_lines) * 0.5)
    is_csv = csv_like_lines >= threshold
    logger.info(f"CSV-like lines: {csv_like_lines}, threshold: {threshold}, is_csv: {is_csv}")
    
    return is_csv

def register_mention_handlers(app: App):
    """メンション関連のハンドラーを登録"""
    
    @app.event("app_mention")
    def handle_app_mention(body, event, client, logger, ack):
        """ボットがメンションされた時の処理"""
        # 即座にACKを返してSlackの3秒タイムアウトを回避
        ack()
        
        try:
            logger.info("=== APP MENTION EVENT RECEIVED ===")
            logger.info(f"Event timestamp: {event.get('ts')}")
            logger.info(f"Event type: {event.get('type')}")
            logger.info(f"Channel: {event.get('channel')}")
            logger.info(f"User: {event.get('user')}")
            
            # Log the full event in DEBUG mode
            logger.debug(f"Full event object: {json.dumps(event, ensure_ascii=False, indent=2)}")
            
            # Check if there are blocks, attachments, or files
            blocks = event.get("blocks", [])
            attachments = event.get("attachments", [])
            files = event.get("files", [])
            logger.info(f"Event has {len(blocks)} blocks, {len(attachments)} attachments, and {len(files)} files")
            
            # Log the full body for debugging
            logger.info(f"Full body keys: {list(body.keys()) if body else 'No body'}")
            logger.info(f"Full event keys: {list(event.keys())}")
            if blocks:
                logger.info(f"First block: {blocks[0] if blocks else 'No blocks'}")
                # Log all blocks for debugging
                for i, block in enumerate(blocks):
                    logger.info(f"Block {i}: type={block.get('type')}, keys={list(block.keys())}")
                    if block.get('type') == 'rich_text':
                        elements = block.get('elements', [])
                        for j, elem in enumerate(elements):
                            logger.info(f"  Element {j}: type={elem.get('type')}")
            
            # Check for files
            if files:
                logger.info(f"Files found: {files}")
            
            channel_id = event["channel"]
            user_id = event["user"]
            text = event.get("text", "")
            thread_ts = event.get("thread_ts", event["ts"])
            
            # メンションテキストからボットIDを除去
            bot_user_id = client.auth_test()["user_id"]
            clean_text = text.replace(f"<@{bot_user_id}>", "").strip()
            
            # If there are code blocks in the message, extract the text from them
            if blocks:
                code_block_text = ""
                for i, block in enumerate(blocks):
                    logger.debug(f"Processing block {i}: type={block.get('type')}")
                    if block.get("type") == "rich_text":
                        for j, element in enumerate(block.get("elements", [])):
                            logger.debug(f"  Processing element {j}: type={element.get('type')}")
                            # Check for both preformatted blocks and sections
                            if element.get("type") == "rich_text_preformatted":
                                # This is a code block
                                logger.info(f"Found rich_text_preformatted block at block[{i}].element[{j}]")
                                for k, elem in enumerate(element.get("elements", [])):
                                    if elem.get("type") == "text":
                                        text_content = elem.get("text", "")
                                        logger.debug(f"    Text element {k}: {text_content[:50]}...")
                                        code_block_text += text_content
                            elif element.get("type") == "rich_text_section":
                                # Check for inline code or regular text that might contain CSV
                                for k, elem in enumerate(element.get("elements", [])):
                                    if elem.get("type") == "text":
                                        # Skip bot mentions
                                        elem_text = elem.get("text", "")
                                        if not elem_text.startswith(f"<@{bot_user_id}>"):
                                            code_block_text += elem_text
                if code_block_text:
                    logger.info(f"Found code block text: {code_block_text[:100]}...")
                    # Always use code block text if it exists
                    clean_text = code_block_text
                else:
                    logger.info("No code blocks found in rich_text elements")
            
            # Fallback: Check if the original text contains code block markers
            if not clean_text or (not _contains_csv_data(clean_text) and "```" in text):
                logger.info("Checking for code blocks in original text field...")
                # Extract text between ``` markers
                import re
                code_block_matches = re.findall(r'```(?:\w+)?\n?(.*?)```', text, re.DOTALL)
                if code_block_matches:
                    logger.info(f"Found {len(code_block_matches)} code blocks in text field")
                    # Use the first code block
                    potential_csv = code_block_matches[0].strip()
                    if _contains_csv_data(potential_csv):
                        clean_text = potential_csv
                        logger.info(f"Using code block from text field: {clean_text[:100]}...")
            
            logger.info(f"=== App Mention Debug ===")
            logger.info(f"Original text: {repr(text)}")
            logger.info(f"Bot user ID: {bot_user_id}")
            logger.info(f"Clean text: {repr(clean_text)}")
            logger.info(f"Clean text length: {len(clean_text)}")
            logger.info(f"Clean text first 100 chars: {clean_text[:100] if clean_text else 'EMPTY'}")
            
            # Check for CSV files
            csv_files = [f for f in files if f.get("name", "").lower().endswith(".csv")]
            if csv_files:
                # CSVファイルが添付されている場合
                logger.info(f"CSV files found: {[f.get('name') for f in csv_files]}")
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text="📊 CSVファイルを検出しました。分析を開始します..."
                )
                
                # CSV処理を実行
                from handlers.csv_handler import process_csv_async
                import asyncio
                
                job_manager = get_job_manager()
                
                def run_csv_processing_in_event_loop():
                    """イベントループ内でCSV処理を実行"""
                    try:
                        # 新しいイベントループを作成
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # 各CSVファイルを処理
                        for csv_file in csv_files:
                            logger.info(f"Processing CSV file: {csv_file.get('name', 'unknown')} via job manager")
                            try:
                                loop.run_until_complete(process_csv_async(
                                    file_info=csv_file,
                                    channel_id=channel_id,
                                    user_id=user_id,
                                    client=client,
                                    logger=logger,
                                    thread_ts=thread_ts
                                ))
                            except Exception as file_error:
                                logger.error(f"Error processing {csv_file.get('name')}: {file_error}", exc_info=True)
                                # ファイル単位のエラーを通知
                                try:
                                    client.chat_postMessage(
                                        channel=channel_id,
                                        thread_ts=thread_ts,
                                        text=f"❌ {csv_file.get('name', 'CSVファイル')}の処理中にエラーが発生しました: {str(file_error)}"
                                    )
                                except Exception as notify_error:
                                    logger.error(f"Failed to notify file error: {notify_error}")
                        
                        loop.close()
                        logger.info("CSV processing completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Error in CSV processing job: {e}", exc_info=True)
                        # 全体的なエラーを通知
                        try:
                            client.chat_postMessage(
                                channel=channel_id,
                                thread_ts=thread_ts,
                                text=f"❌ CSV処理中にエラーが発生しました: {str(e)}"
                            )
                        except Exception as notify_error:
                            logger.error(f"Failed to notify error: {notify_error}")
                
                # ジョブをサブミット
                job_id = job_manager.submit_job(
                    job_id=f"csv_processing_{channel_id}_{thread_ts}_{int(time.time())}",
                    func=run_csv_processing_in_event_loop
                )
                logger.info(f"CSV processing job submitted with ID: {job_id}")
                return
            
            # スレッド内メッセージの場合、既存の会話状態をチェック
            if event.get("thread_ts"):
                logger.info(f"Processing thread message. Thread TS: {event['thread_ts']}")
                
                # 会話状態を確認
                from utils.conversation_state import get_or_create_state, DialogState
                try:
                    state = get_or_create_state(event["thread_ts"], channel_id)
                    logger.info(f"Current conversation state: {state.state}")
                    
                    # パラメータ収集中の場合
                    if state.state == DialogState.ANALYSIS_PREFERENCE:
                        logger.info(f"Processing parameter collection in thread {event['thread_ts']}: {clean_text}")
                        
                        # パラメータ収集を非同期で実行
                        import asyncio
                        from handlers.parameter_handler import handle_natural_language_parameters
                        
                        def run_parameter_processing():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            async def process_params():
                                # messageオブジェクトを構築
                                message = {
                                    "channel": channel_id,
                                    "thread_ts": event["thread_ts"],
                                    "text": clean_text,
                                    "user": user_id,
                                    "ts": event["ts"]
                                }
                                
                                # say 関数を定義
                                async def say(text):
                                    client.chat_postMessage(channel=channel_id, thread_ts=event["thread_ts"], text=text)
                                
                                await handle_natural_language_parameters(message, say, client, logger)
                            
                            loop.run_until_complete(process_params())
                            loop.close()
                        
                        # ジョブとして実行
                        job_manager = get_job_manager()
                        job_id = job_manager.submit_job(
                            job_id=f"parameter_collection_{channel_id}_{event['thread_ts']}_{int(time.time())}",
                            func=run_parameter_processing
                        )
                        logger.info(f"Parameter collection job submitted with ID: {job_id}")
                        return
                        
                except Exception as e:
                    logger.error(f"Error checking conversation state: {e}")
            
            if not clean_text:
                # メンションのみの場合はヘルプメッセージを表示
                help_text = (
                    "👋 こんにちは！メタ解析ボットです。\n\n"
                    "使い方:\n"
                    "1. CSVファイルをアップロードしてください\n"
                    "2. ボットが自動でメタ解析に適したデータかチェックします\n"
                    "3. 適していれば解析パラメータを対話で設定し、\n"
                    "4. 解析を実行してレポートを返却します\n\n"
                    "お困りの場合は、CSVファイルをアップロードしてお試しください！"
                )
                
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=help_text
                )
            else:
                # CSVデータが含まれているかチェック
                logger.info(f"Checking for CSV data in clean_text...")
                contains_csv = _contains_csv_data(clean_text)
                logger.info(f"CSV detection result: {contains_csv}")
                
                if contains_csv:
                    # CSVデータが含まれている場合は処理する
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text="📊 CSVデータを検出しました。分析を開始します..."
                    )
                    
                    # CSV処理を実行
                    from handlers.csv_handler import process_csv_text_async
                    import asyncio
                    
                    job_manager = get_job_manager()
                    
                    def run_csv_text_processing_in_event_loop():
                        """イベントループ内でCSVテキスト処理を実行"""
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            logger.info(f"Processing CSV text data via job manager")
                            loop.run_until_complete(process_csv_text_async(
                                csv_text=clean_text,
                                channel_id=channel_id,
                                user_id=user_id,
                                thread_ts=thread_ts,
                                client=client,
                                logger=logger
                            ))
                            
                            loop.close()
                            logger.info("CSV text processing completed successfully")
                            
                        except Exception as e:
                            logger.error(f"Error in CSV text processing job: {e}", exc_info=True)
                            # エラーをSlackに通知
                            try:
                                client.chat_postMessage(
                                    channel=channel_id,
                                    thread_ts=thread_ts,
                                    text=f"❌ CSVデータ処理中にエラーが発生しました: {str(e)}"
                                )
                            except Exception as notify_error:
                                logger.error(f"Failed to notify error: {notify_error}")
                    
                    # ジョブをサブミット
                    job_id = job_manager.submit_job(
                        job_id=f"csv_text_processing_{channel_id}_{thread_ts}_{int(time.time())}",
                        func=run_csv_text_processing_in_event_loop
                    )
                    logger.info(f"CSV text processing job submitted with ID: {job_id}")
                else:
                    # その他のテキストが含まれている場合
                    response_text = (
                        f"メッセージを受信しました: 「{clean_text}」\n\n"
                        "現在、このボットはCSVファイルのメタ解析に特化しています。\n"
                        "CSVファイルをアップロードするか、CSVデータをテキストとして貼り付けていただければ、解析をお手伝いできます！"
                    )
                    
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=response_text
                    )
                
        except Exception as e:
            logger.error(f"Error handling app mention: {e}")
            try:
                client.chat_postMessage(
                    channel=event["channel"],
                    thread_ts=event.get("thread_ts", event["ts"]),
                    text="申し訳ございません。メッセージの処理中にエラーが発生しました。"
                )
            except Exception as reply_error:
                logger.error(f"Error sending error message: {reply_error}")
    
    @app.event("message")
    def handle_direct_message(body, event, client, logger, ack):
        """ダイレクトメッセージとスレッド返信の処理"""
        # 即座にACKを返してSlackの3秒タイムアウトを回避
        ack()
        
        try:
            # ボット自身のメッセージは無視
            if event.get("bot_id"):
                return
            
            # スレッド内のメッセージかチェック
            is_thread_message = "thread_ts" in event and event.get("ts") != event.get("thread_ts")
            
            # チャンネルタイプを確認
            channel_type = event.get("channel_type")
            
            # ファイルの確認
            files = event.get("files", [])
            
            # DM、スレッド内メッセージ、または"thread_ts"が存在する場合（スレッド参加者）に処理
            has_thread_ts = "thread_ts" in event
            if channel_type == "im" or is_thread_message or has_thread_ts:
                text = event.get("text", "")
                thread_ts = event.get("thread_ts", event.get("ts"))  # 必要に応じてイベントTSをフォールバック
                channel_id = event["channel"]
                user_id = event["user"]
                
                logger.info(f"Message in thread or DM received: {text[:100]}...")
                logger.info(f"Files in message: {len(files)} files")
                logger.info(f"Thread TS: {thread_ts}, Channel: {channel_id}, Is thread message: {is_thread_message}")
                
                # CSVファイルがあるかチェック
                csv_files = [f for f in files if f.get("name", "").lower().endswith(".csv")]
                if csv_files:
                    # CSVファイルが添付されている場合
                    
                    logger.info(f"CSV files found in thread: {[f.get('name') for f in csv_files]}")
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text="📊 CSVファイルを検出しました。分析を開始します..."
                    )
                    
                    # CSV処理を実行
                    from handlers.csv_handler import process_csv_async
                    import asyncio
                    
                    job_manager = get_job_manager()
                    
                    def run_dm_csv_processing_in_event_loop():
                        """ダイレクトメッセージ内のCSV処理を実行"""
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            for csv_file in csv_files:
                                logger.info(f"Processing CSV file in DM: {csv_file.get('name', 'unknown')}")
                                try:
                                    loop.run_until_complete(process_csv_async(
                                        file_info=csv_file,
                                        channel_id=channel_id,
                                        user_id=user_id,
                                        client=client,
                                        logger=logger,
                                        thread_ts=thread_ts
                                    ))
                                except Exception as file_error:
                                    logger.error(f"Error processing {csv_file.get('name')} in DM: {file_error}", exc_info=True)
                                    try:
                                        client.chat_postMessage(
                                            channel=channel_id,
                                            thread_ts=thread_ts,
                                            text=f"❌ {csv_file.get('name', 'CSVファイル')}の処理中にエラーが発生しました: {str(file_error)}"
                                        )
                                    except Exception as notify_error:
                                        logger.error(f"Failed to notify file error in DM: {notify_error}")
                            
                            loop.close()
                            logger.info("DM CSV processing completed successfully")
                            
                        except Exception as e:
                            logger.error(f"Error in DM CSV processing job: {e}", exc_info=True)
                            try:
                                client.chat_postMessage(
                                    channel=channel_id,
                                    thread_ts=thread_ts,
                                    text=f"❌ CSV処理中にエラーが発生しました: {str(e)}"
                                )
                            except Exception as notify_error:
                                logger.error(f"Failed to notify error: {notify_error}")
                    
                    # ジョブをサブミット
                    job_id = job_manager.submit_job(
                        job_id=f"dm_csv_processing_{channel_id}_{thread_ts}_{int(time.time())}",
                        func=run_dm_csv_processing_in_event_loop
                    )
                    logger.info(f"DM CSV processing job submitted with ID: {job_id}")
                # CSVデータが含まれているかチェック
                elif _contains_csv_data(text):
                    # CSVデータが含まれている場合は処理する
                    
                    client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text="📊 CSVデータを検出しました。分析を開始します..."
                    )
                    
                    # CSV処理を実行
                    from handlers.csv_handler import process_csv_text_async
                    import asyncio
                    
                    job_manager = get_job_manager()
                    
                    def run_dm_csv_text_processing_in_event_loop():
                        """ダイレクトメッセージ内のCSVテキスト処理を実行"""
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            logger.info("Processing CSV text data in DM via job manager")
                            loop.run_until_complete(process_csv_text_async(
                                csv_text=text,
                                channel_id=channel_id,
                                user_id=user_id,
                                thread_ts=thread_ts,
                                client=client,
                                logger=logger
                            ))
                            
                            loop.close()
                            logger.info("DM CSV text processing completed successfully")
                            
                        except Exception as e:
                            logger.error(f"Error in DM CSV text processing job: {e}", exc_info=True)
                            try:
                                client.chat_postMessage(
                                    channel=channel_id,
                                    thread_ts=thread_ts,
                                    text=f"❌ CSVデータ処理中にエラーが発生しました: {str(e)}"
                                )
                            except Exception as notify_error:
                                logger.error(f"Failed to notify error: {notify_error}")
                    
                    # ジョブをサブミット
                    job_id = job_manager.submit_job(
                        job_id=f"dm_csv_text_processing_{channel_id}_{thread_ts}_{int(time.time())}",
                        func=run_dm_csv_text_processing_in_event_loop
                    )
                    logger.info(f"DM CSV text processing job submitted with ID: {job_id}")
                else:
                    # CSVファイルがない場合、パラメータ収集の対話を処理する可能性がある
                    # 会話状態をチェック
                    from utils.conversation_state import get_state
                    logger.info(f"Checking conversation state for thread_ts={thread_ts}, channel_id={channel_id}")
                    state = get_state(thread_ts, channel_id)
                    logger.info(f"Retrieved state: {state.state if state else 'None'}")
                    
                    from utils.conversation_state import DialogState
                    if state and state.state == DialogState.ANALYSIS_PREFERENCE:
                        # パラメータ収集中の場合
                        logger.info(f"Processing parameter collection in thread {thread_ts}: {text}")
                        
                        # パラメータ収集を非同期で実行
                        import asyncio
                        from handlers.parameter_handler import handle_natural_language_parameters
                        
                        def run_parameter_processing():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                            async def process_params():
                                # message オブジェクトを構築
                                message = {
                                    'channel': channel_id,
                                    'thread_ts': thread_ts,
                                    'text': text,
                                    'user': user_id,
                                    'ts': event.get('ts')
                                }
                                
                                # say 関数を定義
                                async def say(text):
                                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)
                                
                                await handle_natural_language_parameters(message, say, client, logger)
                            
                            loop.run_until_complete(process_params())
                            loop.close()
                        
                        # ジョブとして実行
                        job_manager = get_job_manager()
                        job_id = job_manager.submit_job(
                            job_id=f"param_collection_{channel_id}_{thread_ts}_{int(time.time())}",
                            func=run_parameter_processing
                        )
                        logger.info(f"Parameter collection job submitted with ID: {job_id}")
                    elif channel_type == "im":
                        # DMでCSVデータがない場合のみヘルプメッセージ
                        help_text = (
                            "👋 ダイレクトメッセージありがとうございます！\n\n"
                            "メタ解析ボットは以下の手順でご利用いただけます:\n"
                            "1. CSVファイルをこのチャットにアップロードしてください\n"
                            "2. 自動でデータを分析します\n"
                            "3. メタ解析の設定を行います\n"
                            "4. 解析を実行して結果を表示します\n\n"
                            "まずはCSVファイルをアップロードしてお試しください！"
                        )
                        
                        client.chat_postMessage(
                            channel=event["channel"],
                            text=help_text
                        )
                
        except Exception as e:
            logger.error(f"Error handling direct message: {e}")