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
