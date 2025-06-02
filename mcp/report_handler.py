"""
Report Handlerモジュール

メタアナリシス結果のレポート生成とSlackへのアップロード機能を提供します。
"""
import logging
import json
import time
import os # For os.path.exists
from pathlib import Path

from mcp.gemini_utils import generate_academic_writing_suggestion

logger = logging.getLogger(__name__)

class ReportHandler:
    def __init__(self, context_manager, app_client):
        self.context_manager = context_manager
        self.app_client = app_client # Slack app client for uploading files

    def handle_report_generation_and_upload(self, result, channel_id, thread_ts, client, context):
        """
        英語論文形式のMethodsとResultsセクションを生成してSlackに投稿する
        resultは run_meta_analysis からの返り値。
        """
        preferences = context.get("analysis_state", {}).get("preferences", {})

        if not result.get("success"):
            logger.info("メタ解析が失敗したため、レポート生成は開始されません。")
            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="メタアナリシスの主要な処理が完了しましたが、分析自体に失敗したためレポートは生成されません。")
            context["dialog_state"] = {"type": "post_analysis", "state": "analysis_failed_no_report"}
            self.context_manager.save_context(thread_ts, context, channel_id)
            return

        # structured_summary_content (JSON文字列) を確認
        summary_json_content_str = result.get("structured_summary_content")

        summary_for_gemini = None

        if "processed_rdata_json" in context and context["processed_rdata_json"] is not None:
            summary_for_gemini = context["processed_rdata_json"]
            logger.info("Using processed_rdata_json from context for report generation.")
        elif summary_json_content_str:
            try:
                summary_for_gemini = json.loads(summary_json_content_str)
                logger.info("Using structured_summary_content string from result for report generation.")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse structured_summary_content string: {e}")
        
        if summary_for_gemini is None:
            logger.warning("No valid summary data (processed_rdata_json or string content) found for report generation.")
            client.chat_postMessage(
                channel=channel_id, 
                thread_ts=thread_ts, 
                text="レポート生成に必要な分析結果データが見つかりませんでした。メタアナリシスの主要処理は完了しています。(Error code: RPH001)"
            )
            context["dialog_state"] = {"type": "post_analysis", "state": "missing_summary_for_report"}
            self.context_manager.save_context(thread_ts, context, channel_id)
            return
        
        report_progress_ts = None
        try:
            try:
                report_progress_response = client.chat_postMessage(
                    channel=channel_id, thread_ts=thread_ts, text="英語論文形式のレポートを生成中です。少々お待ちください..."
                )
                report_progress_ts = report_progress_response.get("ts")
            except Exception as e: logger.error(f"Failed to post report generation progress message: {e}")

            academic_writing = generate_academic_writing_suggestion(summary_for_gemini)
            
            if report_progress_ts:
                try: client.chat_delete(channel=channel_id, ts=report_progress_ts)
                except Exception as e: logger.error(f"Failed to delete report progress message: {e}")
            
            if academic_writing:
                completion_message = "英語論文形式のレポートの生成が完了しました。結果を投稿します..."
                # Post new message instead of updating, as original might be deleted
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=completion_message)

                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="📝 **メタアナリシス結果レポート（英語論文形式）**")
                
                max_message_length = 3000
                messages = [academic_writing[i:i + max_message_length] for i in range(0, len(academic_writing), max_message_length)]
                
                for message_part in messages: # Renamed to avoid conflict
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=message_part)
                    time.sleep(1)

                # 感度分析結果の表示
                sensitivity_data = summary_for_gemini.get("sensitivity_analysis")
                if sensitivity_data:
                    effect_measure = preferences.get("measure", "効果量") # デフォルトは「効果量」
                    # 効果量が対数スケールの場合のexp変換を考慮 (OR, RR, HRなど)
                    apply_exp_transform_report = effect_measure in ["OR", "RR", "HR", "IRR", "PLO", "IR"]

                    full_est_val = sensitivity_data.get('full_estimate')
                    full_ci_lb_val = sensitivity_data.get('full_ci_lb')
                    full_ci_ub_val = sensitivity_data.get('full_ci_ub')
                    sens_est_val = sensitivity_data.get('sensitivity_estimate')
                    sens_ci_lb_val = sensitivity_data.get('sensitivity_ci_lb')
                    sens_ci_ub_val = sensitivity_data.get('sensitivity_ci_ub')

                    full_display = "N/A"
                    sens_display = "N/A"

                    if all(v is not None for v in [full_est_val, full_ci_lb_val, full_ci_ub_val]):
                        if apply_exp_transform_report:
                            full_display = f"{effect_measure} = {json.dumps(full_est_val) if not isinstance(full_est_val, (int, float)) else f'{full_est_val:.2f}' if isinstance(full_est_val, float) else full_est_val} [{json.dumps(full_ci_lb_val) if not isinstance(full_ci_lb_val, (int, float)) else f'{full_ci_lb_val:.2f}' if isinstance(full_ci_lb_val, float) else full_ci_lb_val}, {json.dumps(full_ci_ub_val) if not isinstance(full_ci_ub_val, (int, float)) else f'{full_ci_ub_val:.2f}' if isinstance(full_ci_ub_val, float) else full_ci_ub_val}]"
                            full_display = f"{effect_measure} = {json.dumps(full_est_val) if not isinstance(full_est_val, (int, float)) else f'{full_est_val:.2f}' if isinstance(full_est_val, float) else full_est_val} [{json.dumps(full_ci_lb_val) if not isinstance(full_ci_lb_val, (int, float)) else f'{full_ci_lb_val:.2f}' if isinstance(full_ci_lb_val, float) else full_ci_lb_val}, {json.dumps(full_ci_ub_val) if not isinstance(full_ci_ub_val, (int, float)) else f'{full_ci_ub_val:.2f}' if isinstance(full_ci_ub_val, float) else full_ci_ub_val}]"
                            full_display = f"{effect_measure} = {f'{float(full_est_val):.2f}' if isinstance(full_est_val, (int, float)) else json.dumps(full_est_val)} [{f'{float(full_ci_lb_val):.2f}' if isinstance(full_ci_lb_val, (int, float)) else json.dumps(full_ci_lb_val)}, {f'{float(full_ci_ub_val):.2f}' if isinstance(full_ci_ub_val, (int, float)) else json.dumps(full_ci_ub_val)}]"
                        else:
                            full_display = f"{effect_measure} = {f'{float(full_est_val):.2f}' if isinstance(full_est_val, (int, float)) else json.dumps(full_est_val)} [{f'{float(full_ci_lb_val):.2f}' if isinstance(full_ci_lb_val, (int, float)) else json.dumps(full_ci_lb_val)}, {f'{float(full_ci_ub_val):.2f}' if isinstance(full_ci_ub_val, (int, float)) else json.dumps(full_ci_ub_val)}]"
                    
                    if all(v is not None for v in [sens_est_val, sens_ci_lb_val, sens_ci_ub_val]):
                        if apply_exp_transform_report:
                            sens_display = f"{effect_measure} = {f'{float(sens_est_val):.2f}' if isinstance(sens_est_val, (int, float)) else json.dumps(sens_est_val)} [{f'{float(sens_ci_lb_val):.2f}' if isinstance(sens_ci_lb_val, (int, float)) else json.dumps(sens_ci_lb_val)}, {f'{float(sens_ci_ub_val):.2f}' if isinstance(sens_ci_ub_val, (int, float)) else json.dumps(sens_ci_ub_val)}]"
                        else:
                            sens_display = f"{effect_measure} = {f'{float(sens_est_val):.2f}' if isinstance(sens_est_val, (int, float)) else json.dumps(sens_est_val)} [{f'{float(sens_ci_lb_val):.2f}' if isinstance(sens_ci_lb_val, (int, float)) else json.dumps(sens_ci_lb_val)}, {f'{float(sens_ci_ub_val):.2f}' if isinstance(sens_ci_ub_val, (int, float)) else json.dumps(sens_ci_ub_val)}]"

                    n_included = sensitivity_data.get('n_included', 0)
                    n_total = sensitivity_data.get('n_total', 0)
                    percentage_included = (n_included / n_total * 100) if n_total > 0 else 0

                    sensitivity_text = f"""
📊 **感度分析結果**
変数: {sensitivity_data.get('variable', 'N/A')} を {sensitivity_data.get('limited_to', 'N/A')} に限定
- 対象研究数: {n_included}/{n_total}件 ({percentage_included:.1f}%)
- 全体の効果推定値: {full_display}
- 限定後の効果推定値: {sens_display}
"""
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=sensitivity_text)
                    time.sleep(1)

                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="✅ メタアナリシスの分析とレポート生成が完了しました。ハルシネーションの可能性に注意してご参照ください。")
                logger.info("英語論文形式のレポートと感度分析結果をSlackに投稿しました。")
            else:
                error_message = "レポート生成中にエラーが発生しました。メタアナリシスの主要処理は完了しています。"
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_message)
                logger.error("generate_academic_writing_suggestionがNoneを返しました。")
            
            context["dialog_state"] = {"type": "post_analysis", "state": "completed_with_report" if academic_writing else "report_generation_failed"}
            self.context_manager.save_context(thread_ts, context, channel_id)
            
        except Exception as e:
            logger.error(f"レポート生成中にエラーが発生しました: {e}", exc_info=True)
            error_message_text = f"レポート生成処理中にエラーが発生しました: {str(e)}\nメタアナリシスの主要処理は完了しています。"
            if report_progress_ts: # Try to update if ts exists
                try: client.chat_update(channel=channel_id, ts=report_progress_ts, text=error_message_text)
                except: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_message_text) # Fallback
            else: client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=error_message_text)

            context["dialog_state"] = {"type": "post_analysis", "state": "report_generation_error"}
            self.context_manager.save_context(thread_ts, context, channel_id)
