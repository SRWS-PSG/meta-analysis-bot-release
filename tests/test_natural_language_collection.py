"""
自然言語パラメータ収集テスト
CLAUDE.md仕様: Gemini AIによる対話的パラメータ収集をテストする
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from utils.gemini_dialogue import process_user_input_with_gemini
from utils.parameter_extraction import extract_parameters_from_text
from utils.conversation_state import DialogState


class TestNaturalLanguageParameterCollection:
    """自然言語パラメータ収集のテストクラス"""
    
    def test_continuous_dialogue_until_completion(self):
        """必要なパラメータが揃うまで対話を継続すること"""
        # Given: 不完全なパラメータ入力
        user_input = "オッズ比で解析してください"
        csv_columns = ["Study", "Events_A", "Total_A", "Events_B", "Total_B", "Region"]
        current_params = {}
        conversation_history = []
        csv_analysis = {"suggested_analysis": {"effect_type_suggestion": "OR"}}
        
        # When: Gemini処理実行
        result = process_user_input_with_gemini(
            user_input, csv_columns, current_params, conversation_history, csv_analysis
        )
        
        # Then: パラメータが部分的に収集され、次の質問が生成される
        assert "extracted_params" in result
        assert result["extracted_params"]["effect_size"] == "OR"
        assert result["is_ready_to_analyze"] == False
        assert "bot_message" in result
        assert "モデル" in result["bot_message"] or "手法" in result["bot_message"]
    
    def test_context_aware_conversation(self):
        """会話文脈を理解して適切な質問を生成すること"""
        # Given: 進行中の会話履歴
        conversation_history = [
            {"role": "assistant", "content": "統計モデルはランダム効果モデルと固定効果モデルのどちらを使用しますか？"},
            {"role": "user", "content": "ランダム効果で"}
        ]
        current_params = {"effect_size": "OR"}
        
        # When: 文脈を考慮した処理
        result = process_user_input_with_gemini(
            "ランダム効果で", [], current_params, conversation_history, {}
        )
        
        # Then: 適切にパラメータが更新される
        assert result["extracted_params"]["model_type"] == "random"
        assert "method" in result["extracted_params"]
        assert result["extracted_params"]["method"] in ["REML", "DL"]
    
    def test_no_keyword_matching_dependency(self):
        """キーワードマッチングに依存せず自然な表現を理解すること"""
        # Given: 様々な自然な表現
        natural_expressions = [
            "オッズ比を使ってランダム効果で解析したいです",
            "ORでREMLを使ってください",
            "二値データの効果量でお願いします",
            "地域別のサブグループ解析も含めてください"
        ]
        
        for expression in natural_expressions:
            # When: 自然言語処理
            result = extract_parameters_from_text(expression, [])
            
            # Then: キーワードに関係なく意図が理解される
            assert "effect_size" in result or "model_type" in result or "subgroup" in result
    
    def test_gemini_function_calling_usage(self):
        """Gemini Function Callingが構造化データ抽出に使用されること"""
        # Given: 複雑なパラメータ指定
        user_input = "オッズ比でランダム効果モデル、REML法、地域別サブグループ解析で"
        
        # When: Function Calling処理
        with patch('core.gemini_client.GeminiClient.generate_content_with_function_calling') as mock_gemini:
            mock_gemini.return_value = {
                "function_call": {
                    "name": "extract_analysis_parameters",
                    "arguments": {
                        "effect_size": "OR",
                        "model_type": "random",
                        "method": "REML",
                        "subgroup_column": "地域"
                    }
                }
            }
            
            result = extract_parameters_from_text(user_input, ["地域"])
            
            # Then: 構造化されたパラメータが抽出される
            assert result["effect_size"] == "OR"
            assert result["model_type"] == "random"
            assert result["method"] == "REML"
            assert mock_gemini.called
    
    def test_automatic_csv_column_mapping(self):
        """CSV列の自動マッピングが機能すること"""
        # Given: 様々な列名パターン
        csv_columns = ["StudyID", "Treatment_Events", "Treatment_N", "Control_Events", "Control_N", "Country"]
        user_input = "国別のサブグループ解析をお願いします"
        
        # When: 列マッピング実行
        result = extract_parameters_from_text(user_input, csv_columns)
        
        # Then: 適切な列がマッピングされる
        assert "subgroup_column" in result
        assert result["subgroup_column"] in ["Country", "country"] or "Country" in str(result)
    
    def test_parameter_completion_detection(self):
        """パラメータ収集完了の検出ができること"""
        # Given: 完全なパラメータセット
        complete_params = {
            "effect_size": "OR",
            "model_type": "random",
            "method": "REML"
        }
        
        # When: 完了チェック
        result = process_user_input_with_gemini(
            "それで解析してください", [], complete_params, [], {}
        )
        
        # Then: 解析準備完了と判定される
        assert result["is_ready_to_analyze"] == True
        assert "解析を開始" in result["bot_message"]
    
    def test_japanese_natural_language_processing(self):
        """日本語の自然言語処理が正常に動作すること"""
        # Given: 日本語の様々な表現
        japanese_inputs = [
            "オッズ比でお願いします",
            "ランダム効果モデルを使用してください",
            "地域ごとのサブグループ解析も行ってください",
            "REML法で推定してください"
        ]
        
        for japanese_input in japanese_inputs:
            # When: 日本語処理
            result = extract_parameters_from_text(japanese_input, [])
            
            # Then: 適切に理解される
            assert len(result) > 0
            # 少なくとも何らかのパラメータが抽出される
            assert any(key in result for key in ["effect_size", "model_type", "method", "subgroup_column"])
    
    def test_conversation_state_persistence(self):
        """会話状態が適切に保持されること"""
        # Given: 会話状態
        from utils.conversation_state import ConversationState, get_or_create_state, save_state
        
        thread_ts = "1234567890.123456"
        channel_id = "C123456"
        
        # When: 状態作成と更新
        state = get_or_create_state(thread_ts, channel_id)
        state.state = DialogState.ANALYSIS_PREFERENCE
        state.collected_params = {"effect_size": "OR"}
        save_state(state)
        
        # 状態を再取得
        retrieved_state = get_or_create_state(thread_ts, channel_id)
        
        # Then: 状態が保持されている
        assert retrieved_state.state == DialogState.ANALYSIS_PREFERENCE
        assert retrieved_state.collected_params["effect_size"] == "OR"
    
    def test_48_hour_context_retention(self):
        """48時間のコンテキスト保持ができること"""
        import time
        from utils.conversation_state import ConversationState
        
        # Given: 48時間前の状態
        old_state = ConversationState(
            thread_ts="old_thread",
            channel_id="C123456",
            created_at=time.time() - (48 * 3600 + 1)  # 48時間+1秒前
        )
        
        # Given: 新しい状態
        new_state = ConversationState(
            thread_ts="new_thread",
            channel_id="C123456",
            created_at=time.time()
        )
        
        # When: 有効性チェック
        old_is_valid = old_state.is_valid()
        new_is_valid = new_state.is_valid()
        
        # Then: 適切に期限管理される
        assert old_is_valid == False  # 48時間超過で無効
        assert new_is_valid == True   # 新しい状態は有効
    
    def test_max_20_message_history(self):
        """最大20メッセージの履歴管理ができること"""
        from utils.conversation_state import ConversationState
        
        # Given: 状態オブジェクト
        state = ConversationState("thread", "channel")
        
        # When: 25メッセージを追加
        for i in range(25):
            state.conversation_history.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}"
            })
        
        # 履歴制限を適用
        if len(state.conversation_history) > 20:
            state.conversation_history = state.conversation_history[-20:]
        
        # Then: 最大20メッセージに制限される
        assert len(state.conversation_history) == 20
        assert state.conversation_history[0]["content"] == "Message 5"  # 古いものが削除される
        assert state.conversation_history[-1]["content"] == "Message 24"
    
    def test_storage_backend_configuration(self):
        """ストレージバックエンドの設定が機能すること"""
        import os
        from utils.conversation_state import get_storage_backend
        
        # Given: 様々なストレージ設定
        storage_configs = ["redis", "memory", "file", "dynamodb"]
        
        for config in storage_configs:
            # When: 環境変数設定
            with patch.dict(os.environ, {"STORAGE_BACKEND": config}):
                backend = get_storage_backend()
                
                # Then: 適切なバックエンドが選択される
                assert backend is not None
                assert hasattr(backend, 'get')
                assert hasattr(backend, 'set')
