import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# Useful for local development
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to initialize and start the Meta-Analysis Slack Bot.
    """
    # Ensure necessary environment variables are set
    required_env_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET"
    ]
    if os.environ.get("SOCKET_MODE", "false").lower() == "true":
        required_env_vars.append("SLACK_APP_TOKEN")

    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
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