"""
状態管理テスト
CLAUDE.md仕様: 会話永続化と状態管理をテストする
"""
import pytest
import time
import os
from unittest.mock import Mock, patch, MagicMock
from utils.conversation_state import (
    ConversationState, DialogState, get_or_create_state, 
    save_state, get_state, cleanup_expired_states
)


class TestStateManagement:
    """状態管理機能のテストクラス"""
    
    def test_conversation_state_creation(self):
        """会話状態の作成ができること"""
        # Given: スレッド情報
        thread_ts = "1234567890.123456"
        channel_id = "C123456"
        
        # When: 状態作成
        state = ConversationState(thread_ts, channel_id)
        
        # Then: 適切に初期化される
        assert state.thread_ts == thread_ts
        assert state.channel_id == channel_id
        assert state.state == DialogState.WAITING_FOR_FILE
        assert state.collected_params == {}
        assert state.conversation_history == []
        assert state.created_at > 0
    
    def test_dialog_state_transitions(self):
        """ダイアログ状態の遷移が正常に動作すること"""
        # Given: 会話状態
        state = ConversationState("thread", "channel")
        
        # When: 状態遷移シーケンス
        state.update_state(DialogState.PROCESSING_FILE)
        assert state.state == DialogState.PROCESSING_FILE
        
        state.update_state(DialogState.ANALYSIS_PREFERENCE)
        assert state.state == DialogState.ANALYSIS_PREFERENCE
        
        state.update_state(DialogState.ANALYSIS_RUNNING)
        assert state.state == DialogState.ANALYSIS_RUNNING
        
        state.update_state(DialogState.POST_ANALYSIS)
        assert state.state == DialogState.POST_ANALYSIS
        
        # Then: 各状態遷移が正常
        assert state.state == DialogState.POST_ANALYSIS
    
    def test_parameter_collection_and_updates(self):
        """パラメータ収集と更新ができること"""
        # Given: 会話状態
        state = ConversationState("thread", "channel")
        
        # When: パラメータ更新
        params = {
            "effect_size": "OR",
            "model_type": "random",
            "method": "REML"
        }
        state.update_params(params)
        
        # Then: パラメータが保存される
        assert state.collected_params["effect_size"] == "OR"
        assert state.collected_params["model_type"] == "random"
        assert state.collected_params["method"] == "REML"
        
        # When: 部分更新
        state.update_params({"subgroup_column": "Region"})
        
        # Then: 既存パラメータが保持される
        assert state.collected_params["effect_size"] == "OR"
        assert state.collected_params["subgroup_column"] == "Region"
    
    def test_conversation_history_management(self):
        """会話履歴の管理ができること"""
        # Given: 会話状態
        state = ConversationState("thread", "channel")
        
        # When: 会話履歴追加
        for i in range(25):  # 20件制限を超えた数
            state.conversation_history.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
                "timestamp": time.time()
            })
        
        # 制限適用
        state.limit_history(max_messages=20)
        
        # Then: 20件に制限される
        assert len(state.conversation_history) == 20
        assert state.conversation_history[0]["content"] == "Message 5"
        assert state.conversation_history[-1]["content"] == "Message 24"
    
    def test_48_hour_expiration_check(self):
        """会話状態の48時間無効化が機能すること"""
        # Given: 異なる時間の状態
        current_time = time.time()
        
        # 新しい状態
        fresh_state = ConversationState("fresh", "channel")
        fresh_state.created_at = current_time
        
        # 47時間前の状態
        valid_state = ConversationState("valid", "channel")
        valid_state.created_at = current_time - (47 * 3600)
        
        # 49時間前の状態
        expired_state = ConversationState("expired", "channel")
        expired_state.created_at = current_time - (49 * 3600)
        
        # When: 有効性チェック
        # Then: 適切に判定される
        assert fresh_state.is_valid() == True
        assert valid_state.is_valid() == True
        assert expired_state.is_valid() == False
    
    def test_storage_backend_redis_configuration(self):
        """Redisストレージバックエンドの設定ができること"""
        # Given: Redis設定
        with patch.dict(os.environ, {
            "STORAGE_BACKEND": "redis",
            "REDIS_URL": "redis://localhost:6379"
        }):
            # When: ストレージバックエンド取得
            from utils.conversation_state import get_storage_backend
            backend = get_storage_backend()
            
            # Then: Redisバックエンドが返される
            assert backend is not None
            assert hasattr(backend, 'get')
            assert hasattr(backend, 'set')
            assert hasattr(backend, 'delete')
    
    def test_storage_backend_memory_configuration(self):
        """メモリストレージバックエンドの設定ができること"""
        # Given: メモリ設定
        with patch.dict(os.environ, {"STORAGE_BACKEND": "memory"}):
            # When: ストレージバックエンド取得
            from utils.conversation_state import get_storage_backend
            backend = get_storage_backend()
            
            # Then: メモリバックエンドが返される
            assert backend is not None
            assert hasattr(backend, 'get')
            assert hasattr(backend, 'set')
    
    def test_storage_backend_file_configuration(self):
        """ファイルストレージバックエンドの設定ができること"""
        # Given: ファイル設定
        with patch.dict(os.environ, {"STORAGE_BACKEND": "file"}):
            # When: ストレージバックエンド取得
            from utils.conversation_state import get_storage_backend
            backend = get_storage_backend()
            
            # Then: ファイルバックエンドが返される
            assert backend is not None
            assert hasattr(backend, 'get')
            assert hasattr(backend, 'set')
    
    def test_storage_backend_dynamodb_configuration(self):
        """DynamoDBストレージバックエンドの設定ができること"""
        # Given: DynamoDB設定
        with patch.dict(os.environ, {
            "STORAGE_BACKEND": "dynamodb",
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret"
        }):
            # When: ストレージバックエンド取得
            from utils.conversation_state import get_storage_backend
            backend = get_storage_backend()
            
            # Then: DynamoDBバックエンドが返される
            assert backend is not None
            assert hasattr(backend, 'get')
            assert hasattr(backend, 'set')
    
    def test_state_persistence_across_sessions(self):
        """セッションを跨いだ状態永続化ができること"""
        # Given: 状態作成と保存
        thread_ts = "test_persistence"
        channel_id = "C123456"
        
        # 初期状態作成
        state1 = get_or_create_state(thread_ts, channel_id)
        state1.update_state(DialogState.ANALYSIS_PREFERENCE)
        state1.update_params({"effect_size": "SMD"})
        save_state(state1)
        
        # When: 新しいセッションで状態取得
        state2 = get_state(thread_ts, channel_id)
        
        # Then: 状態が保持されている
        assert state2 is not None
        assert state2.state == DialogState.ANALYSIS_PREFERENCE
        assert state2.collected_params["effect_size"] == "SMD"
    
    def test_concurrent_state_access(self):
        """同時アクセス時の状態整合性が保たれること"""
        import threading
        import time
        
        # Given: 共有状態
        thread_ts = "concurrent_test"
        channel_id = "C123456"
        results = []
        
        def update_state_worker(param_value):
            state = get_or_create_state(thread_ts, channel_id)
            state.update_params({"test_param": param_value})
            save_state(state)
            results.append(param_value)
        
        # When: 同時更新
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_state_worker, args=(f"value_{i}",))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Then: すべての更新が正常に処理される
        assert len(results) == 5
        final_state = get_state(thread_ts, channel_id)
        assert "test_param" in final_state.collected_params
    
    def test_expired_state_cleanup(self):
        """期限切れ状態のクリーンアップができること"""
        # Given: 期限切れ状態を含む複数の状態
        current_time = time.time()
        
        # 有効な状態
        valid_state = ConversationState("valid_thread", "channel")
        valid_state.created_at = current_time - (24 * 3600)  # 24時間前
        save_state(valid_state)
        
        # 期限切れ状態
        expired_state = ConversationState("expired_thread", "channel")
        expired_state.created_at = current_time - (50 * 3600)  # 50時間前
        save_state(expired_state)
        
        # When: クリーンアップ実行
        cleanup_count = cleanup_expired_states()
        
        # Then: 期限切れ状態のみ削除される
        assert cleanup_count >= 1
        assert get_state("valid_thread", "channel") is not None
        assert get_state("expired_thread", "channel") is None
    
    def test_csv_analysis_data_persistence(self):
        """CSV解析結果の永続化ができること"""
        # Given: CSV解析結果付き状態
        state = ConversationState("csv_test", "channel")
        csv_analysis = {
            "is_suitable": True,
            "detected_columns": {
                "effect_size_candidates": ["OR", "RR"],
                "subgroup_candidates": ["Region"]
            },
            "suggested_analysis": {
                "effect_type_suggestion": "OR",
                "model_type_suggestion": "REML"
            }
        }
        
        # When: CSV解析結果保存
        state.csv_analysis = csv_analysis
        save_state(state)
        
        # 状態再取得
        retrieved_state = get_state("csv_test", "channel")
        
        # Then: CSV解析結果が保持されている
        assert retrieved_state.csv_analysis["is_suitable"] == True
        assert "OR" in retrieved_state.csv_analysis["detected_columns"]["effect_size_candidates"]
        assert retrieved_state.csv_analysis["suggested_analysis"]["effect_type_suggestion"] == "OR"
    
    def test_file_info_persistence(self):
        """ファイル情報の永続化ができること"""
        # Given: ファイル情報付き状態
        state = ConversationState("file_test", "channel")
        file_info = {
            "file_id": "F123456",
            "file_name": "meta_data.csv",
            "file_url": "https://files.slack.com/test.csv",
            "upload_timestamp": time.time()
        }
        
        # When: ファイル情報保存
        state.file_info = file_info
        save_state(state)
        
        # 状態再取得
        retrieved_state = get_state("file_test", "channel")
        
        # Then: ファイル情報が保持されている
        assert retrieved_state.file_info["file_id"] == "F123456"
        assert retrieved_state.file_info["file_name"] == "meta_data.csv"
        assert "slack.com" in retrieved_state.file_info["file_url"]
    
    def test_async_job_status_tracking(self):
        """非同期ジョブのステータス追跡ができること"""
        # Given: 非同期ジョブ情報
        state = ConversationState("job_test", "channel")
        job_info = {
            "job_id": "analysis_12345",
            "status": "running",
            "started_at": time.time(),
            "progress": 50
        }
        
        # When: ジョブステータス更新
        state.async_job_status = job_info
        save_state(state)
        
        # ステータス更新
        retrieved_state = get_state("job_test", "channel")
        retrieved_state.async_job_status["status"] = "completed"
        retrieved_state.async_job_status["progress"] = 100
        save_state(retrieved_state)
        
        # Then: ジョブステータスが追跡される
        final_state = get_state("job_test", "channel")
        assert final_state.async_job_status["job_id"] == "analysis_12345"
        assert final_state.async_job_status["status"] == "completed"
        assert final_state.async_job_status["progress"] == 100
    
    def test_configuration_based_retention_period(self):
        """設定可能な保持期間が機能すること"""
        # Given: 異なる保持期間設定
        custom_retention_hours = 24  # 24時間
        
        with patch.dict(os.environ, {"CONTEXT_RETENTION_HOURS": str(custom_retention_hours)}):
            # When: カスタム保持期間で状態作成
            state = ConversationState("custom_retention", "channel")
            state.created_at = time.time() - (25 * 3600)  # 25時間前
            
            # Then: カスタム設定に従って無効化される
            assert state.is_valid(retention_hours=custom_retention_hours) == False
            
            # 23時間前の状態は有効
            state.created_at = time.time() - (23 * 3600)
            assert state.is_valid(retention_hours=custom_retention_hours) == True
    
    def test_conversation_history_limit_configuration(self):
        """設定可能な会話履歴件数制限が機能すること"""
        # Given: カスタム履歴件数設定
        custom_history_limit = 10
        
        with patch.dict(os.environ, {"MAX_CONVERSATION_HISTORY": str(custom_history_limit)}):
            # When: カスタム件数で履歴管理
            state = ConversationState("custom_history", "channel")
            
            # 15件の履歴追加
            for i in range(15):
                state.conversation_history.append({
                    "role": "user",
                    "content": f"Message {i}"
                })
            
            # カスタム制限適用
            state.limit_history(max_messages=custom_history_limit)
            
            # Then: カスタム制限に従って制限される
            assert len(state.conversation_history) == custom_history_limit
            assert state.conversation_history[0]["content"] == "Message 5"
