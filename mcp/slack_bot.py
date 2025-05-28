"""
Slack Botメインモジュール

メタアナリシスSlack Botのメイン機能を提供します。
"""

import os
import re
import json
import tempfile
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
import pandas as pd
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError # SlackApiErrorをインポート
import requests
# import rpy2.robjects as robjects # For loading RData # rpy2 関連削除
# from rpy2.robjects import pandas2ri # rpy2 関連削除
# pandas2ri.activate() # rpy2 関連削除


from mcp.thread_context import ThreadContextManager
from mcp.async_processing import AsyncAnalysisRunner
from mcp.error_handling import ErrorHandler, RetryableError
# Remove AnalysisPreferenceDialog as we are moving to a more dynamic approach
# from mcp.user_interaction import AnalysisPreferenceDialog, get_report_type_from_preferences
from mcp.gemini_utils import (
    interpret_meta_analysis_results, 
    interpret_meta_regression_results, 
    suggest_further_analyses, 
    generate_academic_writing_suggestion, 
    detect_reanalysis_intent,
    extract_parameters_from_user_input, # New import
    analyze_csv_compatibility_with_mcp_prompts # Ensure this is imported if used, or defined
)
from mcp.meta_analysis import download_file, analyze_csv, run_meta_analysis, upload_file_to_slack, cleanup_temp_files # analyze_csv is used by CsvProcessor
from mcp.report_generator import generate_report
from mcp.rdata_parser import process_rdata_to_json
from mcp.dialog_state_manager import DialogStateManager
from mcp.csv_processor import CsvProcessor
from mcp.parameter_collector import ParameterCollector
from mcp.analysis_executor import AnalysisExecutor
from mcp.report_handler import ReportHandler
from mcp.message_handlers import MessageHandler # New import


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MetaAnalysisBot:
    """メタアナリシスSlack Botクラス"""
    
    def __init__(self):
        """初期化"""
        self.app = App(
            token=os.environ.get("SLACK_BOT_TOKEN", "").strip(),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET", "").strip()
        )
        
        # Bot自身のユーザーIDを取得
        self.bot_user_id = None
        try:
            auth_test_response = self.app.client.auth_test()
            self.bot_user_id = auth_test_response.get("user_id")
            if self.bot_user_id:
                logger.info(f"Successfully fetched bot user ID: {self.bot_user_id}")
            else:
                logger.error("Failed to fetch bot user ID: 'user_id' not found in auth_test response.")
        except SlackApiError as e:
            logger.error(f"Slack API Error fetching bot user ID via auth_test: {e.response['error'] if e.response else e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error fetching bot user ID via auth_test: {e}", exc_info=True)

        storage_backend = os.environ.get("STORAGE_BACKEND", "memory")
        self.context_manager = ThreadContextManager(storage_backend=storage_backend)
        
        self.async_runner = AsyncAnalysisRunner()
        
        self.error_handler = ErrorHandler()

        # CsvProcessorのインスタンス化に必要な情報を渡す
        self.csv_processor = CsvProcessor(
            context_manager=self.context_manager,
            async_runner=self.async_runner,
            error_handler=self.error_handler,
            required_params_def=ParameterCollector.REQUIRED_PARAMS_DEFINITION 
        )
        # ParameterCollectorのインスタンス化
        self.parameter_collector = ParameterCollector(
            context_manager=self.context_manager,
            async_runner=self.async_runner
        )
        # AnalysisExecutorのインスタンス化
        self.analysis_executor = AnalysisExecutor(
            context_manager=self.context_manager,
            async_runner=self.async_runner,
            error_handler=self.error_handler,
            app_client=self.app.client,
            report_handler_func=self._handle_report_generation_and_upload_wrapper # Updated to wrapper
        )
        # ReportHandlerのインスタンス化
        self.report_handler = ReportHandler(
            context_manager=self.context_manager,
            app_client=self.app.client
        )
        # MessageHandlerのインスタンス化時に bot_user_id を渡す
        self.message_handler = MessageHandler(
            context_manager=self.context_manager,
            csv_processor=self.csv_processor,
            parameter_collector=self.parameter_collector,
            analysis_executor=self.analysis_executor,
            bot_user_id=self.bot_user_id # bot_user_id を渡す
        )
        
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """イベントハンドラーを登録する"""
        # Pass the correct method reference from self.message_handler
        self.app.event("app_mention")(self.handle_app_mention_wrapper) 
        self.app.event("message")(self.handle_message_wrapper)
        self.app.event("file_shared")(self.handle_file_shared_wrapper)

    # --- Wrappers for MessageHandler methods ---
    def handle_app_mention_wrapper(self, event, client):
        # Pass self.context_manager directly as it's an instance attribute of MetaAnalysisBot
        self.message_handler.handle_app_mention(event, client, self.context_manager)

    def handle_message_wrapper(self, event, client):
        # Pass wrapper functions for run_meta_analysis and check_analysis_job
        self.message_handler.handle_message(event, client, self.run_meta_analysis_wrapper, self.analysis_executor.check_analysis_job)

    def handle_file_shared_wrapper(self, event, client):
        self.message_handler.handle_file_shared(event, client)

    # --- Methods moved to other classes or to be removed ---
    # handle_file_shared, handle_message, handle_app_mention, _handle_general_question are now in MessageHandler
    # _process_csv_file, _check_csv_analysis_job are in CsvProcessor
    # _update_collected_params_and_get_next_question, _get_missing_data_columns_question, _handle_analysis_preference_dialog are in ParameterCollector
    # _check_processing_status, _check_analysis_job are in AnalysisExecutor
    # _handle_report_generation_and_upload is in ReportHandler

    def run_meta_analysis_wrapper(self, csv_path, analysis_preferences, thread_dir):
        """
        Wrapper for run_meta_analysis to be passed to ParameterCollector and MessageHandler.
        """
        return run_meta_analysis(csv_path, analysis_preferences, thread_dir)

    def _handle_report_generation_and_upload_wrapper(self, result, channel_id, thread_ts, client, context):
        """
        Wrapper for ReportHandler's method to be called by AnalysisExecutor.
        """
        return self.report_handler.handle_report_generation_and_upload(result, channel_id, thread_ts, client, context)

    # _handle_general_question is now part of MessageHandler, but if it needs specific bot logic, it can be a wrapper too.
    # For now, assuming MessageHandler's version is sufficient. If not, a wrapper can be added here.

    def start(self):
        socket_mode = os.environ.get("SOCKET_MODE", "false").lower() == "true"
        
        if socket_mode:
            # Socket Mode - WebSocket接続でSlackと通信
            logger.info("Starting bot in Socket Mode")
            if not os.environ.get("SLACK_APP_TOKEN"):
                logger.error("SLACK_APP_TOKEN is required for Socket Mode")
                return
            SocketModeHandler(self.app, os.environ.get("SLACK_APP_TOKEN")).start()
        else:
            # HTTP Mode - HTTPエンドポイントでSlackと通信（Cloud Run対応）
            port = int(os.environ.get("PORT", 8080))
            logger.info(f"Starting bot in HTTP Mode on port {port}")
            self.app.start(port=port)

if __name__ == "__main__":
    bot = MetaAnalysisBot()
    bot.start()
