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

if __name__ == "__main__":
    main()
