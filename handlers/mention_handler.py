"""
Mentionハンドラー

ボットへのメンションやダイレクトメッセージを処理します。
"""
import logging
from slack_bolt import App

logger = logging.getLogger(__name__)

def register_mention_handlers(app: App):
    """メンション関連のハンドラーを登録"""
    
    @app.event("app_mention")
    def handle_app_mention(body, event, client, logger):
        """ボットがメンションされた時の処理"""
        try:
            logger.info(f"App mention received: {event}")
            
            channel_id = event["channel"]
            user_id = event["user"]
            text = event.get("text", "")
            thread_ts = event.get("thread_ts", event["ts"])
            
            # メンションテキストからボットIDを除去
            bot_user_id = client.auth_test()["user_id"]
            clean_text = text.replace(f"<@{bot_user_id}>", "").strip()
            
            if not clean_text:
                # メンションのみの場合はヘルプメッセージを表示
                help_text = (
                    "👋 こんにちは！メタ解析ボットです。\n\n"
                    "使い方:\n"
                    "1. CSVファイルをアップロードしてください\n"
                    "2. ボットが自動でメタ解析に適したデータかチェックします\n"
                    "3. 適していれば解析パラメータを設定できます\n"
                    "4. 解析を実行して結果を確認できます\n\n"
                    "お困りの場合は、CSVファイルをアップロードしてお試しください！"
                )
                
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=help_text
                )
            else:
                # その他のテキストが含まれている場合
                response_text = (
                    f"メッセージを受信しました: 「{clean_text}」\n\n"
                    "現在、このボットはCSVファイルのメタ解析に特化しています。\n"
                    "CSVファイルをアップロードしていただければ、解析をお手伝いできます！"
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
    def handle_direct_message(body, event, client, logger):
        """ダイレクトメッセージの処理"""
        try:
            # DM（ダイレクトメッセージ）またはボットが参加しているチャンネルでのメッセージ
            # ボットのmention以外でも反応する場合の処理
            
            # ボット自身のメッセージは無視
            if event.get("bot_id"):
                return
                
            # ファイル共有メッセージは csv_handler で処理されるのでここでは無視
            if event.get("subtype") == "file_share":
                return
                
            # チャンネルタイプを確認してDMのみ処理
            channel_type = event.get("channel_type")
            if channel_type == "im":  # ダイレクトメッセージ
                logger.info(f"Direct message received: {event}")
                
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