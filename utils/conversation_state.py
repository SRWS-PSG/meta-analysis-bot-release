"""
会話状態管理ユーティリティ

スレッドごとのパラメータ収集状態を管理します。
"""
import logging
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# ストレージバックエンド設定
STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'memory').lower()

# 状態の有効期限（48時間に更新）
STATE_EXPIRY_HOURS = int(os.environ.get('CONTEXT_RETENTION_HOURS', '48'))

# 会話履歴の最大保持件数
MAX_HISTORY_LENGTH = int(os.environ.get('MAX_HISTORY_LENGTH', '20'))

class DialogState(str, Enum):
    """CLAUDE.mdの要件に準拠した5つの状態"""
    WAITING_FOR_FILE = "waiting_for_file"
    PROCESSING_FILE = "processing_file"
    ANALYSIS_PREFERENCE = "analysis_preference"
    ANALYSIS_RUNNING = "analysis_running"
    POST_ANALYSIS = "post_analysis"

class ConversationState:
    """会話状態を管理するクラス"""
    
    def __init__(self, thread_ts: str, channel_id: str):
        self.thread_ts = thread_ts
        self.channel_id = channel_id
        self.key = f"{channel_id}:{thread_ts}"
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.state = DialogState.WAITING_FOR_FILE
        self.conversation_history = []
        self.job_status = None
        self.analysis_params = {}
        self.collected_params = {}
        self.csv_analysis = {}
        self.file_info = {}
        self.async_job_status = {}
        
    def update_params(self, params: Dict[str, Any]):
        """パラメータを更新"""
        self.collected_params.update(params)
        self.updated_at = datetime.now()
        
    def update_state(self, new_state: DialogState):
        """状態を更新"""
        self.state = new_state
        self.updated_at = datetime.now()
        
    def add_conversation(self, role: str, content: str):
        """会話履歴を追加（最大件数制限あり）"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # 最大件数を超えた場合は古い履歴を削除
        if len(self.conversation_history) > MAX_HISTORY_LENGTH:
            self.conversation_history = self.conversation_history[-MAX_HISTORY_LENGTH:]
        self.updated_at = datetime.now()
    
    def limit_history(self, max_messages: int):
        """会話履歴を指定件数に制限"""
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]
        self.updated_at = datetime.now()
        
    def is_expired(self) -> bool:
        """状態が期限切れかチェック"""
        return datetime.now() - self.updated_at > timedelta(hours=STATE_EXPIRY_HOURS)
    
    def is_valid(self, retention_hours: Optional[int] = None) -> bool:
        """状態が有効かチェック（カスタム保持期間対応）"""
        if retention_hours is None:
            retention_hours = STATE_EXPIRY_HOURS
        return datetime.now() - self.created_at <= timedelta(hours=retention_hours)
        
    def is_ready_for_analysis(self) -> bool:
        """解析実行可能かチェック"""
        required_params = ['effect_size', 'model_type']
        return all(param in self.collected_params for param in required_params)
    
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
            "file_info": self.file_info,
            "conversation_history": self.conversation_history,
            "job_status": self.job_status,
            "analysis_params": self.analysis_params,
            "async_job_status": self.async_job_status
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """辞書から復元"""
        state = cls(data['thread_ts'], data['channel_id'])
        state.created_at = datetime.fromisoformat(data['created_at'])
        state.updated_at = datetime.fromisoformat(data['updated_at'])
        state.state = data['state']
        state.collected_params = data.get('collected_params', {})
        state.csv_analysis = data.get('csv_analysis', {})
        state.file_info = data.get('file_info', {})
        state.conversation_history = data.get('conversation_history', [])
        state.job_status = data.get('job_status')
        state.analysis_params = data.get('analysis_params', {})
        state.async_job_status = data.get('async_job_status', {})
        return state

# ストレージバックエンドの初期化
_storage_backend = None
_memory_store = {}

def get_storage_backend():
    """ストレージバックエンドを取得（テスト用に公開）"""
    return _get_storage_backend()

def _get_storage_backend():
    """ストレージバックエンドを取得"""
    global _storage_backend
    if _storage_backend is None:
        if STORAGE_BACKEND == 'redis':
            try:
                import redis
                redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
                _storage_backend = redis.from_url(redis_url, decode_responses=True)
                _storage_backend.ping()  # 接続テスト
                logger.info("Redis storage backend initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Redis: {e}, falling back to memory")
                _storage_backend = 'memory'
        elif STORAGE_BACKEND == 'file':
            import tempfile
            file_dir = os.path.join(tempfile.gettempdir(), 'meta_analysis_states')
            os.makedirs(file_dir, exist_ok=True)
            _storage_backend = file_dir
            logger.info(f"File storage backend initialized: {file_dir}")
        elif STORAGE_BACKEND == 'dynamodb':
            try:
                import boto3
                _storage_backend = boto3.resource('dynamodb')
                logger.info("DynamoDB storage backend initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DynamoDB: {e}, falling back to memory")
                _storage_backend = 'memory'
        else:
            _storage_backend = 'memory'
            logger.info("Memory storage backend initialized")
    
    return _storage_backend

def get_or_create_state(thread_ts: str, channel_id: str) -> ConversationState:
    """会話状態を取得または作成"""
    key = f"{channel_id}:{thread_ts}"
    
    # 期限切れの状態をクリーンアップ
    cleanup_expired_states()
    
    # 既存の状態を取得
    state = get_state(thread_ts, channel_id)
    if state is None:
        state = ConversationState(thread_ts, channel_id)
        save_state(state)
        logger.info(f"Created new conversation state for {key}")
    
    return state

def get_state(thread_ts: str, channel_id: str) -> Optional[ConversationState]:
    """会話状態を取得"""
    key = f"{channel_id}:{thread_ts}"
    backend = _get_storage_backend()
    
    try:
        if backend == 'memory':
            state_data = _memory_store.get(key)
        elif isinstance(backend, str) and backend.startswith('/'):  # file backend
            file_path = os.path.join(backend, f"{key}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
            else:
                state_data = None
        elif hasattr(backend, 'get'):  # Redis
            state_json = backend.get(f"conversation_state:{key}")
            state_data = json.loads(state_json) if state_json else None
        elif hasattr(backend, 'Table'):  # DynamoDB
            table = backend.Table(os.environ.get('DYNAMODB_TABLE', 'meta_analysis_states'))
            response = table.get_item(Key={'state_key': key})
            state_data = response.get('Item', {}).get('state_data')
        else:
            state_data = None
            
        if state_data:
            state = ConversationState.from_dict(state_data)
            if not state.is_expired():
                return state
            else:
                # 期限切れの場合は削除
                delete_state(thread_ts, channel_id)
                
    except Exception as e:
        logger.error(f"Error getting state {key}: {e}")
        
    return None

def save_state(state: ConversationState):
    """会話状態を保存"""
    backend = _get_storage_backend()
    state_data = state.to_dict()
    
    try:
        if backend == 'memory':
            _memory_store[state.key] = state_data
        elif isinstance(backend, str) and backend.startswith('/'):  # file backend
            file_path = os.path.join(backend, f"{state.key}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
        elif hasattr(backend, 'set'):  # Redis
            expiry_seconds = STATE_EXPIRY_HOURS * 3600
            backend.setex(f"conversation_state:{state.key}", expiry_seconds, json.dumps(state_data, ensure_ascii=False))
        elif hasattr(backend, 'Table'):  # DynamoDB
            table = backend.Table(os.environ.get('DYNAMODB_TABLE', 'meta_analysis_states'))
            import time
            ttl = int(time.time()) + (STATE_EXPIRY_HOURS * 3600)
            table.put_item(Item={
                'state_key': state.key,
                'state_data': state_data,
                'ttl': ttl
            })
            
        logger.info(f"Saved conversation state for {state.key} using {STORAGE_BACKEND} backend")
        
    except Exception as e:
        logger.error(f"Error saving state {state.key}: {e}")
        # フォールバックとしてメモリに保存
        _memory_store[state.key] = state_data

def delete_state(thread_ts: str, channel_id: str):
    """会話状態を削除"""
    key = f"{channel_id}:{thread_ts}"
    backend = _get_storage_backend()
    
    try:
        if backend == 'memory':
            _memory_store.pop(key, None)
        elif isinstance(backend, str) and backend.startswith('/'):  # file backend
            file_path = os.path.join(backend, f"{key}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
        elif hasattr(backend, 'delete'):  # Redis
            backend.delete(f"conversation_state:{key}")
        elif hasattr(backend, 'Table'):  # DynamoDB
            table = backend.Table(os.environ.get('DYNAMODB_TABLE', 'meta_analysis_states'))
            table.delete_item(Key={'state_key': key})
            
        logger.info(f"Deleted conversation state for {key}")
        
    except Exception as e:
        logger.error(f"Error deleting state {key}: {e}")

def cleanup_expired_states():
    """期限切れの状態をクリーンアップ"""
    backend = _get_storage_backend()
    expired_count = 0
    
    try:
        if backend == 'memory':
            expired_keys = []
            for key, state_data in list(_memory_store.items()):
                try:
                    state = ConversationState.from_dict(state_data)
                    if state.is_expired():
                        expired_keys.append(key)
                except Exception:
                    expired_keys.append(key)  # 破損したデータも削除
            
            for key in expired_keys:
                _memory_store.pop(key, None)
            expired_count = len(expired_keys)
            
        elif isinstance(backend, str) and backend.startswith('/'):  # file backend
            if os.path.exists(backend):
                for filename in os.listdir(backend):
                    if filename.endswith('.json'):
                        file_path = os.path.join(backend, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            state = ConversationState.from_dict(state_data)
                            if state.is_expired():
                                os.remove(file_path)
                                expired_count += 1
                        except Exception:
                            os.remove(file_path)  # 破損したファイルも削除
                            expired_count += 1
                            
        # Redis/DynamoDBは自動的にTTLで削除されるため、明示的なクリーンアップは不要
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired conversation states")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        
    return expired_count