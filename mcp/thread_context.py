"""
スレッドコンテキスト管理モジュール

Slackスレッド内での会話コンテキストを管理し、スレッド間の独立性を保証します。
"""

import json
import time
from datetime import datetime, timedelta
import os
import uuid
import logging
from typing import Dict, List, Optional, Any, Union
import tempfile
from pathlib import Path
import shutil

# Firestore imports
from google.cloud import firestore
from .firestore_client import get_db

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

def convert_firestore_timestamps(obj):
    """
    Firestoreのタイムスタンプオブジェクトを JSON serializable な形式に変換する
    """
    if isinstance(obj, dict):
        return {key: convert_firestore_timestamps(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_firestore_timestamps(item) for item in obj]
    elif hasattr(obj, 'timestamp') and hasattr(obj, '__class__') and 'DatetimeWithNanoseconds' in str(obj.__class__):
        # Firestore DatetimeWithNanoseconds オブジェクトの場合
        return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
    elif isinstance(obj, datetime):
        # 通常のdatetimeオブジェクトの場合
        return obj.isoformat()
    else:
        return obj

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MemoryStorage:
    """メモリ内ストレージ（開発・テスト用）"""
    
    def __init__(self):
        self.data = {}
        self.expiry = {}
    
    def get(self, key: str) -> Optional[Dict]:
        """キーに対応する値を取得"""
        if key in self.data and (key not in self.expiry or self.expiry[key] > time.time()):
            return self.data[key]
        return None
    
    def set(self, key: str, value: Dict, expire: int = 0) -> None:
        """キーと値を保存、オプションで有効期限を設定"""
        self.data[key] = value
        if expire > 0:
            self.expiry[key] = time.time() + expire
    
    def delete(self, key: str) -> None:
        """キーと対応する値を削除"""
        if key in self.data:
            del self.data[key]
        if key in self.expiry:
            del self.expiry[key]
    
    def cleanup(self) -> None:
        """期限切れのエントリを削除"""
        now = time.time()
        expired_keys = [k for k, v in self.expiry.items() if v <= now]
        for key in expired_keys:
            self.delete(key)


class RedisStorage:
    """Redisストレージバックエンド"""
    
    def __init__(self):
        try:
            import redis
            self.redis = redis.Redis(
                host=clean_env_var('REDIS_HOST', 'localhost'),
                port=int(clean_env_var('REDIS_PORT', '6379')),
                db=int(clean_env_var('REDIS_DB', '0')),
                password=clean_env_var('REDIS_PASSWORD', None),
                decode_responses=True
            )
            self.available = True
        except (ImportError, Exception) as e:
            logger.warning(f"Redis接続エラー: {e}. フォールバックとしてメモリストレージを使用します。")
            self.available = False
            self.memory_storage = MemoryStorage()
    
    def get(self, key: str) -> Optional[Dict]:
        """Redisからキーに対応する値を取得"""
        if not self.available:
            return self.memory_storage.get(key)
        
        data = self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                logger.error(f"JSONデコードエラー: {key}")
                return None
        return None
    
    def set(self, key: str, value: Dict, expire: int = 0) -> None:
        """Redisにキーと値を保存、オプションで有効期限を設定"""
        if not self.available:
            return self.memory_storage.set(key, value, expire)
        
        try:
            json_data = json.dumps(value)
            if expire > 0:
                self.redis.setex(key, expire, json_data)
            else:
                self.redis.set(key, json_data)
        except Exception as e:
            logger.error(f"Redis保存エラー: {e}")
    
    def delete(self, key: str) -> None:
        """Redisからキーと対応する値を削除"""
        if not self.available:
            return self.memory_storage.delete(key)
        
        self.redis.delete(key)


class DynamoDBStorage:
    """DynamoDBストレージバックエンド"""
    
    def __init__(self):
        try:
            import boto3
            self.dynamodb = boto3.resource('dynamodb')
            self.table = self.dynamodb.Table(clean_env_var('DYNAMODB_TABLE', 'slack_thread_contexts'))
            self.available = True
        except (ImportError, Exception) as e:
            logger.warning(f"DynamoDB接続エラー: {e}. フォールバックとしてメモリストレージを使用します。")
            self.available = False
            self.memory_storage = MemoryStorage()
    
    def get(self, key: str) -> Optional[Dict]:
        """DynamoDBからキーに対応する値を取得"""
        if not self.available:
            return self.memory_storage.get(key)
        
        try:
            response = self.table.get_item(Key={'thread_key': key})
            item = response.get('Item')
            if item and 'data' in item:
                if 'expires_at' in item and item['expires_at'] < int(time.time()):
                    self.delete(key)
                    return None
                return json.loads(item['data'])
            return None
        except Exception as e:
            logger.error(f"DynamoDB取得エラー: {e}")
            return None
    
    def set(self, key: str, value: Dict, expire: int = 0) -> None:
        """DynamoDBにキーと値を保存、オプションで有効期限を設定"""
        if not self.available:
            return self.memory_storage.set(key, value, expire)
        
        try:
            item = {
                'thread_key': key,
                'data': json.dumps(value),
                'updated_at': int(time.time())
            }
            
            if expire > 0:
                item['expires_at'] = int(time.time()) + expire
            
            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"DynamoDB保存エラー: {e}")
    
    def delete(self, key: str) -> None:
        """DynamoDBからキーと対応する値を削除"""
        if not self.available:
            return self.memory_storage.delete(key)
        
        try:
            self.table.delete_item(Key={'thread_key': key})
        except Exception as e:
            logger.error(f"DynamoDB削除エラー: {e}")


