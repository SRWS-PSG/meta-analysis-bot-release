import asyncio # upload_files_to_slack のために追加
import os # upload_files_to_slack のために追加
import requests # upload_files_to_slack のために追加
import logging # upload_files_to_slack のために追加
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__) # upload_files_to_slack のために追加

def create_analysis_start_blocks(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """解析開始用のSlack Blocksを作成"""
    detected_cols = analysis_result.get("detected_columns", {})
    effect_candidates = detected_cols.get("effect_size_candidates", ["N/A"])
    variance_candidates = detected_cols.get("variance_candidates", ["N/A"])
    
    effect_col_display = effect_candidates[0] if effect_candidates and effect_candidates[0] else "N/A"
    variance_col_display = variance_candidates[0] if variance_candidates and variance_candidates[0] else "N/A"

    suggested_analysis = analysis_result.get("suggested_analysis", {})
    suggested_effect_type = suggested_analysis.get("effect_type_suggestion", "未検出")
    suggested_model_type = suggested_analysis.get("model_type_suggestion", "未検出")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*CSV分析結果:*\n"
                    f"• メタ解析への適合性: `{'適合' if analysis_result.get('is_suitable') else '不適合'}`\n"
                    f"• 理由: {analysis_result.get('reason', 'N/A')}\n"
                    f"• 推定される効果量列候補: `{effect_col_display}`\n"
                    f"• 推定される分散/SE列候補: `{variance_col_display}`\n"
                    f"• 推奨効果量タイプ: `{suggested_effect_type}`\n"
                    f"• 推奨モデルタイプ: `{suggested_model_type}`"
                )
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🚀 推奨設定で解析開始"},
                    "style": "primary",
                    "action_id": "start_analysis_with_defaults"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "⚙️ パラメータを設定して解析"},
                    "action_id": "configure_analysis_parameters"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": " キャンセル"},
                    "style": "danger",
                    "action_id": "cancel_analysis_request"
                }
            ]
        }
    ]
    if not analysis_result.get("is_suitable"):
        blocks[1]["elements"][0]["confirm"] = { 
            "title": {"type": "plain_text", "text": "解析不適合"},
            "text": {"type": "mrkdwn", "text": "このCSVはメタ解析に不適合と判断されました。解析を強行しますか？"},
            "confirm": {"type": "plain_text", "text": "強行する"},
            "deny": {"type": "plain_text", "text": "やめる"}
        }
        blocks[1]["elements"][1]["confirm"] = { 
             "title": {"type": "plain_text", "text": "解析不適合"},
            "text": {"type": "mrkdwn", "text": "このCSVはメタ解析に不適合と判断されました。パラメータ設定に進みますか？"},
            "confirm": {"type": "plain_text", "text": "進む"},
            "deny": {"type": "plain_text", "text": "やめる"}
        }
    return blocks

def create_unsuitable_csv_blocks(reason: str) -> List[Dict[str, Any]]:
    """メタ解析に適さないCSVの場合のSlack Blocksを作成"""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ **メタ解析に不適合なCSVファイル**\n理由: {reason}\n\n別のCSVファイルをアップロードするか、ファイルの内容を確認してください。"
            }
        }
    ]

def create_simple_parameter_selection_blocks(csv_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """モーダルではなくシンプルなメッセージでパラメータ選択用のBlocksを作成"""
    suggested_analysis = csv_analysis.get("suggested_analysis", {})
    suggested_effect_type = suggested_analysis.get("effect_type_suggestion", "OR")
    
    # 二値アウトカムの場合の効果量選択肢
    effect_size_options = [
        {"text": {"type": "plain_text", "text": "OR (オッズ比)"}, "value": "OR"},
        {"text": {"type": "plain_text", "text": "RR (リスク比)"}, "value": "RR"},
        {"text": {"type": "plain_text", "text": "RD (リスク差)"}, "value": "RD"},
        {"text": {"type": "plain_text", "text": "PETO (Petoオッズ比)"}, "value": "PETO"}
    ]
    
    # モデルタイプ選択肢
    model_options = [
        {"text": {"type": "plain_text", "text": "REML (推奨)"}, "value": "REML"},
        {"text": {"type": "plain_text", "text": "DL (DerSimonian-Laird)"}, "value": "DL"},
        {"text": {"type": "plain_text", "text": "FE (固定効果)"}, "value": "FE"}
    ]
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*効果量タイプを選択してください:*\n推奨: `{suggested_effect_type}`"
            },
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "効果量を選択"},
                "action_id": "select_effect_size",
                "initial_option": next((opt for opt in effect_size_options if opt["value"] == suggested_effect_type), effect_size_options[0]),
                "options": effect_size_options
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*統計モデルを選択してください:*"
            },
            "accessory": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "モデルを選択"},
                "action_id": "select_model_type",
                "initial_option": model_options[0],  # REMLをデフォルト
                "options": model_options
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🚀 解析開始"},
                    "style": "primary",
                    "action_id": "start_analysis_with_selected_params"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ キャンセル"},
                    "action_id": "cancel_parameter_selection"
                }
            ]
        }
    ]

