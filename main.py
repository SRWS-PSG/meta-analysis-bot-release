import os
import asyncio
import logging
import signal
import sys
from slack_bolt import App
from slack_bolt.adapter.wsgi import SlackRequestHandler

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration of the root logger
)

# Set specific loggers to DEBUG for troubleshooting
logging.getLogger('handlers.mention_handler').setLevel(logging.DEBUG)
logging.getLogger('handlers.csv_handler').setLevel(logging.DEBUG)
logging.getLogger('core.gemini_client').setLevel(logging.DEBUG)

from handlers.csv_handler import register_csv_handlers
from handlers.analysis_handler import register_analysis_handlers
from handlers.report_handler import register_report_handlers
from handlers.parameter_handler import register_parameter_handlers # 追加
from handlers.mention_handler import register_mention_handlers

# Slack App初期化
logger = logging.getLogger(__name__)
logger.info("Initializing Slack app...")

app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

logger.info("Slack app initialized successfully")

# Add middleware to log all events (for debugging)
@app.middleware
def log_request(logger, body, next):
    """Log all incoming requests for debugging"""
    logger.debug(f"=== INCOMING REQUEST ===")
    logger.debug(f"Request type: {body.get('type')}")
    if body.get('event'):
        logger.debug(f"Event type: {body['event'].get('type')}")
        logger.debug(f"Event subtype: {body['event'].get('subtype')}")
    logger.debug(f"Body keys: {list(body.keys())}")
    return next()

# 各ハンドラーを登録
register_csv_handlers(app)
register_analysis_handlers(app)
register_report_handlers(app)
register_parameter_handlers(app) # 追加
register_mention_handlers(app)

# 統一メッセージハンドラー（legacy style）
@app.event("message")
def handle_unified_message(event, client):
    """統一されたメッセージハンドラー - legacyスタイル"""
    logger.info(f"=== UNIFIED MESSAGE HANDLER ===")
    logger.info(f"Event type: {event.get('type')}, subtype: {event.get('subtype')}")
    logger.info(f"Text: {event.get('text', '')}")
    logger.info(f"Thread TS: {event.get('thread_ts')}")
    logger.info(f"Channel: {event.get('channel')}")
    logger.info(f"User: {event.get('user')}")
    logger.info(f"Bot ID: {event.get('bot_id')}")
    
    # Botメッセージは無視
    if event.get('bot_id'):
        logger.info("Ignoring bot message")
        return
    
    # スレッド内のメッセージのみ処理
    thread_ts = event.get('thread_ts')
    if not thread_ts:
        logger.info("Not a thread message, ignoring")
        return
    
    channel_id = event.get('channel')
    text = event.get('text', '')
    
    # メンション除去
    user_text = text
    if text.startswith('<@'):
        # メンションを除去
        import re
        user_text = re.sub(r'<@[^>]+>\s*', '', text).strip()
    
    # 会話状態を確認
    from utils.conversation_state import get_state
    state = get_state(thread_ts, channel_id)
    
    if not state:
        logger.info(f"No conversation state found for {channel_id}:{thread_ts}")
        return
    
    logger.info(f"Current state: {state.state}")
    
    # analysis_preference状態でパラメータ収集を処理
    if state.state == "analysis_preference":
        logger.info(f"Processing parameter input: {user_text}")
        
        # パラメータ収集を実行
        import asyncio
        import threading
        
        def run_parameter_processing():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def process_params():
                from handlers.parameter_handler import handle_natural_language_parameters
                
                # message オブジェクトを構築
                message = {
                    'channel': channel_id,
                    'thread_ts': thread_ts,
                    'text': user_text,
                    'user': event.get('user'),
                    'ts': event.get('ts')
                }
                
                # say 関数を定義
                async def say(text):
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)
                
                await handle_natural_language_parameters(message, say, client, logger)
            
            loop.run_until_complete(process_params())
            loop.close()
        
        # 別スレッドで実行
        thread = threading.Thread(target=run_parameter_processing)
        thread.start()
    else:
        logger.info(f"State {state.state} does not require parameter processing")

# グレースフルシャットダウンのハンドラー
def signal_handler(sig, frame):
    """シグナルハンドラー"""
    logger.info(f"Received signal {sig}. Starting graceful shutdown...")
    
    # mention_handlerのジョブマネージャーをシャットダウン
    try:
        from handlers.mention_handler import shutdown_job_manager
        shutdown_job_manager()
    except Exception as e:
        logger.error(f"Error during job manager shutdown: {e}")
    
    logger.info("Graceful shutdown complete")
    sys.exit(0)

# シグナルハンドラーを登録
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# テストハンドラーは削除（mention_handlerで処理されるため）

# Heroku用のハンドラー
handler = SlackRequestHandler(app)

# Gunicorn が探す WSGI callable
application = handler

if __name__ == "__main__":
    if os.environ.get("SOCKET_MODE", "false").lower() == "true":
        # ローカル開発用
        app.start(port=int(os.environ.get("PORT", 3000)))
    # Heroku用の起動ロジックはProcfile経由でGunicornが行うため削除
