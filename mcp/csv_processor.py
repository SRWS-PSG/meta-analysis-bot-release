"""
CSV Processorモジュール

CSVファイルのダウンロード、分析、および関連する状態管理を行います。
"""
import os
import logging
import time
import json
from pathlib import Path

from mcp.meta_analysis import download_file, analyze_csv, cleanup_temp_files
from mcp.dialog_state_manager import DialogStateManager # Assuming DialogStateManager is in its own file

logger = logging.getLogger(__name__)

class CsvProcessor:
    def __init__(self, context_manager, async_runner, error_handler, required_params_def):
        self.context_manager = context_manager
        self.async_runner = async_runner
        self.error_handler = error_handler
        self.REQUIRED_PARAMS_DEFINITION = required_params_def # Store for use in _check_csv_analysis_job

    def process_csv_file(self, file_obj, thread_ts, channel_id, client, context):
        """
        CSVファイルを処理する共通メソッド
        """
        # 処理中チェックを追加
        current_dialog_type = context.get("dialog_state", {}).get("type")
        # process_csv_fileが呼ばれるのは、基本的に handle_app_mention から。
        # handle_app_mention 内で、既にファイル処理中かどうかをチェックする。
        # ここでは、dialog_stateが "waiting_for_file" から "processing_file" に遷移することを前提とする。
        # もし、何らかの理由で既に処理中の場合に呼ばれたら、重複処理を避ける。
        if current_dialog_type == "processing_file" and context.get("file_processing_job_id"):
            # 既に別のCSVファイルの処理が進行中の場合
            logger.warning(f"Attempted to process CSV file {file_obj.get('name')} while another CSV is already being processed (job_id: {context.get('file_processing_job_id')}). Skipping.")
            # ユーザーに通知（任意）
            # client.chat_postMessage(
            #     channel=channel_id,
            #     thread_ts=thread_ts,
            #     text=f"現在、ファイル「{context.get('data_state', {}).get('summary', {}).get('original_filename', '以前のファイル')}」を処理中です。完了後に再度お試しください。"
            # )
            return
        elif current_dialog_type == "analysis_preference":
             client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="現在メタアナリシスのパラメータ設定中です。設定完了後に新しいファイルを共有してください。"
            )
             return


        context["initial_csv_prompt_sent"] = False
        self.context_manager.save_context(thread_ts, context, channel_id)

        progress_message_ts = None
        try:
            response = client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"CSVファイル「{file_obj.get('name')}」の分析を開始しています..."
            )
            progress_message_ts = response.get("ts")
        except Exception as e:
            logger.error(f"Failed to post CSV processing progress message: {e}")

        try:
            logger.info(f"Processing CSV file: {file_obj.get('name')}")
            
            thread_dir = self.context_manager.get_thread_storage_path(thread_ts, channel_id)
            if not thread_dir:
                logger.error(f"Failed to get or create thread_dir for thread {thread_ts}, channel {channel_id}. Aborting CSV processing.")
                error_text = "ファイル処理に必要な作業ディレクトリの準備に失敗しました。(Error code: CSP001)"
                if progress_message_ts:
                    try:
                        client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                    except Exception as e_upd:
                        logger.error(f"Failed to update progress message: {e_upd}")
                        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                else:
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                return

            # ローカル一時ファイルパスの準備
            original_filename = file_obj.get('name', 'input.csv')
            local_csv_path = Path(thread_dir) / original_filename

            if progress_message_ts:
                try:
                    client.chat_update(
                        channel=channel_id,
                        ts=progress_message_ts,
                        text=f"CSVファイル「{file_obj.get('name')}」をダウンロード中..."
                    )
                except Exception as e:
                    logger.error(f"Failed to update CSV progress message: {e}")

            file_content_bytes = download_file(
                file_obj.get("url_private_download"),
                client.token
            )
            
            if not isinstance(file_content_bytes, bytes):
                logger.error(f"Downloaded file content is not bytes. Type: {type(file_content_bytes)}. Aborting.")
                error_text = "ファイルのダウンロードに失敗しました。(Error code: CSP002)"
                if progress_message_ts:
                    try:
                        client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                    except Exception as e_upd:
                        logger.error(f"Failed to update progress message: {e_upd}")
                        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                else:
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                return

            # ダウンロードしたバイトデータをローカル一時ファイルに保存
            try:
                with open(local_csv_path, "wb") as f:
                    f.write(file_content_bytes)
                logger.info(f"CSV file downloaded and saved to temporary path: {local_csv_path}")
            except Exception as e:
                logger.error(f"Failed to save downloaded CSV to {local_csv_path}: {e}")
                error_text = f"ダウンロードしたファイルの保存に失敗しました。(Error code: CSP003)\n詳細: {e}"
                if progress_message_ts: client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                else: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
                return

            # GCSへのアップロード処理はHeroku化に伴い削除
            # gcs_file_path = self.context_manager.upload_file_to_gcs(...)
            # context["gcs_csv_file_path"] = gcs_file_path 
            # 代わりにローカルパスを直接使用する
            logger.info(f"CSV file will be processed from local path: {local_csv_path}")
            context["local_csv_file_path"] = str(local_csv_path) # ローカルパスをコンテキストに保存

            if progress_message_ts:
                try:
                    client.chat_update(
                        channel=channel_id,
                        ts=progress_message_ts,
                        text=f"CSVファイル「{original_filename}」を分析中..."
                    )
                except Exception as e:
                    logger.error(f"Failed to update CSV progress message: {e}")

            # analyze_csv にはローカル一時ファイルのパスを渡す
            job_id = self.async_runner.run_analysis_async(
                analyze_csv,
                # analyze_csv が file_path を期待するように変更する必要があるかもしれない
                # 現状は file_content, thread_dir, input_filename を受け取っている
                # ここでは、analyze_csvがthread_dirとinput_filenameからローカルパスを再構築すると仮定
                # または、analyze_csvに直接ローカルパスを渡すように変更する
                {"file_path": str(local_csv_path), "thread_dir": thread_dir, "input_filename": original_filename},
                None
            )
            
            logger.info(f"Started CSV analysis job: {job_id} for local_csv_path: {local_csv_path}, thread_dir: {thread_dir}")
            
            context["file_processing_job_id"] = job_id
            context["csv_progress_message_ts"] = progress_message_ts
            context["dialog_state"] = {
                "type": "processing_file",
                "state": "analyzing_csv"
            }
            self.context_manager.save_context(thread_ts, context, channel_id)
            
            self.check_csv_analysis_job(job_id, channel_id, thread_ts, client, thread_dir, progress_message_ts)
            
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_info = self.error_handler.handle_error(e)
            error_text = f"ファイル処理中にエラーが発生しました: {self.error_handler.format_error_message(error_info)}"
            if progress_message_ts:
                try:
                    client.chat_update(channel=channel_id, ts=progress_message_ts, text=error_text)
                except Exception as e_upd:
                    logger.error(f"Failed to update progress message: {e_upd}")
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)
            else:
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_text)

    def check_csv_analysis_job(self, job_id, channel_id, thread_ts, client, thread_dir, progress_message_ts=None):
        context = self.context_manager.get_context(thread_ts, channel_id) or {}
        processed_csv_job_ids = set(context.get("processed_csv_job_ids", []))
        
        if job_id in processed_csv_job_ids:
            logger.info(f"CSV job {job_id} has already been processed. Skipping check_csv_analysis_job.")
            return

        max_checks = 60
        check_interval = 10
        
        for i in range(max_checks):
            status = self.async_runner.get_analysis_status(job_id)
            current_time_elapsed = (i + 1) * check_interval

            if progress_message_ts:
                try:
                    if status["status"] == "pending" or status["status"] == "running":
                        client.chat_update(
                            channel=channel_id,
                            ts=progress_message_ts,
                            text=f"CSVファイルを分析中です... (約{current_time_elapsed}秒経過)"
                        )
                except Exception as e:
                    logger.error(f"Failed to update CSV analysis progress message: {e}")
            
            if status["status"] == "completed":
                result = status["result"]
                context = self.context_manager.get_context(thread_ts, channel_id) or {}
                
                processed_csv_job_ids = set(context.get("processed_csv_job_ids", []))
                processed_csv_job_ids.add(job_id)
                context["processed_csv_job_ids"] = list(processed_csv_job_ids)
                
                logger.info(f"DEBUG: csv_processor - result from analyze_csv: {result}") # DEBUG LOG
                column_mappings_from_result = result.get("column_mappings", {})
                gemini_analysis_from_result = result.get("gemini_analysis")
                logger.info(f"DEBUG: csv_processor - column_mappings_from_result: {json.dumps(column_mappings_from_result, ensure_ascii=False)}") # DEBUG LOG
                logger.info(f"DEBUG: csv_processor - gemini_analysis_from_result: {json.dumps(gemini_analysis_from_result, ensure_ascii=False)}") # DEBUG LOG
                
                # data_state にはローカルの一時パスを保存する
                local_analyzed_csv_path = str(result.get("file_path")) # analyze_csvが返したパス
                
                context["data_state"] = {
                    "file_path": context.get("local_csv_file_path"), # CSV Processorが保存したローカルパス
                    "local_temp_file_path": local_analyzed_csv_path, # analyze_csvが使用したパス（クリーンアップ用）
                    "summary": result.get("summary"),
                    "suitable_for_meta_analysis": result.get("suitable_for_meta_analysis"),
                    "gemini_analysis": gemini_analysis_from_result,
                    "column_mappings": column_mappings_from_result,
                    "thread_dir": thread_dir # これはローカルの一時ディレクトリ
                }
                
                if result.get("suitable_for_meta_analysis"):
                    DialogStateManager.transition_to_collecting_params(context, self.REQUIRED_PARAMS_DEFINITION)
                else:
                    DialogStateManager.set_dialog_state(context, "WAITING_FILE")

                self.context_manager.save_context(thread_ts, context, channel_id)
                
                gemini_analysis_data = result.get("gemini_analysis")

                if not result.get("suitable_for_meta_analysis"):
                    user_message = "CSVファイルにメタアナリシスに必要な列が含まれていませんでした。"
                    if gemini_analysis_data and gemini_analysis_data.get("user_message"):
                        user_message = gemini_analysis_data.get("user_message")
                    elif result.get("user_message"): # analyze_csvからの直接のメッセージ
                        user_message = result.get("user_message")
                    
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=user_message)
                    if local_analyzed_csv_path: # ローカルの一時ファイルをクリーンアップ
                         cleanup_temp_files(local_analyzed_csv_path)
                    # GCS上のファイルは元々ないので削除処理は不要
                    return

                if not context.get("initial_csv_prompt_sent"):
                    current_dialog_state = context.get("dialog_state", {})
                    already_collecting_params = (
                        current_dialog_state.get("type") == "analysis_preference" and
                        current_dialog_state.get("state") == "collecting_params" and
                        (not current_dialog_state.get("is_initial_response") or 
                         any(current_dialog_state.get("collected_params", {}).get("required", {}).values()) or
                         any(current_dialog_state.get("collected_params", {}).get("optional", {}).values()))
                    )

                    if not already_collecting_params:
                        if gemini_analysis_data and gemini_analysis_data.get("user_message"):
                            user_message_template = gemini_analysis_data.get("user_message")
                            initial_message = user_message_template.format(
                                data_summary_shape_0=context.get("data_state", {}).get("summary", {}).get("shape", [0])[0],
                                data_summary_columns=context.get("data_state", {}).get("summary", {}).get("columns", [])
                            )
                            suggested_questions = gemini_analysis_data.get("suggested_questions", [])
                            if suggested_questions:
                                first_question = suggested_questions[0].get("question")
                                initial_message += f"\n\n{first_question}"
                            
                            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=initial_message)
                            context["dialog_state"]["gemini_questions"] = suggested_questions
                            context["initial_csv_prompt_sent"] = True 
                            self.context_manager.save_context(thread_ts, context, channel_id)
                        else: 
                            initial_prompt_message = (
                                f"CSVファイル「{context.get('data_state', {}).get('summary', {}).get('original_filename', 'data.csv')}」の分析が完了しました。\n"
                                f"研究数: {context.get('data_state', {}).get('summary', {}).get('shape', [0])[0]}件\n"
                                f"データ形式: {', '.join(context.get('data_state', {}).get('summary', {}).get('columns', []))}\n\n"
                                "どのようなメタアナリシスを実行しますか？ (例: オッズ比 ランダム効果、サブグループ解析はX列で)"
                            )
                            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=initial_prompt_message)
                            context["initial_csv_prompt_sent"] = True 
                            self.context_manager.save_context(thread_ts, context, channel_id)
                    else:
                        logger.info(f"Thread {thread_ts}: Already collecting params. Skipping initial prompt in check_csv_analysis_job.")
                        self.context_manager.save_context(thread_ts, context, channel_id)
                else:
                    logger.info(f"Thread {thread_ts}: Initial CSV prompt already sent. Skipping in check_csv_analysis_job.")
                    self.context_manager.save_context(thread_ts, context, channel_id)
                
                context.pop("file_processing_job_id", None)
                # local_csv_file_path は data_state に保存済みなので、ここでは削除しない
                self.context_manager.save_context(thread_ts, context, channel_id)
                logger.info(f"Thread {thread_ts}: file_processing_job_id removed after CSV analysis completion.")
                # ローカルの一時CSVファイルは、この後の処理で不要になれば削除されるべき
                # analyze_csv が返した file_path (local_analyzed_csv_path) は、
                # suitable_for_meta_analysis が False の場合に cleanup される。(これは既に上の分岐で処理済み)
                # True の場合は、後続の run_meta_analysis で使われるCSVデータはローカルのものを使用する想定。
                # CsvProcessorが最初に保存したローカルの一時CSVファイル (context["local_csv_file_path"]) は、
                # analyze_csv がそれをコピーして処理したか、直接使ったかによるが、
                # analyze_csv が返した local_analyzed_csv_path と同じであれば、既に上でクリーンアップされている。
                # 念のため、CsvProcessorが作成した元のローカルファイルも削除する。
                original_local_csv_path = context.get("local_csv_file_path")
                if original_local_csv_path and os.path.exists(original_local_csv_path) and original_local_csv_path != local_analyzed_csv_path:
                    logger.info(f"Cleaning up original local temp CSV file after successful CSV analysis: {original_local_csv_path}")
                    cleanup_temp_files(original_local_csv_path)
                elif local_analyzed_csv_path and os.path.exists(local_analyzed_csv_path): # analyze_csvが返したパスがまだ残っていれば
                    logger.info(f"Cleaning up local_analyzed_csv_path if it still exists: {local_analyzed_csv_path}")
                    cleanup_temp_files(local_analyzed_csv_path)

                return
            
            elif status["status"] == "failed":
                error_message = status.get("error", "不明なエラー") 
                if isinstance(status.get("result"), dict) and status.get("result", {}).get("gemini_analysis"): 
                    gemini_error = status.get("result").get("gemini_analysis").get("user_message") 
                    if gemini_error:
                        error_message = gemini_error
                elif isinstance(status.get("result"), dict) and status.get("result", {}).get("user_message"): # analyze_csvからの直接のエラーメッセージ
                    error_message = status.get("result").get("user_message")
                
                error_info = { 
                    "error_type": "AnalysisError", 
                    "error_message": error_message, 
                    "is_retryable": False 
                } 
                
                client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=self.error_handler.format_error_message(error_info) 
                )
                # 失敗した場合もローカル一時ファイルをクリーンアップ
                failed_job_local_path = None
                if isinstance(status.get("result"), dict) and status.get("result", {}).get("file_path"):
                    failed_job_local_path = str(status.get("result").get("file_path"))
                elif context.get("data_state", {}).get("local_temp_file_path"): # コンテキストからも試みる
                    failed_job_local_path = str(context.get("data_state").get("local_temp_file_path"))

                if failed_job_local_path:
                    cleanup_temp_files(failed_job_local_path)
                return
            
            time.sleep(check_interval)
        
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="CSV分析処理がタイムアウトしました。もう一度お試しください。"
        )
        context = self.context_manager.get_context(thread_ts, channel_id) or {}
        timed_out_csv_path = None
        job_details_on_timeout = self.async_runner.get_analysis_status(job_id)
        if isinstance(job_details_on_timeout.get("result"), dict) and job_details_on_timeout.get("result", {}).get("file_path"):
            timed_out_csv_path = str(job_details_on_timeout.get("result").get("file_path"))
        elif context.get("data_state", {}).get("file_path"):
            timed_out_csv_path = str(context.get("data_state").get("file_path"))

        if timed_out_csv_path:
            cleanup_temp_files(timed_out_csv_path)
        
        # タイムアウト時も、コンテキストにローカル一時ファイルパスがあれば削除試行
        context_local_temp_path = context.get("data_state", {}).get("local_temp_file_path")
        if context_local_temp_path and os.path.exists(context_local_temp_path) and context_local_temp_path != timed_out_csv_path:
            logger.info(f"Cleaning up local temp CSV file on timeout (from context): {context_local_temp_path}")
            cleanup_temp_files(context_local_temp_path)
        
        DialogStateManager.set_dialog_state(context, "WAITING_FILE") # タイムアウト後もファイル待ち状態に
        self.context_manager.save_context(thread_ts, context, channel_id)
