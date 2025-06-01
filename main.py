import os
import asyncio
from slack_bolt import App
from slack_bolt.adapter.heroku import SlackRequestHandler

from handlers.csv_handler import register_csv_handlers
from handlers.analysis_handler import register_analysis_handlers
from handlers.report_handler import register_report_handlers
from handlers.parameter_handler import register_parameter_handlers # 追加

# Slack App初期化
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# 各ハンドラーを登録
register_csv_handlers(app)
register_analysis_handlers(app)
register_report_handlers(app)
register_parameter_handlers(app) # 追加

# Heroku用のハンドラー
handler = SlackRequestHandler(app)

# Flask互換のWSGIアプリケーション
def application(environ, start_response):
    return handler.handle(environ, start_response)

if __name__ == "__main__":
    if os.environ.get("SOCKET_MODE", "false").lower() == "true":
        # ローカル開発用
        app.start(port=int(os.environ.get("PORT", 3000)))
    else:
        # Heroku用
        port = int(os.environ.get("PORT", 8000))
        from wsgiref.simple_server import make_server
        server = make_server("0.0.0.0", port, application)
        server.serve_forever()
