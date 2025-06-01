# main.py ★修正版
import os
import logging
from slack_bolt.adapter.wsgi import SlackRequestHandler
from mcp.slack_bot import MetaAnalysisBot  # 既存クラス

# Configure logging (ensure clean_env_var is available or simplify for this context)
# For simplicity in this snippet, basicConfig is used.
# Consider re-integrating clean_env_var if needed for LOG_LEVEL.
log_level_env = os.environ.get("LOG_LEVEL", "INFO").upper()
valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
if log_level_env not in valid_levels:
    print(f"Invalid LOG_LEVEL '{log_level_env}', using INFO instead")
    log_level_env = "INFO"

logging.basicConfig(
    level=log_level_env,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# --- Environment Variable Check ---
# (Copied and adapted from original main.py for essential checks)
def clean_env_var(var_name, default=None):
    """
    環境変数からBOMと余分な空白を除去
    """
    value = os.environ.get(var_name, default)
    if value:
        return value.strip().lstrip('\ufeff').strip()
    return value

socket_mode_env = clean_env_var("SOCKET_MODE", "false").lower() == "true"

if socket_mode_env:
    logger.info("Socket Mode is configured. This main.py is intended for HTTP/Gunicorn.")
    # If Socket Mode is true, Gunicorn shouldn't be running this main:app.
    # The original main() or main_socket_mode_start() would be invoked directly.
    # This WSGI app definition is for HTTP mode.
    # Consider exiting or logging a critical error if gunicorn tries to run this in socket mode.

required_env_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"]
if socket_mode_env: # This check is more for direct execution context
    required_env_vars.append("SLACK_APP_TOKEN")

missing_vars = [var for var in required_env_vars if not clean_env_var(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    # This error should ideally prevent the app from starting if critical vars are missing.
    # For Gunicorn, this check happens at module load time.
    # Raising an exception here might be appropriate to stop Gunicorn.
    # raise RuntimeError(f"Missing environment variables: {', '.join(missing_vars)}")


# Bolt アプリ生成
# This instantiation might also have dependencies on env vars.
# Ensure MetaAnalysisBot handles its own necessary env var checks or they are done before this.
try:
    bot_instance = MetaAnalysisBot()
    bolt_app = bot_instance.app # Get the Bolt App instance from MetaAnalysisBot
    handler = SlackRequestHandler(bolt_app)  # path="/slack/events" が既定
    logger.info("MetaAnalysisBot and SlackRequestHandler initialized successfully for HTTP mode.")
except Exception as e:
    logger.critical(f"Failed to initialize MetaAnalysisBot or SlackRequestHandler: {e}", exc_info=True)
    # If initialization fails, Gunicorn should not serve a broken app.
    # Setting app to None or raising an exception can prevent this.
    bolt_app = None
    handler = None
    # raise # Re-raise the exception to stop Gunicorn from starting with a faulty app


def app(environ, start_response):
    """Gunicorn が呼び出す WSGI アプリ.

    - GET  / -> 200 OK (ヘルスチェック)
    - POST /slack/events -> Bolt へ委譲
    - その他 -> 404
    """
    if handler is None: # Check if handler initialization failed
        logger.error("WSGI app called, but SlackRequestHandler (handler) is None due to initialization failure.")
        start_response("500 Internal Server Error", [("Content-Type", "text/plain")])
        return [b"Application initialization failed"]

    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "")

    # Log incoming request details for easier debugging on Heroku
    logger.info(f"Incoming request: Method={method}, Path={path}")

    if path == "/slack/events":
        # Log Slack-specific headers and request body for /slack/events
        logger.info("--- Request to /slack/events ---")
        for k, v in environ.items():
            if k.startswith("HTTP_X_SLACK_") or k == "CONTENT_TYPE" or k == "CONTENT_LENGTH":
                logger.info(f"Header: {k}={v}")
        
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0))
            if content_length > 0:
                request_body = environ['wsgi.input'].read(content_length).decode('utf-8')
                logger.info(f"Request Body: {request_body}")
                # Put the body back for the handler to read. This needs careful handling
                # as wsgi.input is a stream. For simple logging, reading it once might be okay
                # if the handler re-reads or if Bolt handles this robustly.
                # A more robust way would be to wrap wsgi.input if multiple reads are needed.
                # For now, let's assume Bolt's handler will manage.
                # If issues arise, we might need to reset the stream:
                # environ['wsgi.input'] = io.BytesIO(request_body.encode('utf-8'))
            else:
                logger.info("Request Body: No content or content length is 0.")
        except Exception as e:
            logger.error(f"Error reading request body: {e}", exc_info=True)
        logger.info("--- End of /slack/events request details ---")

    if method == "GET" and path == "/":
        logger.info("Health check endpoint / called.")
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"OK"]

    if path == "/slack/events":
        # SlackRequestHandler expects to be called with the WSGI environ and start_response
        logger.info(f"Routing request to SlackRequestHandler for path: {path}")
        return handler(environ, start_response)

    logger.warn(f"Path not found: {path}. Responding with 404.")
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]

# ★ローカルデバッグ用 (Socket Modeがfalseの場合のみ意味がある)
if __name__ == "__main__":
    if not socket_mode_env: # Only run Werkzeug if not in Socket Mode
        if handler: # Check if handler was initialized
            from werkzeug.serving import run_simple
            port_str = clean_env_var("PORT", "3000")
            try:
                port = int(port_str)
            except ValueError:
                logger.error(f"Invalid PORT value: '{port_str}'. Defaulting to 3000.")
                port = 3000
            logger.info(f"Starting Werkzeug development server on 0.0.0.0:{port} for HTTP mode testing.")
            run_simple("0.0.0.0", port, app, use_reloader=True, use_debugger=True)
        else:
            logger.error("Cannot start Werkzeug server: SlackRequestHandler (handler) failed to initialize.")
    else:
        # If Socket Mode is true, this __main__ block should trigger the SocketModeHandler start.
        # The original main.py had a main_socket_mode_start() or similar.
        # This needs to be reconciled if direct execution in Socket Mode is still desired.
        logger.info("Socket Mode is true. To run in Socket Mode, execute the bot's Socket Mode entry point directly.")
        # Example: bot_instance.start() if bot_instance is available and handles mode switching.
        # For now, this __main__ is primarily for HTTP testing with Werkzeug.
        if bot_instance:
            logger.info("Attempting to start bot in Socket Mode via bot_instance.start()...")
            # This assumes bot_instance.start() checks SOCKET_MODE and starts SocketModeHandler
            try:
                bot_instance.start()
            except Exception as e:
                logger.critical(f"Failed to start bot in Socket Mode from __main__: {e}", exc_info=True)
        else:
            logger.error("Cannot start in Socket Mode: bot_instance is not available.")
