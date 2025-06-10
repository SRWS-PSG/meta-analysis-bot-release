import asyncio # upload_files_to_slack のために追加
import os # upload_files_to_slack のために追加
import requests # upload_files_to_slack のために追加
import logging # upload_files_to_slack のために追加
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__) # upload_files_to_slack のために追加

def create_analysis_start_message(analysis_result: Dict[str, Any], initial_params: Optional[Dict[str, Any]] = None) -> str:
    """CSV分析結果を自然言語メッセージとして作成（Button UI削除）"""
    detected_cols = analysis_result.get("detected_columns", {})
    
    # 各種データタイプの列候補を取得
    effect_candidates = detected_cols.get("effect_size_candidates", [])
    variance_candidates = detected_cols.get("variance_candidates", [])
    binary_intervention_events = detected_cols.get("binary_intervention_events", [])
    binary_control_events = detected_cols.get("binary_control_events", [])
    continuous_intervention_mean = detected_cols.get("continuous_intervention_mean", [])
    continuous_control_mean = detected_cols.get("continuous_control_mean", [])
    proportion_events = detected_cols.get("proportion_events", [])
    proportion_total = detected_cols.get("proportion_total", [])
    study_id_candidates = detected_cols.get("study_id_candidates", [])
    subgroup_candidates = detected_cols.get("subgroup_candidates", [])
    moderator_candidates = detected_cols.get("moderator_candidates", [])
    
    # 表示用の候補を構築
    data_type_info = []
    
    # 事前計算済み効果量データ
    if effect_candidates:
        data_type_info.append(f"事前計算済み効果量: {', '.join(effect_candidates[:2])}")
    
    # 二値アウトカムデータ
    binary_candidates = []
    if binary_intervention_events:
        binary_candidates.extend(binary_intervention_events[:1])
    if binary_control_events:
        binary_candidates.extend(binary_control_events[:1])
    
    # 総数列も含める
    binary_total_info = []
    binary_intervention_total = detected_cols.get("binary_intervention_total", [])
    binary_control_total = detected_cols.get("binary_control_total", [])
    if binary_intervention_total:
        binary_total_info.extend(binary_intervention_total[:1])
    if binary_control_total:
        binary_total_info.extend(binary_control_total[:1])
    
    if binary_candidates:
        display_text = f"二値アウトカム: {', '.join(binary_candidates)}"
        if binary_total_info:
            display_text += f" (総数: {', '.join(binary_total_info)})"
        data_type_info.append(display_text)
    
    # 連続アウトカムデータ
    continuous_candidates = []
    if continuous_intervention_mean:
        continuous_candidates.extend(continuous_intervention_mean[:1])
    if continuous_control_mean:
        continuous_candidates.extend(continuous_control_mean[:1])
    if continuous_candidates:
        data_type_info.append(f"連続アウトカム: {', '.join(continuous_candidates)}")
    
    # 単一群比率データ
    proportion_candidates = []
    if proportion_events:
        proportion_candidates.extend(proportion_events[:1])
    if proportion_total:
        proportion_candidates.extend(proportion_total[:1])
    if proportion_candidates:
        data_type_info.append(f"単一群比率: {', '.join(proportion_candidates)}")
    
    # 表示用文字列の作成
    effect_display = "; ".join(data_type_info) if data_type_info else "検出されませんでした"
    variance_display = ", ".join(variance_candidates[:3]) if variance_candidates else "検出されませんでした"
    study_id_display = ", ".join(study_id_candidates[:2]) if study_id_candidates else "検出されませんでした"
    subgroup_display = ", ".join(subgroup_candidates[:5]) if subgroup_candidates else "検出されませんでした"
    moderator_display = ", ".join(moderator_candidates[:5]) if moderator_candidates else "検出されませんでした"

    suggested_analysis = analysis_result.get("suggested_analysis", {})
    suggested_effect_type = suggested_analysis.get("effect_type_suggestion", "未検出")
    suggested_model_type = suggested_analysis.get("model_type_suggestion", "未検出")
    
    # 配列として返される場合の処理
    if isinstance(suggested_effect_type, list):
        suggested_effect_type = ", ".join(suggested_effect_type) if suggested_effect_type else "未検出"
    if isinstance(suggested_model_type, list):
        suggested_model_type = ", ".join(suggested_model_type) if suggested_model_type else "未検出"
    
    # 研究数を取得（Geminiが返すnum_studiesフィールドを優先）
    num_studies = analysis_result.get("num_studies", "不明")
    if num_studies == "不明":
        # フォールバック: reasonから抽出を試みる
        reason = analysis_result.get("reason", "")
        import re
        study_count_match = re.search(r'(\d+)件?の?研究', reason)
        if study_count_match:
            num_studies = study_count_match.group(1)
        else:
            data_preview = analysis_result.get("data_preview", [])
            num_studies = f"{len(data_preview)}+ (サンプル表示)" if data_preview else "不明"
    
    # 初期パラメータの表示
    auto_detected_params = ""
    if initial_params:
        auto_params = []
        if initial_params.get("effect_size"):
            auto_params.append(f"効果量: {initial_params['effect_size']}")
        if initial_params.get("model_type"):
            auto_params.append(f"モデル: {initial_params['model_type']}")
        if initial_params.get("study_column"):
            auto_params.append(f"研究ID列: {initial_params['study_column']}")
        
        if auto_params:
            auto_detected_params = f"\n\n**🤖 自動検出済みパラメータ:**\n• " + "\n• ".join(auto_params)
    
    # 事前計算済み効果量として検出された場合の確認メッセージ
    confirmation_message = ""
    if effect_candidates and not binary_candidates and not continuous_candidates:
        # 事前計算済み効果量のみが検出された場合
        confirmation_message = f"\n\n**❓ 確認事項:**\n検出された列 ({', '.join(effect_candidates[:2])}) は事前計算済みの効果量でしょうか？\n• はい → そのまま解析を続行します\n• いいえ → 二値アウトカム（OR/RR等）として扱います"
    
    message = f"""📊 **CSVファイルを分析しました！**

**データセット概要:**
• 研究数: {num_studies}件
• 検出データ: {effect_display}
• 分散/SE候補列: {variance_display}
• 研究ID候補列: {study_id_display}
• サブグループ候補列: {subgroup_display}
• メタ回帰候補列: {moderator_display}
• 推奨効果量: {suggested_effect_type}
• 推奨モデル: {suggested_model_type}{auto_detected_params}{confirmation_message}

**解析パラメータを教えてください。**

例：
• 「オッズ比でランダム効果モデルを使って解析して」
• 「SMDでREML法を使って、地域別のサブグループ解析も行って」
• 「このまま解析開始」（自動検出済みパラメータを使用）

どのような解析をご希望ですか？"""

    return message

