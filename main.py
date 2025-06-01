import os
import logging

def clean_env_var(var_name, default=None):
    """
    環境変数からBOMと余分な空白を除去
    Secret Managerから読み込まれた値にBOMが含まれる場合があるため
    """
    value = os.environ.get(var_name, default)
    if value:
        # BOM（\ufeff）と前後の空白を除去
        return value.strip().lstrip('\ufeff').strip()
    return value

# Load environment variables from .env file only for local development
# Cloud Run環境では環境変数が直接設定されるため、.envファイルは不要
if os.path.exists('.env') and not os.getenv('GOOGLE_CLOUD_PROJECT'):
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file (local development)")
else:
    print("Using environment variables directly (Cloud Run or production)")

# Configure logging with validation
log_level = clean_env_var("LOG_LEVEL", "INFO").upper()
valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level not in valid_levels:
    print(f"Invalid LOG_LEVEL '{log_level}', using INFO instead")
    log_level = "INFO"

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to initialize and start the Meta-Analysis Slack Bot.
    """
    # Check SOCKET_MODE setting
    socket_mode = clean_env_var("SOCKET_MODE", "false").lower() == "true"
    
    # Ensure necessary environment variables are set
    required_env_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET"
    ]
    
    if socket_mode:
        required_env_vars.append("SLACK_APP_TOKEN")
        logger.info("Running in Socket Mode")
    else:
        logger.info("Running in HTTP Mode (Cloud Run compatible)")

    missing_vars = [var for var in required_env_vars if not clean_env_var(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        if socket_mode:
            logger.error("For Socket Mode, ensure SLACK_APP_TOKEN is set.")
        else:
            logger.error("For HTTP Mode, ensure PORT is set (defaults to 8080 if not specified).")
        logger.error("Please set them before running the bot. Refer to README.md for setup instructions.")
        return

    # Import the bot class only after ensuring env vars might be loaded
    # and basic logging is set up.
    try:
        from mcp.slack_bot import MetaAnalysisBot
    except ImportError as e:
        logger.error(f"Failed to import MetaAnalysisBot: {e}")
        logger.error("Ensure all dependencies are installed and the mcp package is correctly structured.")
        return
    except Exception as e:
        logger.error(f"An unexpected error occurred during import: {e}")
        return

    logger.info("Initializing MetaAnalysisBot...")
    try:
        bot = MetaAnalysisBot()
        logger.info("Starting MetaAnalysisBot...")
        bot.start()
    except Exception as e:
        logger.exception(f"An error occurred while initializing or starting the bot: {e}")


# ↓↓↓↓↓↓ ここから修正 ↓↓↓↓↓↓
from mcp.slack_bot import MetaAnalysisBot

# MetaAnalysisBotのインスタンスを作成
# この時点で環境変数が読み込まれ、基本的なロギングが設定されている必要がある
try:
    bot_instance = MetaAnalysisBot()
    # gunicornが参照するWSGIアプリケーションインスタンス
    app = bot_instance.app
    logger.info("MetaAnalysisBot instance created and 'app' exposed for gunicorn.")
except Exception as e:
    logger.exception(f"Failed to initialize MetaAnalysisBot or expose 'app': {e}")
    # エラーが発生した場合、gunicornが起動できないようにNoneを設定するなどの処理も検討可能
    app = None 

def main_socket_mode_start():
    """
    Main function to initialize and start the Meta-Analysis Slack Bot in Socket Mode.
    This function is intended to be called when __name__ == "__main__" and SOCKET_MODE is true.
    """
    # Check SOCKET_MODE setting
    # This function should only be called if socket_mode is true,
    # but we double-check here for safety or direct calls.
    socket_mode_env = clean_env_var("SOCKET_MODE", "false").lower() == "true"
    if not socket_mode_env:
        logger.warning("main_socket_mode_start called, but SOCKET_MODE is not true. Bot will not start in Socket Mode via this path.")
        return

    # (環境変数チェックはmain()から移動または共通化が必要だが、一旦bot_instanceの初期化に依存)
    # 必要な環境変数がbot_instanceの初期化時にチェックされている前提

    if bot_instance is None:
        logger.error("MetaAnalysisBot instance ('bot_instance') is None. Cannot start in Socket Mode.")
        return

    logger.info("Initializing and starting MetaAnalysisBot for Socket Mode...")
    try:
        # bot_instance.start() will handle the actual SocketModeHandler start
        bot_instance.start() 
    except Exception as e:
        logger.exception(f"An error occurred while starting the bot in Socket Mode: {e}")

if __name__ == "__main__":
    # HTTPモードの場合、gunicornはこのファイルをモジュールとしてロードし、
    # 'app'という名前のWSGIアプリケーションを探す。
    # Socketモードの場合は、このスクリプトが直接実行される。
    socket_mode_check = clean_env_var("SOCKET_MODE", "false").lower() == "true"
    if socket_mode_check:
        # main()関数はgunicornの起動ポイントと競合するため、
        # Socket Mode専用の起動関数を呼び出す
        main_socket_mode_start()
    elif app is None:
        # gunicornが起動しようとしたがappの初期化に失敗した場合
        logger.critical("Failed to initialize the WSGI 'app' instance for gunicorn. Exiting.")
    else:
        # HTTP Mode (gunicorn will use the 'app' instance defined globally)
        logger.info("Running in HTTP mode. Gunicorn will serve the 'app' instance.")
        # It's important that 'app' is defined at the module level for gunicorn.
        # No explicit start needed here as gunicorn handles it.
        pass
# ↑↑↑↑↑↑ ここまで修正 ↑↑↑↑↑↑
