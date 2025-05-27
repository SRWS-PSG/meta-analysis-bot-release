"""
Analysis Executorモジュール

メタアナリシスおよび関連する非同期ジョブの実行と状態監視を行います。
"""
import os
import logging
import time
import json
from pathlib import Path

from mcp.meta_analysis import upload_file_to_slack, cleanup_temp_files # For _check_analysis_job
from mcp.rdata_parser import process_rdata_to_json # For _check_analysis_job
from mcp.dialog_state_manager import DialogStateManager
from mcp.parameter_collector import ParameterCollector # For REQUIRED_PARAMS_DEFINITION

logger = logging.getLogger(__name__)

class AnalysisExecutor:
    def __init__(self, context_manager, async_runner, error_handler, app_client, report_handler_func):
        self.context_manager = context_manager
        self.async_runner = async_runner
        self.error_handler = error_handler
        self.app_client = app_client # Slack app client for uploading files
        self._handle_report_generation_and_upload = report_handler_func # Function from ReportHandler

    def check_processing_status(self, thread_ts, channel_id, client, context, user_text=None):
        """処理中のジョブステータスを確認し、ユーザーに通知する
        Returns: bool - ユーザーの入力をパラメータとして処理すべきかどうか"""
        current_dialog_state = context.get("dialog_state", {})
        if current_dialog_state.get("type") == "analysis_preference" and current_dialog_state.get("state") == "collecting_params":
            logger.info(f"Thread {thread_ts}: Already in 'collecting_params' state. Skipping redundant job status check.")
            return False

        if context.get("file_processing_job_id"):
            job_id = context["file_processing_job_id"]
            processed_csv_job_ids = set(context.get("processed_csv_job_ids", []))
            if job_id in processed_csv_job_ids:
                logger.info(f"CSV job {job_id} already processed. Current dialog_state: {current_dialog_state}")
                context.pop("file_processing_job_id", None)
                if current_dialog_state.get("type") == "processing_file":
                    logger.warning(f"Thread {thread_ts}: Job {job_id} was processed, but dialog was 'processing_file'. Forcing to 'analysis_preference'.")
                    DialogStateManager.transition_to_collecting_params(context, ParameterCollector.REQUIRED_PARAMS_DEFINITION)
                    self.context_manager.save_context(thread_ts, context, channel_id)
                    return True
                self.context_manager.save_context(thread_ts, context, channel_id)
                return False
            
            job_status = self.async_runner.get_analysis_status(job_id)
            if job_status["status"] in ["pending", "running"]:
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="現在CSVファイルを分析中です。完了まで少々お待ちください。")
                return False # Still processing, don't interpret user text as params yet
            
            elif job_status["status"] == "completed":
                processed_csv_job_ids.add(job_id)
                context["processed_csv_job_ids"] = list(processed_csv_job_ids)
                result = job_status["result"]
                thread_dir = context.get("data_state", {}).get("thread_dir") or (str(Path(result.get("file_path")).parent) if result.get("file_path") else None)
                
                context["data_state"] = {
                    "file_path": str(result.get("file_path")), "summary": result.get("summary"),
                    "suitable_for_meta_analysis": result.get("suitable_for_meta_analysis"),
                    "gemini_analysis": result.get("gemini_analysis"), "thread_dir": thread_dir
                }
                if result.get("suitable_for_meta_analysis"):
                    DialogStateManager.transition_to_collecting_params(context, ParameterCollector.REQUIRED_PARAMS_DEFINITION)
                    context.pop("file_processing_job_id", None)
                    self.context_manager.save_context(thread_ts, context, channel_id)
                    return True # CSV suitable, now process user_text as params
                else:
                    DialogStateManager.set_dialog_state(context, "WAITING_FILE")
                    user_msg = result.get("gemini_analysis", {}).get("user_message") or "CSVファイルにメタアナリシスに必要な列が含まれていませんでした。"
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=user_msg)
                    if result.get("file_path"): cleanup_temp_files(str(result.get("file_path")))
                context.pop("file_processing_job_id", None)
                self.context_manager.save_context(thread_ts, context, channel_id)
                return False # CSV unsuitable, don't process user_text as params

            elif job_status["status"] == "failed":
                error_msg = job_status.get("error", "不明なエラー")
                if isinstance(job_status.get("result"), dict) and job_status.get("result", {}).get("gemini_analysis", {}).get("user_message"):
                    error_msg = job_status["result"]["gemini_analysis"]["user_message"]
                error_info = {"error_type": "AnalysisError", "error_message": error_msg, "is_retryable": False}
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=self.error_handler.format_error_message(error_info))
                if job_status.get("result") and job_status.get("result", {}).get("file_path"):
                    cleanup_temp_files(str(job_status.get("result").get("file_path")))
                context.pop("file_processing_job_id", None)
                DialogStateManager.set_dialog_state(context, "WAITING_FILE")
                self.context_manager.save_context(thread_ts, context, channel_id)
                return False

        if context.get("analysis_job_id"):
            job_status = self.async_runner.get_analysis_status(context["analysis_job_id"])
            if job_status["status"] in ["pending", "running"]:
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="現在メタアナリシスを実行中です。完了まで少々お待ちください。")
                return False # Analysis running, don't process user_text as params
        
        logger.info(f"No active file_processing_job or analysis_job found for thread {thread_ts}, or job already handled.")
        # If no file_processing_job was active, and no analysis_job is active,
        # it implies we might be in a state to collect params if dialog state allows.
        # However, the calling function in handle_message should make the final decision based on dialog_state.
        # This function's primary role is to update on *active* jobs.
        # If we reach here, it means no *CSV processing* job is active.
        # The calling function will then check dialog_state to see if it's 'analysis_preference'.
        return False # Default to False, let handle_message decide if params should be processed.


    def check_analysis_job(self, job_id, channel_id, thread_ts, client):
        context = self.context_manager.get_context(thread_ts, channel_id) or {}
        processed_job_ids = set(context.get("processed_job_ids", []))
        if job_id in processed_job_ids:
            logger.info(f"Job {job_id} has already been processed. Skipping check_analysis_job.")
            return

        progress_message_ts = None
        try:
            response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="メタアナリシスの準備を開始しました...")
            progress_message_ts = response.get("ts")
        except Exception as e: logger.error(f"Failed to post initial progress message for job {job_id}: {e}")

        max_checks, check_interval = 60, 10
        for i in range(max_checks):
            status = self.async_runner.get_analysis_status(job_id)
            current_time_elapsed = (i + 1) * check_interval

            if progress_message_ts and status["status"] in ["pending", "running"]:
                try: client.chat_update(channel=channel_id, ts=progress_message_ts, text=f"メタアナリシスを実行中です... (約{current_time_elapsed}秒経過)")
                except Exception as e: logger.error(f"Failed to update progress message for job {job_id}: {e}")

            if status["status"] == "completed":
                result = status["result"]
                context.setdefault("analysis_state", {}).update({"result": result, "stage": "completed"})
                
                final_msg = "メタアナリシスの主要処理が完了しました。結果をアップロードしています..."
                try:
                    if progress_message_ts: client.chat_update(channel=channel_id, ts=progress_message_ts, text=final_msg)
                    else: progress_message_ts = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=final_msg).get("ts")
                except Exception as e:
                    logger.error(f"Failed to update/post final progress message (completed) for job {job_id}: {e}")
                    if not progress_message_ts: # If initial post failed and update also failed
                         client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=final_msg)


                if result.get("success"):
                    if "r_script_path" in result and os.path.exists(result["r_script_path"]):
                        try: upload_file_to_slack(self.app_client, result["r_script_path"], channel_id, "Rスクリプト", thread_ts); time.sleep(1)
                        except Exception as e: logger.error(f"Rスクリプトのアップロードエラー: {e}")
                    
                    for plot_info in result.get("generated_plots", []):
                        plot_path = plot_info.get("path")
                        plot_label = plot_info.get("label", "プロット")
                        plot_full_path = os.path.join(result["output_dir"], plot_path) if result.get("output_dir") and not os.path.isabs(plot_path) else plot_path
                        if plot_full_path and os.path.exists(plot_full_path):
                            try: upload_file_to_slack(self.app_client, plot_full_path, channel_id, plot_label.replace("_", " ").title(), thread_ts); time.sleep(1)
                            except Exception as e: logger.error(f"{plot_label} のアップロードエラー: {e}")
                    
                    if "result_data_path" in result and os.path.exists(result["result_data_path"]):
                        try: upload_file_to_slack(self.app_client, result["result_data_path"], channel_id, "結果データ (result.RData)", thread_ts); time.sleep(1)
                        except Exception as e: logger.error(f"結果データのアップロードエラー: {e}")

                    summary_content_str = result.get("structured_summary_content")
                    summary_json_path = result.get("structured_summary_json_path")
                    parsed_summary = None
                    if summary_content_str and summary_content_str != "{}":
                        try: parsed_summary = json.loads(summary_content_str)
                        except json.JSONDecodeError as e: logger.error(f"structured_summary_content のパース失敗: {e}")
                    elif summary_json_path and os.path.exists(summary_json_path):
                        try:
                            rdata_json_str = process_rdata_to_json(summary_json_path)
                            if rdata_json_str and rdata_json_str != "{}": parsed_summary = json.loads(rdata_json_str)
                        except Exception as e: logger.error(f"{summary_json_path} の処理エラー: {e}")
                    
                    if isinstance(parsed_summary, dict) and "error" in parsed_summary:
                        logger.error(f"構造化サマリーエラー: {parsed_summary['error']}")
                        context["processed_rdata_json"] = None
                    else:
                        context["processed_rdata_json"] = parsed_summary
                    
                    self._handle_report_generation_and_upload(result, channel_id, thread_ts, client, context) # Call the passed function
                else:
                    error_text = f"メタ解析の実行に失敗しました: {result.get('error', '不明なエラー')}"
                    try:
                        if progress_message_ts: client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                        else: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                    except Exception as e_upd: logger.error(f"失敗時メッセージの更新エラー: {e_upd}")
                    if "r_script_path" in result and os.path.exists(result["r_script_path"]):
                        try: upload_file_to_slack(self.app_client, result["r_script_path"], channel_id, "失敗したRスクリプト", thread_ts); time.sleep(1)
                        except Exception as e: logger.error(f"失敗Rスクリプトのアップロードエラー: {e}")
                
                context["dialog_state"] = {"type": "post_analysis", "state": "ready_for_questions"}
                break # Exit loop on completion
            
            elif status["status"] == "failed":
                error_info = {"error_type": "AnalysisJobError", "error_message": status.get("error", "不明なエラー")}
                error_text = self.error_handler.format_error_message(error_info)
                try:
                    if progress_message_ts: client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                    else: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                except Exception as e_upd: logger.error(f"ジョブ失敗メッセージの更新エラー: {e_upd}")
                
                if isinstance(status.get("result"), dict) and status.get("result", {}).get("r_script_path"):
                    if os.path.exists(status["result"]["r_script_path"]):
                        try: upload_file_to_slack(self.app_client, status["result"]["r_script_path"], channel_id, "失敗したRスクリプト (ジョブ失敗時)", thread_ts); time.sleep(1)
                        except Exception as e: logger.error(f"ジョブ失敗Rスクリプトのアップロードエラー: {e}")
                context["dialog_state"] = {"type": "post_analysis", "state": "error_occurred"}
                break # Exit loop on failure

            time.sleep(check_interval)
        else: # Loop finished without break (timeout)
            timeout_text = "分析処理がタイムアウトしました。"
            try:
                if progress_message_ts: client.chat_update(channel=channel_id, ts=progress_message_ts, text=timeout_text)
                else: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=timeout_text)
            except Exception as e_upd: logger.error(f"タイムアウトメッセージの更新エラー: {e_upd}")
            
            job_details_on_timeout = self.async_runner.get_analysis_status(job_id) # Get final status
            if isinstance(job_details_on_timeout.get("result"), dict) and job_details_on_timeout.get("result", {}).get("r_script_path"):
                if os.path.exists(job_details_on_timeout["result"]["r_script_path"]):
                    try: upload_file_to_slack(self.app_client, job_details_on_timeout["result"]["r_script_path"], channel_id, "Rスクリプト (タイムアウト時)", thread_ts); time.sleep(1)
                    except Exception as e: logger.error(f"タイムアウトRスクリプトのアップロードエラー: {e}")
            context["dialog_state"] = {"type": "post_analysis", "state": "timeout"}

        processed_job_ids.add(job_id)
        context["processed_job_ids"] = list(processed_job_ids)
        self.context_manager.save_context(thread_ts, context, channel_id)
