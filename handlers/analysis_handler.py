import asyncio
import json # 追加
from slack_bolt import App
from core.metadata_manager import MetadataManager
from core.r_executor import RAnalysisExecutor # コメント解除
from utils.slack_utils import create_analysis_result_message, upload_files_to_slack
from utils.file_utils import get_r_output_dir, cleanup_temp_dir_async, save_content_to_temp_file # file_utils から関数をインポート

# upload_files_to_slack は utils.slack_utils に作成するが、ここでは一旦ダミーを定義しておく
# async def upload_files_to_slack(files_to_upload: list, channel_id: str, thread_ts: str, client, job_id: str):
#     print(f"仮のupload_files_to_slackが呼び出されました。job_id: {job_id}, files: {files_to_upload}")
#     await asyncio.sleep(1)
#     return [{"type": f["type"], "id": f"F_UPLOADED_{f['type'].upper()}", "path": f["path"]} for f in files_to_upload]


def register_analysis_handlers(app: App):
    """解析関連のハンドラーを登録"""
    
    @app.action("start_analysis") # 計画書では start_analysis だが、csv_handler からの連携を考えるとパラメータあり/なしで分けるべき
                                 # ここでは一旦 start_analysis のまま進め、後でパラメータ収集フローと合わせて調整する
    def handle_analysis_start(ack, body, client, logger):
        """解析開始ボタンのハンドラー"""
        ack()
        
        payload = MetadataManager.extract_from_body(body)
        
        if not payload:
            client.chat_postMessage(
                channel=body["channel"]["id"],
                text="❌ 解析情報が見つかりません。CSVファイルを再アップロードしてください。"
            )
            return
        
        # ユーザーパラメータをpayloadから取得する想定 (モーダル等で設定された場合)
        # ここではダミーのパラメータを使用
        user_parameters = payload.get("user_parameters", {
            "measure": payload.get("csv_analysis", {}).get("suggested_analysis", {}).get("effect_type", "SMD"),
            "model": payload.get("csv_analysis", {}).get("suggested_analysis", {}).get("model_type", "random")
        })
        
        # 一時ディレクトリの準備
        job_id = payload.get('job_id', 'unknown_job')
        r_output_dir = get_r_output_dir(job_id)

        # CSVファイルもRがアクセスできるように一時保存する (file_urlからダウンロードして保存)
        # csv_handlerでダウンロードしたコンテンツをmetadata経由で渡すか、ここで再度ダウンロードするか検討
        # ここでは、payloadに file_url がある前提で再度ダウンロードして保存する
        # (より効率的なのはcsv_handlerで保存したパスをmetadataで渡すこと)
        
        # payloadから元のファイルIDとURLを取得
        original_file_id = payload.get("file_id")
        original_file_url = payload.get("file_url") # csv_handlerで保存したURL
        original_file_name = payload.get("csv_analysis", {}).get("original_filename", "data.csv") # Gemini分析結果からファイル名取得

        asyncio.create_task(run_analysis_async(
            payload=payload,
            user_parameters=user_parameters,
            channel_id=body["channel"]["id"],
            thread_ts=body["message"]["ts"],
            user_id=body["user"]["id"],
            client=client,
            logger=logger,
            r_output_dir=r_output_dir, # Rの出力先ディレクトリ
            original_file_url=original_file_url, # CSVファイルのURL
            original_file_name=original_file_name # CSVファイル名
        ))
        
        client.chat_postMessage(
            channel=body["channel"]["id"],
            thread_ts=body["message"]["ts"],
            text="🔄 解析を開始しました。完了まで少々お待ちください..."
        )

