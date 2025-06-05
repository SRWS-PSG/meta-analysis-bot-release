import asyncio # generate_report_async のために追加
from slack_bolt import App
from core.metadata_manager import MetadataManager
from core.gemini_client import GeminiClient
from utils.slack_utils import create_report_message

def register_report_handlers(app: App):
    """レポート生成関連のハンドラーを登録"""
    
    @app.action("generate_interpretation")
    def handle_interpretation_request(ack, body, client, logger):
        """解釈レポート生成ボタンのハンドラー"""
        ack()
        
        payload = MetadataManager.extract_from_body(body)
        
        if not payload or payload.get("stage") != "awaiting_interpretation":
            client.chat_postMessage(
                channel=body["channel"]["id"],
                thread_ts=body["message"]["ts"], # ボタンイベントの場合、元のメッセージのts
                text="❌ 解釈対象の解析結果が見つかりません。"
            )
            return
        
        asyncio.create_task(generate_report_async(
            payload=payload,
            channel_id=body["channel"]["id"],
            thread_ts=body["message"]["ts"], # ボタンイベントの場合、元のメッセージのts
            client=client,
            logger=logger
        ))
        
        client.chat_postMessage(
            channel=body["channel"]["id"],
            thread_ts=body["message"]["ts"], # ボタンイベントの場合、元のメッセージのts
            text="📝 解釈レポートを生成中..."
        )

async def generate_report_async(payload, channel_id, thread_ts, client, logger):
    """解釈レポートの非同期生成"""
    try:
        gemini_client = GeminiClient()
        interpretation = await gemini_client.generate_interpretation(
            result_summary=payload["result_summary"], # analysis_handlerから渡されるサマリー
            job_id=payload["job_id"]
        )
        
        report_metadata = MetadataManager.create_metadata("interpretation_generated", {
            "job_id": payload["job_id"],
            "interpretation_summary": interpretation.get("summary", "解釈の要約がありません。"), # Geminiからの応答構造に依存
            "full_interpretation": interpretation, # 完全な解釈結果も保存（圧縮対象になる可能性あり）
            "stage": "completed",
            "user_id": payload["user_id"],
            "original_file_id": payload.get("original_file_id"),
            "analysis_summary": payload.get("result_summary") # 元の解析サマリーも参照用に保持
        })
        
        report_text = create_report_message(interpretation)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=report_text,
            metadata=report_metadata
        )
        
    except Exception as e:
        logger.error(f"レポート生成エラー: {e}")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"❌ レポート生成中にエラーが発生しました: {str(e)}"
        )