def create_unsuitable_csv_message(reason: str) -> str:
    """メタ解析に適さないCSVの場合のメッセージを作成"""
    return f"""❌ **メタ解析に不適合なCSVファイル**

理由: {reason}

別のCSVファイルをアップロードするか、ファイルの内容を確認してください。

必要な列の例：
• 効果量とその標準誤差
• 二値アウトカムの場合：イベント数とサンプルサイズ
• 連続アウトカムの場合：平均値、標準偏差、サンプルサイズ

ご不明な点があれば、サンプルデータをお送りください。"""

# Button UIを削除し、自然言語対話に統一
# create_simple_parameter_selection_blocksは削除（CLAUDE.mdの要件に従い自然言語対話のみ）

def create_analysis_result_message(analysis_result_from_r: Dict[str, Any]) -> str:
    """解析結果を自然言語メッセージとして作成"""
    summary = analysis_result_from_r.get("summary", {})
    
    # R script generates: estimate, ci_lb, ci_ub, I2, k
    pooled_effect = summary.get('estimate', 'N/A')
    ci_lower = summary.get('ci_lb', 'N/A')
    ci_upper = summary.get('ci_ub', 'N/A') 
    i2_value = summary.get('I2', 'N/A')
    num_studies = summary.get('k', 'N/A')
    
    # Format numeric values
    if isinstance(pooled_effect, (int, float)):
        pooled_effect = f"{pooled_effect:.3f}"
    if isinstance(ci_lower, (int, float)):
        ci_lower = f"{ci_lower:.3f}"
    if isinstance(ci_upper, (int, float)):
        ci_upper = f"{ci_upper:.3f}"
    if isinstance(i2_value, (int, float)):
        i2_value = f"{i2_value:.1f}"
    
    # サブグループ解析結果を追加
    subgroup_text = ""
    for key, value in summary.items():
        if key.startswith('subgroup_moderation_test_'):
            subgroup_var = key.replace('subgroup_moderation_test_', '')
            if isinstance(value, dict):
                qm_p = value.get('QMp', 'N/A')
                if isinstance(qm_p, (int, float)):
                    qm_p = f"{qm_p:.3f}"
                subgroup_text += f"\n• {subgroup_var}別サブグループ解析: p={qm_p}"
        
        elif key.startswith('subgroup_analyses_'):
            subgroup_var = key.replace('subgroup_analyses_', '')
            if isinstance(value, dict):
                subgroup_text += f"\n\n**【{subgroup_var}別サブグループ結果】**"
                for level_name, level_result in value.items():
                    if isinstance(level_result, dict):
                        sg_estimate = level_result.get('estimate', 'N/A')
                        sg_ci_lb = level_result.get('ci_lb', 'N/A')
                        sg_ci_ub = level_result.get('ci_ub', 'N/A')
                        sg_k = level_result.get('k', 'N/A')
                        
                        if isinstance(sg_estimate, (int, float)):
                            sg_estimate = f"{sg_estimate:.3f}"
                        if isinstance(sg_ci_lb, (int, float)):
                            sg_ci_lb = f"{sg_ci_lb:.3f}"
                        if isinstance(sg_ci_ub, (int, float)):
                            sg_ci_ub = f"{sg_ci_ub:.3f}"
                        
                        subgroup_text += f"\n• {level_name}: 効果量={sg_estimate} [{sg_ci_lb}, {sg_ci_ub}] (k={sg_k})"
    
    # ゼロセル解析結果を追加
    zero_cell_text = ""
    zero_cells_summary = summary.get('zero_cells_summary')
    
    # DEBUG: Log summary structure
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG: Full summary keys: {list(summary.keys())}")
    logger.info(f"DEBUG: zero_cells_summary: {zero_cells_summary}")
    
    if zero_cells_summary:
        studies_with_zero = zero_cells_summary.get('studies_with_zero_cells', 0)
        logger.info(f"DEBUG: studies_with_zero: {studies_with_zero}")
        if studies_with_zero > 0:
            double_zero = zero_cells_summary.get('double_zero_studies', 0)
            intervention_zero = zero_cells_summary.get('intervention_zero_studies', 0)
            control_zero = zero_cells_summary.get('control_zero_studies', 0)
            main_method = summary.get('main_analysis_method', 'N/A')
            
            zero_cell_text = f"\n\n**【ゼロセル対応】**"
            zero_cell_text += f"\n• ゼロセルを含む研究数: {studies_with_zero}件"
            if double_zero > 0:
                zero_cell_text += f"\n• 両群ゼロ研究数: {double_zero}件"
            if intervention_zero > 0:
                zero_cell_text += f"\n• 介入群ゼロ研究数: {intervention_zero}件"
            if control_zero > 0:
                zero_cell_text += f"\n• 対照群ゼロ研究数: {control_zero}件"
            zero_cell_text += f"\n• 主解析手法: {main_method}"
            
            # 感度解析結果を追加
            sensitivity_results = summary.get('sensitivity_analysis', {})
            if sensitivity_results:
                zero_cell_text += f"\n• 感度解析も実行（詳細はRスクリプト参照）"

    # メタ回帰結果を追加
    meta_regression_text = ""
    meta_regression_results = summary.get('meta_regression_results')
    if meta_regression_results:
        qm_p = meta_regression_results.get('QMp', 'N/A')
        if isinstance(qm_p, (int, float)):
            qm_p = f"{qm_p:.3f}"
        meta_regression_text = f"\n• メタ回帰分析: p={qm_p}"
        
        moderators = meta_regression_results.get('moderators', {})
        if moderators:
            meta_regression_text += f"\n\n**【メタ回帰結果】**"
            for mod_name, mod_result in moderators.items():
                if isinstance(mod_result, dict):
                    mod_estimate = mod_result.get('estimate', 'N/A')
                    mod_pval = mod_result.get('pval', 'N/A')
                    
                    if isinstance(mod_estimate, (int, float)):
                        mod_estimate = f"{mod_estimate:.3f}"
                    if isinstance(mod_pval, (int, float)):
                        mod_pval = f"{mod_pval:.3f}"
                    
                    meta_regression_text += f"\n• {mod_name}: 係数={mod_estimate}, p={mod_pval}"
    
    message = f"""📊 **メタ解析が完了しました！**

**【解析結果サマリー】**
• 統合効果量: {pooled_effect}
• 95%信頼区間: {ci_lower} - {ci_upper}
• 異質性: I²={i2_value}%
• 研究数: {num_studies}件{zero_cell_text}{subgroup_text}{meta_regression_text}

ファイルが添付されています：
• フォレストプロット
• Rスクリプト
• 解析結果データ

解釈レポートを生成中です..."""
    
    return message