def create_analysis_result_blocks(analysis_result_from_r: Dict[str, Any]) -> List[Dict[str, Any]]:
    """解析結果表示用のSlack Blocksを作成"""
    summary = analysis_result_from_r.get("summary", {})
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*メタ解析結果サマリー:*\n"
                    f"• 統合効果量: `{summary.get('pooled_effect', summary.get('estimate', 'N/A'))}`\n" # estimate も考慮
                    f"• 95%信頼区間: `{summary.get('ci_lower', summary.get('ci_lb', 'N/A'))}` - `{summary.get('ci_upper', summary.get('ci_ub', 'N/A'))}`\n"
                    f"• I²統計量: `{summary.get('i2', summary.get('I2', 'N/A'))}%`\n" # 大文字I2も考慮
                    f"• 解析ログ抜粋: ```{analysis_result_from_r.get('r_log', 'ログなし')[:200]}...```"
                )
            }
        }
    ]
            
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📝 解釈レポート生成"},
                "style": "primary",
                "action_id": "generate_interpretation"
            },
        ]
    })
    return blocks

def create_report_blocks(interpretation: Dict[str, Any]) -> List[Dict[str, Any]]:
    """レポート表示用のSlack Blocksを作成"""
    methods_text = interpretation.get('methods_section', 'N/A')
    results_text = interpretation.get('results_section', 'N/A')
    summary_text = interpretation.get('summary', 'N/A')
    discussion_points = interpretation.get('discussion_points', [])
    limitations = interpretation.get('limitations', [])

    discussion_md = "\n".join([f"• {point}" for point in discussion_points])
    limitations_md = "\n".join([f"• {limitation}" for limitation in limitations])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "解釈レポート",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*要約:*\n{summary_text}"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*方法セクション概要:*\n{methods_text[:1000]}{'...' if len(methods_text) > 1000 else ''}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*結果セクション概要:*\n{results_text[:1000]}{'...' if len(results_text) > 1000 else ''}"
            }
        }
    ]
    if discussion_points:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*考察のポイント:*\n{discussion_md}"
            }
        })
    if limitations:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*本解析の限界:*\n{limitations_md}"
            }
        })
    
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "このレポートはAIによって生成されました。内容は参考情報としてご利用ください。"
            }
        ]
    })
    return blocks

