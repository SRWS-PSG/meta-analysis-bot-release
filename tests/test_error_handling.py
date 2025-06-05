"""
エラーハンドリングテスト
CLAUDE.md仕様: エラーシナリオとリトライ機構をテストする
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from mcp_legacy.error_handling import ErrorHandler, ErrorType
from mcp_legacy.self_debugging import SelfDebuggingHandler


class TestErrorHandling:
    """エラーハンドリング機能のテストクラス"""
    
    def test_csv_format_error_handling(self):
        """不正CSV形式エラーのハンドリングができること"""
        # Given: 不正なCSVデータ
        malformed_csv = "Study,Events\nStudy1,invalid_number"
        
        # When: CSVエラー処理
        error_handler = ErrorHandler()
        result = error_handler.handle_csv_error(malformed_csv)
        
        # Then: 日本語エラーメッセージが返される
        assert "CSV" in result["error_message"]
        assert "形式" in result["error_message"] or "データ" in result["error_message"]
        assert result["error_type"] == ErrorType.CSV_FORMAT_ERROR
    
    def test_r_execution_error_gemini_debugging(self):
        """R実行エラー時のGemini自動デバッグが機能すること"""
        # Given: Rエラーとスクリプト
        r_error = "Error in rma(yi, vi): object 'invalid_column' not found"
        script = "rma(yi=invalid_column, vi=se_column, data=df)"
        
        # When: 自動デバッグ実行
        with patch('core.gemini_client.GeminiClient.debug_r_script') as mock_debug:
            mock_debug.return_value = {
                "fixed_script": "rma(yi=effect_size, vi=se_column, data=df)",
                "explanation": "列名を修正しました"
            }
            
            debug_handler = SelfDebuggingHandler()
            result = debug_handler.debug_r_error(r_error, script)
            
            # Then: 修正されたスクリプトが返される
            assert "fixed_script" in result
            assert "invalid_column" not in result["fixed_script"]
            assert mock_debug.called
    
    def test_maximum_3_retry_attempts(self):
        """最大3回のリトライ試行が制限されること"""
        # Given: 繰り返しエラーを起こすスクリプト
        failing_script = "stop('Persistent error')"
        
        # When: リトライ実行
        with patch('core.r_executor.RExecutor.execute_script') as mock_execute:
            mock_execute.return_value = {
                "return_code": 1,
                "stderr": "Persistent error",
                "stdout": ""
            }
            
            debug_handler = SelfDebuggingHandler(max_retries=3)
            result = debug_handler.execute_with_retry(failing_script)
            
            # Then: 3回までしかリトライしない
            assert mock_execute.call_count <= 3
            assert result["retry_count"] <= 3
    
    def test_error_pattern_matching_fixes(self):
        """エラーパターンマッチングによる具体的修正提案ができること"""
        # Given: 既知エラーパターン
        error_patterns = {
            "object 'yi' not found": "効果量列が見つかりません",
            "subscript out of bounds": "データの範囲を超えています",
            "package 'metafor' is not available": "metaforパッケージがインストールされていません"
        }
        
        for error_text, expected_message in error_patterns.items():
            # When: エラーパターンマッチング
            error_handler = ErrorHandler()
            result = error_handler.match_error_pattern(error_text)
            
            # Then: 適切な修正提案が返される
            assert result["matched"] == True
            assert expected_message in result["suggestion"]
    
    def test_exponential_backoff_retry(self):
        """指数バックオフによるリトライ機構が機能すること"""
        import time
        
        # Given: リトライハンドラー
        retry_handler = SelfDebuggingHandler()
        
        # When: 指数バックオフ計算
        delays = [retry_handler.calculate_backoff_delay(i) for i in range(3)]
        
        # Then: 遅延時間が指数的に増加する
        assert delays[0] < delays[1] < delays[2]
        assert delays[0] >= 1  # 最小1秒
        assert delays[2] <= 8  # 最大8秒程度
    
    def test_slack_3_second_timeout_handling(self):
        """Slackの3秒タイムアウトに対応した非同期処理ができること"""
        import asyncio
        
        # Given: 長時間処理を要するタスク
        async def long_running_task():
            await asyncio.sleep(5)  # 5秒遅延
            return "completed"
        
        # When: 非同期処理実行
        from mcp_legacy.async_processing import AsyncAnalysisRunner
        
        runner = AsyncAnalysisRunner()
        task_id = runner.submit_task(long_running_task())
        
        # Then: 即座にタスクIDが返される
        assert task_id is not None
        assert len(task_id) > 0
    
    def test_japanese_error_messages(self):
        """全てのユーザー向けエラーメッセージが日本語であること"""
        # Given: 様々なエラータイプ
        error_types = [
            ErrorType.CSV_FORMAT_ERROR,
            ErrorType.R_EXECUTION_ERROR,
            ErrorType.INSUFFICIENT_DATA_ERROR,
            ErrorType.PARAMETER_VALIDATION_ERROR
        ]
        
        for error_type in error_types:
            # When: エラーメッセージ生成
            error_handler = ErrorHandler()
            message = error_handler.get_user_friendly_message(error_type)
            
            # Then: 日本語メッセージが返される
            assert any(char in message for char in "あかさたなはまやらわ")
            assert len(message) > 0
    
    def test_technical_error_logging_in_english(self):
        """技術的エラーが英語でログ出力されること"""
        import logging
        from unittest.mock import patch
        
        # Given: ログハンドラー
        with patch('logging.Logger.error') as mock_logger:
            # When: 技術エラーログ出力
            error_handler = ErrorHandler()
            error_handler.log_technical_error("R execution failed: invalid syntax")
            
            # Then: 英語ログが出力される
            mock_logger.assert_called()
            logged_message = mock_logger.call_args[0][0]
            assert "R execution failed" in logged_message
            # 日本語文字が含まれていないことを確認
            assert not any(char in logged_message for char in "あかさたなはまやらわ")
    
    def test_different_error_type_handlers(self):
        """異なるエラータイプに応じた専用ハンドラーが存在すること"""
        # Given: エラーハンドラー
        error_handler = ErrorHandler()
        
        # When & Then: 各エラータイプに専用メソッドがある
        assert hasattr(error_handler, 'handle_csv_error')
        assert hasattr(error_handler, 'handle_r_execution_error')
        assert hasattr(error_handler, 'handle_parameter_error')
        assert hasattr(error_handler, 'handle_network_error')
        
        # 各メソッドが呼び出し可能
        csv_result = error_handler.handle_csv_error("invalid data")
        r_result = error_handler.handle_r_execution_error("R error")
        param_result = error_handler.handle_parameter_error("missing param")
        
        assert all('error_type' in result for result in [csv_result, r_result, param_result])
    
    def test_error_recovery_suggestions(self):
        """エラーからの復旧提案が提供されること"""
        # Given: 様々なエラーシナリオ
        error_scenarios = {
            "CSV format error": "正しいCSV形式で再アップロードしてください",
            "R package missing": "管理者にパッケージインストールを依頼してください",
            "Insufficient data": "より多くの研究データを含めて再実行してください"
        }
        
        for error_type, expected_suggestion in error_scenarios.items():
            # When: 復旧提案取得
            error_handler = ErrorHandler()
            suggestion = error_handler.get_recovery_suggestion(error_type)
            
            # Then: 適切な復旧提案が返される
            assert len(suggestion) > 0
            assert any(char in suggestion for char in "あかさたなはまやらわ")
    
    def test_analysis_failure_detailed_messages(self):
        """解析失敗時に詳細なエラーメッセージが提供されること"""
        # Given: 解析失敗シナリオ
        failure_scenarios = {
            "convergence_failure": "収束判定が失敗しました",
            "insufficient_studies": "研究数が不十分です",
            "high_heterogeneity": "異質性が高すぎます"
        }
        
        for scenario, expected_message in failure_scenarios.items():
            # When: 詳細エラーメッセージ生成
            error_handler = ErrorHandler()
            detailed_message = error_handler.get_detailed_failure_message(scenario)
            
            # Then: 詳細な日本語メッセージが返される
            assert len(detailed_message) > 50  # 十分詳細
            assert expected_message in detailed_message
            assert any(char in detailed_message for char in "あかさたなはまやらわ")
    
    def test_gemini_api_error_handling(self):
        """Gemini APIエラーのハンドリングができること"""
        # Given: Gemini APIエラー
        api_errors = [
            "Rate limit exceeded",
            "API key invalid",
            "Request timeout",
            "Model unavailable"
        ]
        
        for api_error in api_errors:
            # When: Geminiエラー処理
            error_handler = ErrorHandler()
            result = error_handler.handle_gemini_api_error(api_error)
            
            # Then: 適切なエラー処理がされる
            assert "retry" in result or "再試行" in result["message"]
            assert result["should_retry"] in [True, False]
    
    def test_file_access_error_handling(self):
        """ファイルアクセスエラーのハンドリングができること"""
        # Given: ファイルアクセスエラー
        file_errors = [
            "Permission denied",
            "File not found",
            "Disk space full",
            "Invalid file format"
        ]
        
        for file_error in file_errors:
            # When: ファイルエラー処理
            error_handler = ErrorHandler()
            result = error_handler.handle_file_error(file_error)
            
            # Then: ユーザーフレンドリーなメッセージ
            assert "ファイル" in result["message"]
            assert any(char in result["message"] for char in "あかさたなはまやらわ")
    
    def test_error_context_preservation(self):
        """エラー文脈が保持されること"""
        # Given: エラー文脈情報
        error_context = {
            "analysis_type": "OR",
            "data_rows": 15,
            "user_input": "オッズ比で解析",
            "step": "parameter_collection"
        }
        
        # When: エラー処理時に文脈保持
        error_handler = ErrorHandler()
        result = error_handler.handle_error_with_context("Invalid parameter", error_context)
        
        # Then: 文脈情報が保持される
        assert "context" in result
        assert result["context"]["analysis_type"] == "OR"
        assert result["context"]["step"] == "parameter_collection"
        assert "オッズ比" in result["context"]["user_input"]