def create_report_message(interpretation: Dict[str, Any]) -> str:
    """解釈レポートを自然言語メッセージとして作成（統計解析とGRADE準拠結果のみ）"""
    methods_text = interpretation.get('methods_section', 'N/A')
    results_text = interpretation.get('results_section', 'N/A')
    summary_text = interpretation.get('summary', 'N/A')

    message = f"""📄 **解釈レポート（学術論文形式）**

**【要約】**
{summary_text}

**【統計解析 / Statistical Analysis】**
{methods_text[:1200]}{'...' if len(methods_text) > 1200 else ''}

**【結果 / Results】**
{results_text[:1200]}{'...' if len(results_text) > 1200 else ''}

---
*このレポートはAIによって生成されました。統計解析結果のみを記載しています。*"""
    
    return message

# create_parameter_modal_blocksも削除（自然言語対話に統一）

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
            # Slack SDKの files_upload_v2 を使用（fileパラメータで指定）
            response = await asyncio.to_thread(
                client.files_upload_v2,
                channel=channel_id,
                file=file_path,
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

def upload_file_to_slack(client, file_path, channel_id, title, thread_ts=None):
    """新しいfiles.getUploadURLExternal APIを使用してファイルをSlackにアップロードする"""
    try:
        get_url_response = client.files_getUploadURLExternal(
            filename=os.path.basename(file_path),
            length=os.path.getsize(file_path),
        )
    except Exception as e:
        logger.error(f"files.getUploadURLExternalの呼び出し中にエラー: {e}")
        raise

    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    try:
        upload_response = requests.post(
            get_url_response["upload_url"],
            data=file_content,
            headers={"Content-Type": "application/octet-stream"},
            allow_redirects=True
        )
        upload_response.raise_for_status()
    except Exception as e:
        logger.error(f"ファイルコンテンツのアップロード中にエラー: {e}")
        raise
        
    files_data = [{
        "id": get_url_response["file_id"],
        "title": title,
    }]

    try:
        complete_response = client.files_completeUploadExternal(
            files=files_data,
            channel_id=channel_id,
            thread_ts=thread_ts,
            initial_comment=f"{title}をアップロードしました。"
        )
        return complete_response
    except Exception as e:
        logger.error(f"files.completeUploadExternalの呼び出し中にエラー: {e}")
        # Attempt to delete the file if completion fails to avoid orphaned uploads
        try:
            client.files_delete(file=get_url_response["file_id"])
            logger.info(f"アップロード完了失敗後、ファイル {get_url_response['file_id']} を削除しました。")
        except Exception as delete_e:
            logger.error(f"アップロード完了失敗後のファイル削除中にエラー: {delete_e}")
        raise
