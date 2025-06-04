"""
会話状態管理ユーティリティ

スレッドごとのパラメータ収集状態を管理します。
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# メモリベースの簡易ストレージ（本番環境ではRedis等を推奨）
_conversation_states = {}

# 状態の有効期限（24時間）
STATE_EXPIRY_HOURS = 24

class ConversationState:
    """会話状態を管理するクラス"""
    
    def __init__(self, thread_ts: str, channel_id: str):
        self.thread_ts = thread_ts
        self.channel_id = channel_id
        self.key = f"{channel_id}:{thread_ts}"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.state = "COLLECTING_PARAMETERS"
        self.collected_params = {}
        self.csv_analysis = {}
        self.file_info = {}
        
    def update_params(self, params: Dict[str, Any]):
        """パラメータを更新"""
        self.collected_params.update(params)
        self.updated_at = datetime.now()
        
    def is_expired(self) -> bool:
        """状態が期限切れかチェック"""
        return datetime.now() - self.updated_at > timedelta(hours=STATE_EXPIRY_HOURS)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "thread_ts": self.thread_ts,
            "channel_id": self.channel_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "state": self.state,
            "collected_params": self.collected_params,
            "csv_analysis": self.csv_analysis,
            "file_info": self.file_info
        }

def get_or_create_state(thread_ts: str, channel_id: str) -> ConversationState:
    """会話状態を取得または作成"""
    key = f"{channel_id}:{thread_ts}"
    
    # 期限切れの状態をクリーンアップ
    cleanup_expired_states()
    
    if key not in _conversation_states:
        _conversation_states[key] = ConversationState(thread_ts, channel_id)
        logger.info(f"Created new conversation state for {key}")
    
    return _conversation_states[key]

def get_state(thread_ts: str, channel_id: str) -> Optional[ConversationState]:
    """会話状態を取得"""
    key = f"{channel_id}:{thread_ts}"
    state = _conversation_states.get(key)
    
    if state and not state.is_expired():
        return state
    return None

def save_state(state: ConversationState):
    """会話状態を保存"""
    _conversation_states[state.key] = state
    logger.info(f"Saved conversation state for {state.key}")

def delete_state(thread_ts: str, channel_id: str):
    """会話状態を削除"""
    key = f"{channel_id}:{thread_ts}"
    if key in _conversation_states:
        del _conversation_states[key]
        logger.info(f"Deleted conversation state for {key}")

def cleanup_expired_states():
    """期限切れの状態をクリーンアップ"""
    expired_keys = []
    for key, state in _conversation_states.items():
        if state.is_expired():
            expired_keys.append(key)
    
    for key in expired_keys:
        del _conversation_states[key]
        
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired conversation states")