async def run_analysis_async(payload, user_parameters, channel_id, thread_ts, user_id, client, logger, r_output_dir, original_file_url, original_file_name):
    """メタ解析の非同期実行"""
    temp_csv_path = None
    try:
        # CSVファイルをダウンロードして一時保存
        if original_file_url:
            from utils.file_utils import download_slack_file_content_async # ここでインポート
            csv_bytes = await download_slack_file_content_async(original_file_url, client.token)
            temp_csv_path_str, temp_csv_path_obj = await save_content_to_temp_file(
                csv_bytes, payload["job_id"], original_filename=original_file_name
            )
            temp_csv_path = temp_csv_path_obj # Pathオブジェクトを後で使う
        else:
            logger.error("run_analysis_async: CSVファイルのURLがpayloadにありません。")
            raise ValueError("CSV file URL is missing.")

        r_executor = RAnalysisExecutor(r_output_dir=r_output_dir, csv_file_path=temp_csv_path, job_id=payload["job_id"])
        
        # data_summary を準備（CSVの基本情報）
        csv_analysis = payload.get("csv_analysis", {})
        
        # CSVの列情報を取得（Geminiの分析結果から）
        column_descriptions = csv_analysis.get("column_descriptions", {})
        csv_columns = list(column_descriptions.keys()) if column_descriptions else []
        
        # data_previewからも列名を取得（フォールバック）
        data_preview = csv_analysis.get("data_preview", [])
        if not csv_columns and data_preview:
            csv_columns = list(data_preview[0].keys()) if data_preview else []
        
        # デバッグログ追加
        logger.info(f"Debug - CSV column extraction: column_descriptions keys: {list(column_descriptions.keys()) if column_descriptions else 'None'}")
        logger.info(f"Debug - CSV column extraction: data_preview sample: {data_preview[0] if data_preview else 'None'}")
        logger.info(f"Debug - CSV column extraction: final csv_columns: {csv_columns}")
        
        data_summary = {
            "csv_file_path": str(temp_csv_path),
            "csv_analysis": csv_analysis,
            "detected_columns": csv_analysis.get("detected_columns", {}),
            "columns": csv_columns,  # 列情報を追加
            "file_info": {
                "filename": original_file_name,
                "job_id": payload["job_id"]
            }
        }
        
        analysis_result_from_r = await r_executor.execute_meta_analysis(
            analysis_params=user_parameters,
            data_summary=data_summary
        )
        
        # analysis_result_from_r["files"] は {"type": "path"} の辞書を想定
        files_to_upload_for_slack = []
        if analysis_result_from_r.get("success") and analysis_result_from_r.get("generated_plots_paths"):
            for plot_info in analysis_result_from_r.get("generated_plots_paths", []): # RExecutorからの戻り値に合わせる
                 files_to_upload_for_slack.append({"type": plot_info["label"], "path": plot_info["path"], "title": plot_info["label"]})
            if analysis_result_from_r.get("structured_summary_json_path"):
                files_to_upload_for_slack.append({
                    "type": "summary_json", 
                    "path": analysis_result_from_r["structured_summary_json_path"],
                    "title": f"summary_{payload['job_id']}.json"
                })
            if analysis_result_from_r.get("rdata_path"):
                 files_to_upload_for_slack.append({
                    "type": "rdata",
                    "path": analysis_result_from_r["rdata_path"],
                    "title": f"result_{payload['job_id']}.RData"
                })
            if analysis_result_from_r.get("r_script_path"):
                 files_to_upload_for_slack.append({
                    "type": "r_script",
                    "path": analysis_result_from_r["r_script_path"],
                    "title": f"run_meta_{payload['job_id']}.R"
                })


        files_uploaded_info = await upload_files_to_slack( # 実際の関数呼び出し
            files_to_upload=files_to_upload_for_slack,
            channel_id=channel_id,
            thread_ts=thread_ts,
            client=client,
            job_id=payload["job_id"]
        )
        
        # Rの実行結果からサマリーを取得 (structured_summary_content を使う)
        r_summary_for_metadata = {}
        if analysis_result_from_r.get("success") and analysis_result_from_r.get("structured_summary_content"):
            try:
                full_r_summary = json.loads(analysis_result_from_r["structured_summary_content"])
                
                # バージョン情報を含む完全なサマリーを保持し、レポート生成で使用する
                r_summary_for_metadata = full_r_summary.copy()
                
                # overall_analysisが存在する場合、そのフィールドをトップレベルに追加（後方互換性のため）
                # ただし、バージョン情報は上書きしない
                if "overall_analysis" in full_r_summary:
                    # バージョン情報を保持
                    version_info = {
                        'r_version': r_summary_for_metadata.get('r_version'),
                        'metafor_version': r_summary_for_metadata.get('metafor_version'),
                        'analysis_environment': r_summary_for_metadata.get('analysis_environment')
                    }
                    
                    r_summary_for_metadata.update(full_r_summary["overall_analysis"])
                    
                    # バージョン情報を復元
                    for key, value in version_info.items():
                        if value is not None:
                            r_summary_for_metadata[key] = value
                    
            except json.JSONDecodeError:
                logger.error("RからのJSONサマリーのパースに失敗しました。")
                r_summary_for_metadata = {"error": "Failed to parse R summary JSON"}


        completion_metadata = MetadataManager.create_metadata("analysis_complete", {
            "job_id": payload["job_id"],
            "result_summary": r_summary_for_metadata, # Rのサマリーを使用
            "uploaded_files": files_uploaded_info,
            "r_stdout": analysis_result_from_r.get("stdout", ""),
            "r_stderr": analysis_result_from_r.get("stderr", ""),
            "r_script_path": analysis_result_from_r.get("r_script_path", ""), # 参考用
            "stage": "awaiting_interpretation",
            "user_id": user_id,
            "original_file_id": payload.get("file_id"),
            "original_file_url": payload.get("file_url") # これは run_analysis_async に渡されたもの
        })
        
        # create_analysis_result_blocks に渡すデータ構造をRの出力に合わせる
        # RExecutorの戻り値の "summary" が create_analysis_result_blocks の期待する構造と異なる場合、ここで変換する
        # ここでは、r_summary_for_metadata をそのまま使えるように create_analysis_result_blocks 側を調整するか、
        # ここで期待される構造に整形する。
        # 今回は r_summary_for_metadata をそのまま渡し、create_analysis_result_blocks で対応すると仮定。
        # ただし、ログ表示のために analysis_result_from_r 全体も渡す。
        display_result_for_blocks = {
            "summary": r_summary_for_metadata,
            "r_log": analysis_result_from_r.get("stdout","") + "\n" + analysis_result_from_r.get("stderr","")
        }

        result_message = create_analysis_result_message(display_result_for_blocks)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=result_message,
            metadata=completion_metadata
        )
        
        # 解釈レポート生成を自動的に開始
        from handlers.report_handler import generate_report_async
        
        # report_handlerが期待するpayload構造を作成
        report_payload = {
            "job_id": payload["job_id"],
            "result_summary": r_summary_for_metadata,
            "stage": "awaiting_interpretation",
            "user_id": user_id,
            "original_file_id": payload.get("file_id"),
            "uploaded_files": files_uploaded_info,
            "r_stdout": analysis_result_from_r.get("stdout", ""),
            "r_stderr": analysis_result_from_r.get("stderr", "")
        }
        
        # レポート生成中メッセージを送信
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="📝 解釈レポートを生成中です..."
        )
        
        # 同期的にレポート生成を実行
        await generate_report_async(
            payload=report_payload,
            channel_id=channel_id,
            thread_ts=thread_ts,
            client=client,
            logger=logger
        )
        
    except Exception as e:
        logger.error(f"解析実行エラー: {e}")
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"❌ 解析中にエラーが発生しました: {str(e)}"
        )
    finally:
        # 一時ディレクトリのクリーンアップ
        if temp_csv_path and temp_csv_path.parent.exists(): # CSVを保存したディレクトリ
            await cleanup_temp_dir_async(temp_csv_path.parent)
        if r_output_dir.exists(): # Rの出力ディレクトリ
            await cleanup_temp_dir_async(r_output_dir)
        logger.info(f"解析完了後の一時ディレクトリクリーンアップ試行完了。")