class FirestoreStorage:
    """Firestoreストレージバックエンド"""

    COLL = "threads"  # Firestore collection name

    def __init__(self):
        try:
            self.db = get_db()
            self.available = True
            logger.info("FirestoreStorage initialized successfully.")
        except Exception as e:
            logger.warning(f"Firestore client initialization error: {e}. Firestore storage will be unavailable.")
            self.available = False

    def get(self, key: str) -> Optional[Dict]:
        """Firestoreからキーに対応する値を取得"""
        if not self.available:
            logger.error("Firestore client not available for get operation.")
            return None

        try:
            actual_thread_id = key.split(':')[-1]
            snap = self.db.collection(self.COLL).document(actual_thread_id).get()
            
            if not snap.exists:
                logger.debug(f"Document {actual_thread_id} not found in Firestore for key {key}.")
                return None

            data = snap.to_dict()
            if not data: # Should not happen if snap.exists is true, but as a safeguard
                return None

            # Check for 'expires_at' field for TTL
            if 'expires_at' in data:
                expires_at_val = data['expires_at']
                # Firestore returns datetime objects for Timestamp fields
                if isinstance(expires_at_val, datetime):
                    if expires_at_val.timestamp() < time.time():
                        logger.info(f"Firestore document {actual_thread_id} for key {key} has expired based on 'expires_at' field. Deleting.")
                        self.delete(key)  # Use the original composite key for deletion consistency
                        return None  # Expired
                # If expires_at_val is firestore.SERVER_TIMESTAMP, it's not resolved yet, so not expired.
            
            # タイムスタンプを JSON serializable な形式に変換
            data = convert_firestore_timestamps(data)
            return data
        except Exception as e:
            logger.error(f"Firestore get error for key {key} (doc_id: {actual_thread_id}): {e}")
            return None

    def set(self, key: str, value: Dict, expire: int = 0) -> None:
        """Firestoreにキーと値を保存、オプションで有効期限を設定"""
        if not self.available:
            logger.error("Firestore client not available for set operation.")
            return

        try:
            actual_thread_id = key.split(':')[-1]
            
            # タイムスタンプを JSON serializable な形式に変換してからコピー
            value = convert_firestore_timestamps(value)
            data_to_set = value.copy()
            
            # Add/overwrite 'updated_at' with Firestore server timestamp
            data_to_set["updated_at"] = firestore.SERVER_TIMESTAMP
            
            # Handle 'expire' for TTL by setting an 'expires_at' field (datetime)
            if expire > 0:
                expiration_datetime = datetime.fromtimestamp(time.time() + expire)
                data_to_set['expires_at'] = expiration_datetime
            elif 'expires_at' in data_to_set:  # If expire is 0 or not positive, remove 'expires_at' if it exists
                del data_to_set['expires_at']

            self.db.collection(self.COLL).document(actual_thread_id).set(data_to_set, merge=True)
            logger.info(f"Context saved to Firestore for key {key} (doc_id: {actual_thread_id})")
        except Exception as e:
            logger.error(f"Firestore set error for key {key} (doc_id: {actual_thread_id}): {e}")

    def delete(self, key: str) -> None:
        """Firestoreからキーと対応する値を削除"""
        if not self.available:
            logger.error("Firestore client not available for delete operation.")
            return
        
        try:
            actual_thread_id = key.split(':')[-1]
            self.db.collection(self.COLL).document(actual_thread_id).delete()
            logger.info(f"Context deleted from Firestore for key {key} (doc_id: {actual_thread_id})")
        except Exception as e:
            logger.error(f"Firestore delete error for key {key} (doc_id: {actual_thread_id}): {e}")

    def append_message(self, conversation_id: str, role: str, content: str, message_ts: Optional[str] = None) -> str:
        """Firestoreの会話にメッセージを追加（サブコレクション形式）"""
        if not self.available:
            logger.error("Firestore client not available for append_message operation.")
            return None
        
        try:
            # メッセージIDを生成（Slackのtsがあればそれを使用、なければUUID）
            msg_id = message_ts.replace('.', '_') if message_ts else str(uuid.uuid4())
            
            conv_ref = self.db.collection("conversations").document(conversation_id)
            msg_ref = conv_ref.collection("messages").document(msg_id)
            
            message_data = {
                "role": role,
                "content": content,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "slackTs": message_ts if message_ts else None
            }
            
            msg_ref.set(message_data)
            
            # 会話のメタデータも更新
            conv_ref.set({
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "lastActivity": firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            logger.info(f"Message appended to conversation {conversation_id} with msg_id {msg_id}")
            return msg_id
            
        except Exception as e:
            logger.error(f"Firestore append_message error for conversation {conversation_id}: {e}")
            return None

    def get_recent_messages(self, conversation_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """最新のメッセージを取得（サブコレクション形式）"""
        if not self.available:
            logger.error("Firestore client not available for get_recent_messages operation.")
            return []
        
        try:
            conv_ref = self.db.collection("conversations").document(conversation_id)
            messages_ref = conv_ref.collection("messages")
            
            # createdAt 降順で取得して、後で昇順にする（最新から古い順で取得し、制限をかけてから逆順にする）
            message_docs = (
                messages_ref
                .order_by("createdAt", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            
            messages = []
            for doc in message_docs:
                data = doc.to_dict()
                if data:
                    # タイムスタンプを JSON serializable な形式に変換
                    data = convert_firestore_timestamps(data)
                    messages.append({
                        "role": data.get("role"),
                        "content": data.get("content"),
                        "timestamp": data.get("createdAt"),
                        "slackTs": data.get("slackTs")
                    })
            
            # 時系列順（古い→新しい）に並び替え
            messages.reverse()
            
            logger.info(f"Retrieved {len(messages)} recent messages for conversation {conversation_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Firestore get_recent_messages error for conversation {conversation_id}: {e}")
            return []

    def cleanup_old_messages(self, conversation_id: str, keep_count: int = 100) -> None:
        """古いメッセージを削除（オプション機能）"""
        if not self.available:
            return
        
        try:
            conv_ref = self.db.collection("conversations").document(conversation_id)
            messages_ref = conv_ref.collection("messages")
            
            # 古いメッセージを取得（keep_count より古いもの）
            docs_to_delete = (
                messages_ref
                .order_by("createdAt", direction=firestore.Query.DESCENDING)
                .offset(keep_count)
                .stream()
            )
            
            batch = self.db.batch()
            delete_count = 0
            
            for doc in docs_to_delete:
                batch.delete(doc.reference)
                delete_count += 1
                
                # バッチサイズの制限（Firestoreは500件まで）
                if delete_count >= 450:
                    batch.commit()
                    batch = self.db.batch()
                    delete_count = 0
            
            if delete_count > 0:
                batch.commit()
                
            logger.info(f"Cleaned up old messages for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"Firestore cleanup_old_messages error for conversation {conversation_id}: {e}")


class ThreadContextManager:
    """スレッドごとの会話コンテキストを管理するクラス"""
    
    def __init__(self, storage_backend: str = "memory", expiration_days: int = 7):
        """
        初期化
        
        Args:
            storage_backend: コンテキスト保存先 ("redis", "dynamodb", "memory")
            expiration_days: コンテキスト有効期限（日数）
        """
        self.storage = self._init_storage(storage_backend)
        self.expiration_days = expiration_days
        self.expiration_seconds = expiration_days * 86400
        self.max_history_length = 20  # デフォルトの履歴保持件数
        self.enable_firestore_subcollection = isinstance(self.storage, FirestoreStorage)  # Firestoreサブコレクション機能の有効化

    def get_thread_storage_path(self, thread_id: str, channel_id: Optional[str] = None) -> Optional[str]:
        """
        Gets the storage path for a given thread.
        For file-based storage, it returns the specific thread's directory.
        For Firestore (or other non-file-based storage), it creates and returns a temporary directory.
        """
        key = self._make_key(thread_id, channel_id)
        if isinstance(self.storage, FileBasedStorage):
            thread_dir_path_obj = self.storage._get_thread_dir(key) # Gets Path object
            try:
                thread_dir_path_obj.mkdir(parents=True, exist_ok=True)
                logger.info(f"Ensured FileBasedStorage directory exists: {thread_dir_path_obj}")
                return str(thread_dir_path_obj)
            except Exception as e:
                logger.error(f"Failed to create or access FileBasedStorage directory {thread_dir_path_obj}: {e}")
                return None
        elif isinstance(self.storage, FirestoreStorage): # Check if storage is Firestore
            try:
                # Cloud Runなどの環境で利用可能な一時ディレクトリを作成
                tmp_dir = tempfile.mkdtemp(prefix=f"thread_{channel_id or 'nochannel'}_{thread_id}_")
                logger.info(f"Created temporary directory for Firestore backend: {tmp_dir} for key {key}")
                return tmp_dir
            except Exception as e:
                logger.error(f"Failed to create temporary directory for Firestore backend (key {key}): {e}")
                return None
        else:
            # For other storage backends like MemoryStorage, RedisStorage, DynamoDBStorage,
            # a file system path might not be applicable or might need a different approach.
            # For now, returning None if not FileBasedStorage or Firestore.
            logger.warning(f"get_thread_storage_path not implemented for storage backend type: {type(self.storage)}. Key: {key}")
            return None

    def get_context(self, thread_id: str, channel_id: Optional[str] = None) -> Optional[Dict]:
        """
        スレッドコンテキストを取得
        
        Args:
            thread_id: スレッドID
            channel_id: チャンネルID（オプション）
            
        Returns:
            dict: スレッドコンテキスト、存在しない場合はNone
        """
        key = self._make_key(thread_id, channel_id)
        context = self.storage.get(key)
        if context:
            # タイムスタンプを JSON serializable な形式に変換
            context = convert_firestore_timestamps(context)
            
            # Firestoreサブコレクション機能が有効な場合は、履歴を別途取得
            if self.enable_firestore_subcollection:
                context["history"] = self.storage.get_recent_messages(key, self.max_history_length)
                
        return context
    
    def save_context(self, thread_id: str, context: Dict, channel_id: Optional[str] = None) -> None:
        """
        スレッドコンテキストを保存
        
        Args:
            thread_id: スレッドID
            context: 保存するコンテキスト
            channel_id: チャンネルID（オプション）
        """
        key = self._make_key(thread_id, channel_id)
        # タイムスタンプを JSON serializable な形式に変換
        context = convert_firestore_timestamps(context)
        context["last_updated"] = datetime.now().isoformat()
        
        # Firestoreサブコレクション機能が有効な場合は、historyフィールドを除外して保存
        if self.enable_firestore_subcollection:
            context_to_save = {k: v for k, v in context.items() if k != "history"}
            # history は個別にサブコレクションで管理されるため、メインドキュメントからは除外
            self.storage.set(key, context_to_save, expire=self.expiration_seconds)
        else:
            # 従来の方式（メモリ、Redis、DynamoDB、ファイル）
            self.storage.set(key, context, expire=self.expiration_seconds)
    
    def update_history(self, thread_id: str, 
                       user_message_content: Optional[str], 
                       bot_response_content: Optional[str], 
                       channel_id: Optional[str] = None, 
                       user_message_ts: Optional[str] = None,
                       bot_response_ts: Optional[str] = None,
                       max_history: int = None) -> None:
        """
        会話履歴を更新。ユーザーメッセージとBotの応答を別々のエントリとして保存。
        
        Args:
            thread_id: スレッドID
            user_message_content: ユーザーメッセージの内容 (Noneの場合あり)
            bot_response_content: ボットの応答内容 (Noneの場合あり)
            channel_id: チャンネルID（オプション）
            user_message_ts: ユーザーメッセージのSlackタイムスタンプ (Noneの場合あり)
            bot_response_ts: Bot応答のSlackタイムスタンプ (Noneの場合あり)
            max_history: 保持する履歴エントリの最大数 (各メッセージが1エントリ)
        """
        # max_historyのデフォルト値設定
        if max_history is None:
            max_history = self.max_history_length
        
        # Firestoreサブコレクション機能が有効な場合は、個別メッセージとして保存
        if self.enable_firestore_subcollection:
            self._update_history_firestore_subcollection(
                thread_id, user_message_content, bot_response_content, 
                channel_id, user_message_ts, bot_response_ts
            )
            return
        
        # 従来の方式（メモリ、Redis、DynamoDB、ファイル）
        self._update_history_traditional(
            thread_id, user_message_content, bot_response_content,
            channel_id, user_message_ts, bot_response_ts, max_history
        )
    
    def _update_history_firestore_subcollection(self, thread_id: str,
                                               user_message_content: Optional[str],
                                               bot_response_content: Optional[str],
                                               channel_id: Optional[str] = None,
                                               user_message_ts: Optional[str] = None,
                                               bot_response_ts: Optional[str] = None) -> None:
        """Firestoreサブコレクション形式での履歴更新"""
        key = self._make_key(thread_id, channel_id)
        
        # ユーザーメッセージを追加 (存在する場合)
        if user_message_content:
            msg_id = self.storage.append_message(key, "user", user_message_content, user_message_ts)
            if msg_id:
                logger.debug(f"Added user message to Firestore subcollection for thread {thread_id}: '{user_message_content}' (msg_id: {msg_id})")

        # Botの応答を追加 (存在する場合)
        if bot_response_content:
            msg_id = self.storage.append_message(key, "model", bot_response_content, bot_response_ts)
            if msg_id:
                logger.debug(f"Added bot response to Firestore subcollection for thread {thread_id}: '{bot_response_content}' (msg_id: {msg_id})")
        
        logger.info(f"History updated in Firestore subcollection for thread {thread_id}")
    
    def _update_history_traditional(self, thread_id: str,
                                   user_message_content: Optional[str],
                                   bot_response_content: Optional[str],
                                   channel_id: Optional[str] = None,
                                   user_message_ts: Optional[str] = None,
                                   bot_response_ts: Optional[str] = None,
                                   max_history: int = 20) -> None:
        """従来方式での履歴更新（メモリ、Redis、DynamoDB、ファイル用）"""
        context = self.get_context(thread_id, channel_id) or self._create_empty_context(thread_id, channel_id)
        
        if "history" not in context or not isinstance(context["history"], list):
            context["history"] = []
        
        # ユーザーメッセージを履歴に追加 (存在する場合)
        if user_message_content:
            context["history"].append({
                "role": "user",
                "content": user_message_content,
                "timestamp": user_message_ts or datetime.now().isoformat() # Slackのtsを優先
            })
            logger.debug(f"Added user message to history for thread {thread_id}: '{user_message_content}' (ts: {user_message_ts})")

        # Botの応答を履歴に追加 (存在する場合)
        if bot_response_content:
            context["history"].append({
                "role": "model", # Geminiが期待する 'model' ロール
                "content": bot_response_content,
                "timestamp": bot_response_ts or datetime.now().isoformat() # Slackのtsを優先
            })
            logger.debug(f"Added bot response to history for thread {thread_id}: '{bot_response_content}' (ts: {bot_response_ts})")
        
        # 履歴の最大件数を維持
        if len(context["history"]) > max_history:
            context["history"] = context["history"][-max_history:]
            logger.debug(f"History for thread {thread_id} trimmed to {max_history} entries.")
        
        self.save_context(thread_id, context, channel_id)
        logger.info(f"History updated for thread {thread_id}. Current length: {len(context['history'])}")

    def cleanup_old_history(self, thread_id: str, channel_id: Optional[str] = None, keep_count: int = 100) -> None:
        """古い履歴をクリーンアップ（Firestoreサブコレクション使用時のみ）"""
        if not self.enable_firestore_subcollection:
            logger.warning("cleanup_old_history is only available with Firestore subcollection feature.")
            return
        
        key = self._make_key(thread_id, channel_id)
        self.storage.cleanup_old_messages(key, keep_count)
        logger.info(f"Cleaned up old history for thread {thread_id}, keeping latest {keep_count} messages")

    def get_conversation_summary(self, thread_id: str, channel_id: Optional[str] = None) -> Optional[str]:
        """会話の要約を取得（将来的にLLMで自動要約する機能の準備）"""
        context = self.get_context(thread_id, channel_id)
        if context:
            return context.get("summary")
        return None

    def update_data_state(self, thread_id: str, data_state: Dict, 
                         channel_id: Optional[str] = None) -> None:
        """
        データ状態を更新
        
        Args:
            thread_id: スレッドID
            data_state: データ状態情報
            channel_id: チャンネルID（オプション）
        """
        context = self.get_context(thread_id, channel_id) or self._create_empty_context(thread_id, channel_id)
        context["data_state"] = data_state
        self.save_context(thread_id, context, channel_id)
    
    def update_analysis_state(self, thread_id: str, analysis_state: Dict, 
                             channel_id: Optional[str] = None) -> None:
        """
        分析状態を更新
        
        Args:
            thread_id: スレッドID
            analysis_state: 分析状態情報
            channel_id: チャンネルID（オプション）
        """
        context = self.get_context(thread_id, channel_id) or self._create_empty_context(thread_id, channel_id)
        context["analysis_state"] = analysis_state
        self.save_context(thread_id, context, channel_id)
    
    def clear_context(self, thread_id: str, channel_id: Optional[str] = None) -> None:
        """
        スレッドコンテキストをクリア
        
        Args:
            thread_id: スレッドID
            channel_id: チャンネルID（オプション）
        """
        key = self._make_key(thread_id, channel_id)
        self.storage.delete(key)
    
    def find_active_threads_in_channel(self, channel_id: str, dialog_type: Optional[str] = None) -> List[str]:
        """
        指定されたチャンネル内のアクティブなスレッドを検索
        
        Args:
            channel_id: チャンネルID
            dialog_type: 特定のダイアログタイプでフィルタ（オプション）
            
        Returns:
            List[str]: アクティブなスレッドのthread_idのリスト
        """
        active_threads = []
        
        # メモリストレージの場合、直接アクセス
        if isinstance(self.storage, MemoryStorage):
            channel_prefix = f"thread:{channel_id}:"
            for key, context in self.storage.data.items():
                if key.startswith(channel_prefix):
                    # キーの有効期限をチェック
                    if key in self.storage.expiry and self.storage.expiry[key] <= time.time():
                        continue
                    
                    thread_id = key.replace(channel_prefix, "")
                    
                    # dialog_typeでフィルタ
                    if dialog_type:
                        dialog_state = context.get("dialog_state", {})
                        if dialog_state.get("type") != dialog_type:
                            continue
                    
                    active_threads.append(thread_id)
        
        # Redisやその他のストレージの場合は、パターンマッチングを使用
        # ここでは簡単な実装として、メモリストレージ以外では空のリストを返す
        # 実際の本番環境では、各ストレージバックエンドに対応したパターン検索を実装する必要がある
        
        return active_threads
    
    def set_max_history_length(self, length: int) -> None:
        """履歴の最大保持件数を設定"""
        self.max_history_length = max(1, length)  # 最低1件は保持
        logger.info(f"Max history length set to {self.max_history_length}")

    def get_max_history_length(self) -> int:
        """現在の履歴最大保持件数を取得"""
        return self.max_history_length
    
    def _create_empty_context(self, thread_id: str, channel_id: Optional[str] = None) -> Dict:
        """
        空のコンテキストを作成
        
        Args:
            thread_id: スレッドID
            channel_id: チャンネルID（オプション）
            
        Returns:
            dict: 初期化されたコンテキスト
        """
        return {
            "thread_id": thread_id,
            "channel_id": channel_id,
            "history": [],
            "data_state": None,
            "analysis_state": None,
            "last_updated": datetime.now().isoformat()
        }
    
    def _make_key(self, thread_id: str, channel_id: Optional[str] = None) -> str:
        """
        ストレージキーを生成
        
        Args:
            thread_id: スレッドID
            channel_id: チャンネルID（オプション）
            
        Returns:
            str: ストレージキー
        """
        if channel_id:
            return f"thread:{channel_id}:{thread_id}"
        return f"thread:{thread_id}"
    
    def _init_storage(self, backend: str):
        """
        ストレージバックエンドを初期化
        
        Args:
            backend: バックエンド種別
            
        Returns:
            object: ストレージインターフェース
        """
        if backend == "file":
            return FileBasedStorage()
        elif backend == "redis":
            return RedisStorage()
        elif backend == "dynamodb":
            return DynamoDBStorage()
        elif backend == "firestore":
            return FirestoreStorage()
        else:  # Default to memory storage
            return MemoryStorage()

class FileBasedStorage:
    """ファイルベースのストレージ実装"""
    
    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or tempfile.gettempdir()
        logger.info(f"FileBasedStorage initialized with base_dir: {self.base_dir}")
        
    def _get_thread_dir(self, key: str) -> Path:
        """スレッド用のディレクトリパスを取得"""
        # key: "thread:C066EQ49QVD:1748077497.657129" or "thread:thread_id_only"
        parts = key.split(":")
        if len(parts) >= 3: # channel_id and thread_ts present
            channel_id = parts[1]
            thread_ts = parts[2]
            # Sanitize thread_ts if it contains characters not suitable for directory names
            sanitized_thread_ts = thread_ts.replace('.', '_') # Example: replace dot with underscore
            dir_name = f"thread_{channel_id}_{sanitized_thread_ts}"
        elif len(parts) == 2: # Only thread_id (e.g., "thread:some_id")
            sanitized_thread_id = parts[1].replace('.', '_')
            dir_name = f"thread_{sanitized_thread_id}"
        else: # Fallback for unexpected key format
            sanitized_key = key.replace(':', '_').replace('.', '_')
            dir_name = f"thread_{sanitized_key}"
            
        return Path(self.base_dir) / dir_name
    
    def _get_context_file(self, key: str) -> Path:
        """コンテキストファイルのパスを取得"""
        return self._get_thread_dir(key) / "context.json"
    
    def get(self, key: str) -> Optional[Dict]:
        """コンテキストを読み込み"""
        context_file = self._get_context_file(key)
        if context_file.exists():
            try:
                # Check for expiration if _expires_at is present
                with open(context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if '_expires_at' in data and data['_expires_at'] < time.time():
                    logger.info(f"Context file {context_file} has expired. Deleting.")
                    self.delete(key) # Delete the entire thread directory
                    return None
                return data
            except json.JSONDecodeError:
                logger.error(f"JSON decode error for {context_file}. File content might be corrupted.")
                return None # Or handle by deleting/renaming the corrupted file
            except Exception as e:
                logger.error(f"Failed to load context from {context_file}: {e}")
                return None
        return None
    
    def set(self, key: str, value: Dict, expire: int = 0) -> None:
        """コンテキストを保存"""
        thread_dir = self._get_thread_dir(key)
        try:
            thread_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {thread_dir}: {e}")
            return # Cannot save if directory creation fails

        context_file = self._get_context_file(key)
        
        # 有効期限情報を追加
        if expire > 0:
            value['_expires_at'] = time.time() + expire
        elif '_expires_at' in value and value['_expires_at'] == 0: # Explicitly no expiration
            pass # Keep _expires_at if it's already set to 0 or not present
        elif '_expires_at' not in value: # Default to no expiration if not specified
             pass


        try:
            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
            logger.info(f"Context saved to {context_file}")
        except Exception as e:
            logger.error(f"Failed to save context to {context_file}: {e}")
    
    def delete(self, key: str) -> None:
        """コンテキストとディレクトリを削除"""
        thread_dir = self._get_thread_dir(key)
        if thread_dir.exists():
            try:
                shutil.rmtree(thread_dir)
                logger.info(f"Deleted thread directory: {thread_dir}")
            except Exception as e:
                logger.error(f"Failed to delete directory {thread_dir}: {e}")
    
    def get_thread_directory_path(self, key: str) -> Optional[str]:
        """スレッド固有のディレクトリパスを取得する"""
        thread_dir = self._get_thread_dir(key)
        if thread_dir.exists():
            return str(thread_dir)
        # ディレクトリが存在しない場合でも、作成してパスを返すことも検討できる
        # thread_dir.mkdir(parents=True, exist_ok=True)
        # return str(thread_dir)
        return None # または、必要に応じてディレクトリを作成する

if __name__ == "__main__":
    context_manager = ThreadContextManager(storage_backend="memory")
    
    thread_id = "test_thread_123"
    channel_id = "test_channel_456"
    
    data_state = {
        "file_id": "F12345",
        "file_name": "meta_data.csv",
        "columns": ["study", "yi", "vi", "n", "subgroup", "year"],
        "summary": {"rows": 10, "cols": 6},
        "processed": True
    }
    context_manager.update_data_state(thread_id, data_state, channel_id)
    
    analysis_state = {
        "type": "subgroup",
        "settings": {
            "subgroup_var": "subgroup",
            "model": "random",
            "measure": "SMD"
        },
        "stage": "config"
    }
    context_manager.update_analysis_state(thread_id, analysis_state, channel_id)
    
    context_manager
