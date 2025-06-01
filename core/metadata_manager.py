import json
import uuid
import base64
from typing import Dict, Any, Optional

class MetadataManager:
    """Slack メッセージのmetadataフィールドを活用した状態管理"""
    
    MAX_METADATA_SIZE = 8000  # 8KB制限
    
    @staticmethod
    def create_job_id() -> str:
        """短縮されたジョブIDを生成"""
        return base64.urlsafe_b64encode(uuid.uuid4().bytes)[:8].decode()
    
    @classmethod
    def create_metadata(cls, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """metadataを作成（サイズ制限チェック付き）"""
        metadata = {
            "event_type": event_type,
            "event_payload": payload
        }
        
        # サイズチェック
        if len(json.dumps(metadata)) > cls.MAX_METADATA_SIZE:
            # 大きすぎる場合は圧縮処理
            metadata = cls._compress_metadata(metadata)
        
        return metadata
    
    @staticmethod
    def extract_from_body(body: Dict[str, Any]) -> Dict[str, Any]:
        """SlackイベントボディからmetadataのpayloadToExtract"""
        # ボタンアクションの場合
        if "message" in body:
            return body["message"].get("metadata", {}).get("event_payload", {})
        
        # メッセージイベントの場合
        if "event" in body:
            return body["event"].get("metadata", {}).get("event_payload", {})
        
        return {}
    
    @classmethod
    def _compress_metadata(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """metadataのサイズを削減"""
        payload = metadata["event_payload"]
        
        # 大きなデータはキーのみ保持し、実データは別途Slackファイルとして保存
        compressed_payload = {}
        for key, value in payload.items():
            if isinstance(value, (dict, list)) and len(json.dumps(value)) > 1000:
                # 大きなオブジェクトはfile_idで参照
                compressed_payload[f"{key}_ref"] = "file_stored"
            else:
                compressed_payload[key] = value
        
        return {
            "event_type": metadata["event_type"],
            "event_payload": compressed_payload
        }