def create_parameter_modal_blocks(csv_analysis_result: Dict[str, Any], initial_params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """解析パラメータ設定モーダル用のSlack Blocksを作成"""
    if initial_params is None:
        initial_params = {}

    all_csv_columns = list(csv_analysis_result.get("column_descriptions", {}).keys())
    column_options = [{"text": {"type": "plain_text", "text": col}, "value": col} for col in all_csv_columns]
    if not column_options:
        column_options.append({"text": {"type": "plain_text", "text": "列が検出されませんでした"}, "value": "no_columns_detected"})

    effect_type_options = [
        {"text": {"type": "plain_text", "text": "Standardized Mean Difference (SMD)"}, "value": "SMD"},
        {"text": {"type": "plain_text", "text": "Mean Difference (MD)"}, "value": "MD"},
        {"text": {"type": "plain_text", "text": "Odds Ratio (OR)"}, "value": "OR"},
        {"text": {"type": "plain_text", "text": "Risk Ratio (RR)"}, "value": "RR"},
        {"text": {"type": "plain_text", "text": "Incidence Rate Ratio (IRR)"}, "value": "IRR"},
        {"text": {"type": "plain_text", "text": "Proportion (PLO)"}, "value": "PLO"},
        {"text": {"type": "plain_text", "text": "Pre-calculated (yi, vi)"}, "value": "PRE"},
    ]
    model_type_options = [
        {"text": {"type": "plain_text", "text": "Random-effects model (REML)"}, "value": "REML"},
        {"text": {"type": "plain_text", "text": "Fixed-effect model (FE)"}, "value": "FE"},
        {"text": {"type": "plain_text", "text": "DerSimonian-Laird (DL)"}, "value": "DL"},
    ]

    initial_effect_type = initial_params.get("measure", csv_analysis_result.get("suggested_analysis", {}).get("effect_type_suggestion", "SMD"))
    initial_model_type = initial_params.get("model", csv_analysis_result.get("suggested_analysis", {}).get("model_type_suggestion", "REML"))
    
    selected_effect_option = next((opt for opt in effect_type_options if opt["value"] == initial_effect_type), None)
    selected_model_option = next((opt for opt in model_type_options if opt["value"] == initial_model_type), None)

    blocks = [
        {
            "type": "input",
            "block_id": "effect_type_block",
            "label": {"type": "plain_text", "text": "効果量の種類"},
            "element": {
                "type": "static_select",
                "action_id": "effect_type_select",
                "placeholder": {"type": "plain_text", "text": "効果量を選択"},
                "options": effect_type_options,
                "initial_option": selected_effect_option
            }
        },
        {
            "type": "input",
            "block_id": "model_type_block",
            "label": {"type": "plain_text", "text": "解析モデル"},
            "element": {
                "type": "static_select",
                "action_id": "model_type_select",
                "placeholder": {"type": "plain_text", "text": "モデルを選択"},
                "options": model_type_options,
                "initial_option": selected_model_option
            }
        },
        {
            "type": "input",
            "block_id": "study_id_col_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "研究ID列 (Study ID column)"},
            "element": {
                "type": "static_select",
                "action_id": "study_id_col_select",
                "placeholder": {"type": "plain_text", "text": "研究ID列を選択"},
                "options": column_options,
                "initial_option": next((opt for opt in column_options if opt["value"] == initial_params.get("study_id_col")), None)
            }
        },
        # 以下、効果量の種類に応じて表示する列マッピング項目を動的に変更するのが理想
        # ここでは主要なものをコメントとして残す
        # { "type": "input", "block_id": "ai_col_block", "optional": True, "label": {"type": "plain_text", "text": "治療群イベント数 (ai)"}, ... },
        # { "type": "input", "block_id": "n1i_col_block", "optional": True, "label": {"type": "plain_text", "text": "治療群サンプルサイズ (n1i)"}, ... },
        # { "type": "input", "block_id": "m1i_col_block", "optional": True, "label": {"type": "plain_text", "text": "治療群平均 (m1i)"}, ... },
        # { "type": "input", "block_id": "sd1i_col_block", "optional": True, "label": {"type": "plain_text", "text": "治療群標準偏差 (sd1i)"}, ... },
        # { "type": "input", "block_id": "yi_col_block", "optional": True, "label": {"type": "plain_text", "text": "効果量 (yi)"}, ... },
        # { "type": "input", "block_id": "vi_col_block", "optional": True, "label": {"type": "plain_text", "text": "分散 (vi)"}, ... },
        {
            "type": "input",
            "block_id": "subgroup_cols_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "サブグループ解析に使用する列 (複数選択可)"},
            "element": {
                "type": "multi_static_select",
                "action_id": "subgroup_cols_select",
                "placeholder": {"type": "plain_text", "text": "サブグループ列を選択"},
                "options": column_options,
                "initial_options": [opt for opt in column_options if opt["value"] in initial_params.get("subgroup_columns", [])]
            }
        },
        {
            "type": "input",
            "block_id": "moderator_cols_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "メタ回帰に使用するモデレーター列 (複数選択可)"},
            "element": {
                "type": "multi_static_select",
                "action_id": "moderator_cols_select",
                "placeholder": {"type": "plain_text", "text": "モデレーター列を選択"},
                "options": column_options,
                "initial_options": [opt for opt in column_options if opt["value"] in initial_params.get("moderator_columns", [])]
            }
        }
    ]
    return blocks

async def upload_files_to_slack(files_to_upload: List[Dict[str, str]], channel_id: str, thread_ts: Optional[str], client: Any, job_id: str) -> List[Dict[str, Any]]:
    """
    指定されたファイルのリストをSlackにアップロードする。
    files_to_upload: [{"type": "file_type", "path": "/path/to/file", "title": "File Title"}, ...]
    """
    uploaded_file_infos = []
    if not files_to_upload:
        return uploaded_file_infos

    for file_info in files_to_upload:
        file_path = file_info.get("path")
        file_title = file_info.get("title", os.path.basename(file_path) if file_path else "Untitled")
        file_type_label = file_info.get("type", "file") # 例: forest_plot, summary_json

        if not file_path or not os.path.exists(file_path):
            logger.warning(f"ファイルが見つからないためアップロードをスキップ: {file_path} (Job ID: {job_id})")
            continue

        try:
            # Slack SDKの files_upload_v2 を使用
            response = await asyncio.to_thread(
                client.files_upload_v2,
                channel=channel_id,
                filepath=file_path,
                title=file_title,
                initial_comment=f"{file_title} ({job_id})",
                thread_ts=thread_ts
            )
            if response.get("ok") and response.get("file"):
                slack_file_info = response["file"]
                uploaded_file_infos.append({
                    "type": file_type_label,
                    "id": slack_file_info.get("id"),
                    "name": slack_file_info.get("name"),
                    "url_private_download": slack_file_info.get("url_private_download"),
                    "permalink": slack_file_info.get("permalink"),
                    "title": file_title # 元のタイトルも保持
                })
                logger.info(f"ファイル '{file_title}' をSlackにアップロード成功 (File ID: {slack_file_info.get('id')}, Job ID: {job_id})")
            else:
                logger.error(f"ファイル '{file_title}' のSlackへのアップロードに失敗。Response: {response} (Job ID: {job_id})")
        except Exception as e:
            logger.error(f"ファイル '{file_title}' のSlackへのアップロード中に例外発生: {e} (Job ID: {job_id})")
            # 個々のファイルアップロード失敗は全体を止めない
    
    return uploaded_file_infos
