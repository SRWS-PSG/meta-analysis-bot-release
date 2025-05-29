"""
Parameter Collectorモジュール

ユーザー入力から分析パラメータを収集し、検証する機能を提供します。
"""
import logging
import json
import time # 追加
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd # pandas をインポート

from mcp.gemini_utils import extract_parameters_from_user_input
from mcp.dialog_state_manager import DialogStateManager # Assuming DialogStateManager is in its own file

logger = logging.getLogger(__name__)

class ParameterCollector:
    # Constants for parameter collection
    REQUIRED_PARAMS_DEFINITION = {
        "effect_size": None,  # OR, RR, HR, proportion, SMD, MD, COR, yi
        "model_type": None,   # fixed, random
    }
    OPTIONAL_PARAMS_DEFINITION = {
        "subgroup_columns": [], # List of strings
        "moderator_columns": [], # List of strings
        "sensitivity_variable": None,      # 感度分析で使用する変数名
        "sensitivity_value": None,         # 限定対象となる値
        # "ai_interpretation": True, # Default to True - Removed, will be hardcoded
        # "output_format": "detailed" # Default to detailed - Removed, will be hardcoded
    }
    EFFECT_SIZE_TO_ANALYSIS_TYPE_MAP = {
        "OR": "binary_outcome_two_groups", "RR": "binary_outcome_two_groups", "RD": "binary_outcome_two_groups",
        "HR": "hazard_ratio", "PETO": "binary_outcome_two_groups", # PETO is for binary
        "proportion": "single_proportion", "IR": "incidence_rate", # IR for incidence rates
        "SMD": "continuous_outcome_two_groups", "MD": "continuous_outcome_two_groups", "ROM": "continuous_outcome_two_groups",
        "COR": "correlation",
        "yi": "pre_calculated_effect_sizes" # For pre-calculated yi and vi
    }

    def __init__(self, context_manager, async_runner): # Add async_runner if needed for run_meta_analysis
        self.context_manager = context_manager
        self.async_runner = async_runner # Store async_runner

    def _update_collected_params_and_get_next_question(self, extracted_params_map: dict, collected_params_state: dict, data_summary: dict, thread_id: str, channel_id: str) -> tuple[bool, Optional[str]]:
        logger.info(f"Updating collected_params. Current: {collected_params_state}, Extracted: {extracted_params_map}")
        
        # コンテキストからgemini_questionsを取得（正しいパス: data_state.gemini_analysis.suggested_questions）
        context = self.context_manager.get_context(thread_id=thread_id, channel_id=channel_id)
        logger.info(f"DEBUG: parameter_collector - context from context_manager: {json.dumps(context, ensure_ascii=False)}") # DEBUG LOG
        gemini_analysis_state = context.get("data_state", {}).get("gemini_analysis", {})
        gemini_questions = gemini_analysis_state.get("suggested_questions", [])

        for param_key, value in extracted_params_map.items():
            if value is not None:
                if param_key in self.REQUIRED_PARAMS_DEFINITION:
                    collected_params_state["required"][param_key] = value
                    if param_key in collected_params_state["missing_required"]:
                        collected_params_state["missing_required"].remove(param_key)
                elif param_key in self.OPTIONAL_PARAMS_DEFINITION:
                    if isinstance(self.OPTIONAL_PARAMS_DEFINITION.get(param_key), list) and isinstance(value, list):
                         collected_params_state["optional"][param_key] = list(set(collected_params_state["optional"].get(param_key, []) + value))
                    else:
                        collected_params_state["optional"][param_key] = value
                elif param_key == "data_columns":
                    if isinstance(value, dict):
                        collected_params_state["optional"]["data_columns"] = value
        
        logger.info(f"Updated collected_params: {collected_params_state}")

        # Geminiによる自動マッピング結果を取得
        column_mappings_from_context = context.get("data_state", {}).get("column_mappings", {}) # Use already fetched context
        logger.info(f"DEBUG: parameter_collector - Column mappings from context: {json.dumps(column_mappings_from_context, ensure_ascii=False)}") # DEBUG LOG

        # 自動マッピングされたデータ列を collected_params_state["optional"]["data_columns"] に反映
        if "data_columns" not in collected_params_state["optional"]:
            collected_params_state["optional"]["data_columns"] = {}
        
        target_mappings = column_mappings_from_context.get("target_role_mappings", {})
        if isinstance(target_mappings, dict): # target_mappingsが辞書であることを確認
            for role_key, mapped_col_name in target_mappings.items():
                # ai, bi, ci, di, n1i, n2i, m1i, m2i, sd1i, sd2i, proportion_events, proportion_total, proportion_time, yi, vi
                # など、escalcに必要な列を優先的にマッピング
                if role_key in self._get_all_escalc_roles() and not collected_params_state["optional"]["data_columns"].get(role_key) and mapped_col_name:
                    collected_params_state["optional"]["data_columns"][role_key] = mapped_col_name
                    logger.info(f"Auto-mapped data_column '{role_key}' to '{mapped_col_name}' from target_role_mappings")
        else:
            logger.warning(f"target_role_mappings is not a dict or is missing: {target_mappings}")


        # 効果量の自動検出と確認 (required parametersが完了していない場合でも実行)
        # ユーザーがまだ効果量を指定しておらず、かつ、この質問が初回でない（つまり、以前に効果量を尋ねていない）場合にのみ自動検出を試みる
        # ただし、GeminiがCSV分析時に効果量を検出していたら、それを優先する
        if not collected_params_state.get("required", {}).get("effect_size") and \
           ("effect_size" in collected_params_state.get("missing_required", []) or not collected_params_state.get("asked_optional")): # 初回質問または効果量が未収集の場合

            detected_effect_size = column_mappings_from_context.get("detected_effect_size")
            is_log_transformed = column_mappings_from_context.get("is_log_transformed")
            data_format = column_mappings_from_context.get("data_format")
            
            # detected_columns から yi と vi のマッピングも確認 (HRの場合に特に重要)
            detected_columns_map = column_mappings_from_context.get("detected_columns", {})
            logger.info(f"DEBUG: parameter_collector - Initial detected_effect_size: {detected_effect_size}, is_log_transformed: {is_log_transformed}, data_format: {data_format}, detected_columns_map: {json.dumps(detected_columns_map, ensure_ascii=False)}") # DEBUG LOG
            
            if detected_effect_size:
                logger.info(f"DEBUG: parameter_collector - Auto-detected effect size: {detected_effect_size}, log_transformed: {is_log_transformed}, format: {data_format}, detected_cols: {json.dumps(detected_columns_map, ensure_ascii=False)}") # DEBUG LOG
                
                # 自動検出された効果量を設定
                collected_params_state["required"]["effect_size"] = detected_effect_size
                if "effect_size" in collected_params_state.get("missing_required", []):
                    collected_params_state["missing_required"].remove("effect_size")
                
                # 対数変換とデータ形式の情報を保存
                if is_log_transformed is not None:
                    collected_params_state["optional"]["is_log_transformed"] = is_log_transformed
                if data_format is not None:
                    collected_params_state["optional"]["data_format"] = data_format
                
                # HRの場合、yiとviのマッピングが target_role_mappings になければ detected_columns から補完
                if detected_effect_size == "HR" and data_format == "pre_calculated":
                    if "yi" not in collected_params_state["optional"]["data_columns"] and detected_columns_map.get("yi"):
                        collected_params_state["optional"]["data_columns"]["yi"] = detected_columns_map["yi"]
                        logger.info(f"Auto-mapped data_column 'yi' to '{detected_columns_map['yi']}' from detected_columns for HR")
                    if "vi" not in collected_params_state["optional"]["data_columns"] and detected_columns_map.get("vi"):
                        collected_params_state["optional"]["data_columns"]["vi"] = detected_columns_map["vi"]
                        logger.info(f"Auto-mapped data_column 'vi' to '{detected_columns_map['vi']}' from detected_columns for HR")
                
                confirmation_parts = [f"データから効果量「{detected_effect_size}」が検出されました。"]
                if is_log_transformed is True:
                    confirmation_parts.append("データは対数変換済みとして認識されました。")
                elif is_log_transformed is False:
                    confirmation_parts.append("データは元のスケールとして認識されました。")
                
                if data_format == "2x2_table":
                    confirmation_parts.append("2×2表形式のデータとして処理されます。")
                elif data_format == "pre_calculated":
                    confirmation_parts.append("事前計算された効果量として処理されます。")
                    # 事前計算の場合、yiとviがマッピングされているか確認
                    current_yi = collected_params_state["optional"]["data_columns"].get("yi")
                    current_vi = collected_params_state["optional"]["data_columns"].get("vi")
                    if current_yi and current_vi:
                        confirmation_parts.append(f"(効果量: {current_yi}, 分散/SE: {current_vi})")
                    else:
                        confirmation_parts.append("(効果量または分散/SEの列がまだ特定できていません)")

                confirmation_parts.append("この効果量で分析を進めてよろしいですか？ (はい/いいえ、または別の効果量を指定)")
                # この質問を「最後に尋ねた質問」として記録しないようにする（ユーザーの自由な回答を期待するため）
                # context["question_history"]["last_question"] = "\n".join(confirmation_parts) # 更新しない
                return False, "\n".join(confirmation_parts)

        if not collected_params_state["missing_required"]:
            effect_size = collected_params_state.get("required", {}).get("effect_size")
            data_columns = collected_params_state.get("optional", {}).get("data_columns", {})
            
            missing_data_cols_question = self._get_missing_data_columns_question(effect_size, data_columns, data_summary.get('columns', []), target_mappings) # column_mappings を target_mappings に変更
            if missing_data_cols_question:
                return False, missing_data_cols_question

            # サブグループ列の自動マッピングと質問の調整
            if not collected_params_state["optional"].get("subgroup_columns") and "subgroup_columns" not in collected_params_state["asked_optional"]:
                subgroup_candidates = column_mappings_from_context.get("suggested_subgroup_candidates", [])
                
                # gemini_questionsからサブグループ解析用の具体例を取得
                subgroup_examples = []
                for question in gemini_questions:
                    if "サブグループ" in question.get("purpose", "") and question.get("variable_names"):
                        subgroup_examples = question.get("variable_names", [])
                        break
                
                if subgroup_candidates and isinstance(subgroup_candidates, list):
                    # ユーザーが明示的に指定していない場合のみ、候補を初期値として設定
                    if not collected_params_state["optional"].get("subgroup_columns"):
                        collected_params_state["optional"]["subgroup_columns"] = subgroup_candidates
                        logger.info(f"Auto-set subgroup_columns to candidates: {subgroup_candidates}")
                    
                    # 候補を提示する質問文
                    if subgroup_examples:
                        question_text = f"サブグループ解析を行う場合、どの変数（例：{', '.join(subgroup_examples)}）で層別化しますか？\n候補となる列: {', '.join(subgroup_candidates)}"
                    else:
                        question_text = f"サブグループ解析は行いますか？候補となる列: {', '.join(subgroup_candidates)}。\nもし行う場合は、サブグループを示す列名（複数可）を教えてください。（例: subgroup_columns: [age_group, gender]）"
                else:
                    if subgroup_examples:
                        question_text = f"サブグループ解析を行う場合、どの変数（例：{', '.join(subgroup_examples)}）で層別化しますか？"
                    else:
                        question_text = "サブグループ解析は行いますか？もし行う場合は、サブグループを示す列名（複数可）を教えてください。（例: subgroup_columns: [age_group, gender]）"
                
                collected_params_state["asked_optional"].append("subgroup_columns")
                return False, question_text

            # モデレーター列の自動マッピングと質問の調整
            if not collected_params_state["optional"].get("moderator_columns") and "moderator_columns" not in collected_params_state["asked_optional"]:
                 moderator_candidates = column_mappings_from_context.get("suggested_moderator_candidates", [])
                 
                 # gemini_questionsからメタ回帰分析用の具体例を取得
                 moderator_examples = []
                 for question in gemini_questions:
                     if "メタ回帰" in question.get("purpose", "") or "モデレーター" in question.get("purpose", ""):
                         moderator_examples = question.get("variable_names", [])
                         break
                 
                 if moderator_candidates and isinstance(moderator_candidates, list):
                    # ユーザーが明示的に指定していない場合のみ、候補を初期値として設定
                    if not collected_params_state["optional"].get("moderator_columns"):
                        collected_params_state["optional"]["moderator_columns"] = moderator_candidates
                        logger.info(f"Auto-set moderator_columns to candidates: {moderator_candidates}")

                    # 候補を提示する質問文
                    if moderator_examples:
                        question_text = f"メタ回帰分析を行う場合、どの変数（例：{', '.join(moderator_examples)}）を共変量として使用しますか？\n候補となる列: {', '.join(moderator_candidates)}"
                    else:
                        question_text = f"メタ回帰分析は行いますか？候補となる列: {', '.join(moderator_candidates)}。\nもし行う場合は、共変量（モデレーター）となる列名を教えてください。（例: moderator_columns: [year, dosage]）"
                 else:
                    if moderator_examples:
                        question_text = f"メタ回帰分析を行う場合、どの変数（例：{', '.join(moderator_examples)}）を共変量として使用しますか？"
                    else:
                        question_text = "メタ回帰分析は行いますか？もし行う場合は、共変量（モデレーター）となる列名を教えてください。（例: moderator_columns: [year, dosage]）"
                 
                 collected_params_state["asked_optional"].append("moderator_columns")
                 return False, question_text

            # 感度分析の質問
            if not collected_params_state["optional"].get("sensitivity_variable") and "sensitivity_variable" not in collected_params_state["asked_optional"]:
                sensitivity_candidates_formatted = []
                note_for_n1_filter = "(n=1のカテゴリはメタアナリシスが実施できないため、表示から除外しています)"
                
                if data_summary and data_summary.get("columns"):
                    # data_summary['head'] はデータの先頭部分のみです。
                    # 正確なカテゴリの出現回数を得るには、全データへのアクセスが必要です。
                    # ここでは df_sample_head を使いますが、これは近似的な情報となります。
                    df_sample_head = pd.DataFrame(data_summary.get("head", [])) 
                    if not df_sample_head.empty:
                        for col in data_summary.get("columns", []):
                            if col in df_sample_head.columns and \
                               (df_sample_head[col].dtype == 'object' or pd.api.types.is_string_dtype(df_sample_head[col])):
                                
                                # headデータからカテゴリとその出現回数を取得
                                value_counts_in_head = df_sample_head[col].value_counts()
                                # 出現回数が2回以上のカテゴリのみを抽出 (headの範囲内)
                                valid_categories_in_head = [
                                    str(idx) for idx, count in value_counts_in_head.items() if count > 1
                                ]
                                
                                # 元のロジック: ユニークなカテゴリ数が1より多く5以下の場合に候補とする
                                # ここでは、n>1の有効なカテゴリが抽出できた場合に候補とする
                                # さらに、その有効なカテゴリの数が1より多く5以下であるかもチェックする
                                if valid_categories_in_head and (1 < len(valid_categories_in_head) <= 5):
                                    sensitivity_candidates_formatted.append(f"{col} ({', '.join(valid_categories_in_head)})")
                
                if sensitivity_candidates_formatted:
                    question_text = (
                        f"感度分析（特定のカテゴリに限定した分析）を行いますか？\n"
                        f"候補となる変数とカテゴリ (データ先頭部分に基づく):\n"
                        f"{'; '.join(sensitivity_candidates_formatted)}\n"
                        f"{note_for_n1_filter}"
                    )
                else:
                    question_text = (
                        "感度分析（特定のカテゴリに限定した分析）を行いますか？\n"
                        "(適切な候補が見つかりませんでした。データ先頭部分に複数回出現し、カテゴリ数が2～5個の変数が少ない可能性があります)\n"
                        f"{note_for_n1_filter}"
                    )
                collected_params_state["asked_optional"].append("sensitivity_variable")
                return False, question_text

            if collected_params_state["optional"].get("sensitivity_variable") and \
               not collected_params_state["optional"].get("sensitivity_value") and \
               "sensitivity_value" not in collected_params_state["asked_optional"]:
                
                sensitivity_var = collected_params_state["optional"]["sensitivity_variable"]
                # 実際のデータからカテゴリ値を取得 (data_summaryのheadから)
                # CsvProcessorが全データを読み込んでユニーク値を渡す方がより正確
                # ここでは data_summary.head を使う簡易的な方法
                unique_values_for_var = []
                if data_summary and data_summary.get("head"):
                    df_sample_head = pd.DataFrame(data_summary.get("head", []))
                    if sensitivity_var in df_sample_head.columns:
                        unique_values_for_var = df_sample_head[sensitivity_var].unique().tolist()
                
                if unique_values_for_var:
                    question_text = f"変数「{sensitivity_var}」のどの値に限定した分析を行いますか？\n選択肢: {', '.join(map(str, unique_values_for_var))}"
                else:
                    question_text = f"変数「{sensitivity_var}」に限定する値を教えてください。"
                
                collected_params_state["asked_optional"].append("sensitivity_value")
                return False, question_text
            
            logger.info("All required, data_columns, and optional (or asked) parameters collected. Ready for analysis.")
            return True, None

        next_missing_required = collected_params_state["missing_required"][0]
        questions_map = {
            "effect_size": f"どの効果量（例：OR, RR, SMD, HR, proportion, yi）で分析しますか？\n利用可能な列: {', '.join(data_summary.get('columns', []))}",
            "model_type": "固定効果モデル（fixed）またはランダム効果モデル（random）のどちらを使用しますか？"
        }
        logger.info(f"Missing required parameter: {next_missing_required}. Asking question.")
        return False, questions_map.get(next_missing_required, "追加情報が必要です。")

    def _get_all_escalc_roles(self) -> List[str]:
        """escalcで使用可能な全ての列ロールを返す"""
        return ["ai", "bi", "ci", "di", "n1i", "n2i", "m1i", "m2i", "sd1i", "sd2i", 
                "proportion_events", "proportion_total", "proportion_time", "yi", "vi",
                "study_label", "study_label_author", "study_label_year"]

    def _get_missing_data_columns_question(self, effect_size: Optional[str], current_data_cols: Dict[str, str], available_csv_columns: List[str], column_mappings: Dict[str, Any]) -> Optional[str]:
        if not effect_size:
            return None

        required_mapping = {}
        col_descriptions = {
            "study_label_author": "研究の著者名を示す列", "study_label_year": "研究の発表年を示す列", "study_label": "研究のユニークなラベルを示す列",
            "ai": "治療群のイベント数を示す列", "bi": "治療群の非イベント数（または治療群の総数からイベント数を引いたもの）を示す列",
            "ci": "対照群のイベント数を示す列", "di": "対照群の非イベント数（または対照群の総数からイベント数を引いたもの）を示す列",
            "n1i": "治療群のサンプルサイズを示す列", "n2i": "対照群のサンプルサイズを示す列",
            "m1i": "治療群の平均値を示す列", "m2i": "対照群の平均値を示す列",
            "sd1i": "治療群の標準偏差を示す列", "sd2i": "対照群の標準偏差を示す列",
            "proportion_events": "割合計算のためのイベント数を示す列", "proportion_total": "割合計算のための総数を示す列",
            "yi": "事前計算された効果量を示す列", "vi": "事前計算された効果量の分散を示す列",
        }

        if effect_size in ["OR", "RR", "RD", "PETO"]: 
            # bi, di は n1i/n2i と ai/ci から計算可能なので、ここでは必須としない
            # 必要なのは ai, ci と、(bi, di) または (n1i, n2i) の組み合わせ
            required_mapping = {"ai": None, "ci": None} 
            # n1i, n2i のチェックは、bi, di がない場合に _generate_escalc_code で行われる
            # ここでユーザーに尋ねるべきは、ai, ci, そして bi/di がなければ n1i/n2i
            # より具体的に不足を指摘するために、ここではまず ai, ci を確認
            # bi, di がなければ、次に n1i, n2i を尋ねるという多段階の質問も考えられるが、
            # Geminiによるパラメータ抽出とRスクリプト生成側でカバーできることを期待し、
            # ここでは基本的な ai, ci のみ必須とする。
            # もし bi, di がなく、n1i, n2i もない場合は、Rスクリプト生成時にエラーとなる。
        elif effect_size in ["SMD", "MD", "ROM"]: required_mapping = {"n1i": None, "n2i": None, "m1i": None, "m2i": None, "sd1i": None, "sd2i": None}
        elif effect_size == "proportion": required_mapping = {"proportion_events": None, "proportion_total": None}
        elif effect_size == "IR": required_mapping = {"proportion_events": None, "proportion_time": "イベント発生期間または追跡時間を示す列"}
        elif effect_size == "yi": required_mapping = {"yi": None, "vi": None}
        
        missing_cols = [key for key in required_mapping if key not in current_data_cols or not current_data_cols[key]]
        if not missing_cols: return None

        next_missing_col_key = missing_cols[0]
        description = col_descriptions.get(next_missing_col_key, next_missing_col_key)
        
        return (
            f"効果量「{effect_size}」の分析には、{description}が必要です。\n"
            f"CSVファイル内の利用可能な列は次の通りです: {', '.join(available_csv_columns)}\n"
            f"「{description}」に対応する列名を教えてください。（例: {next_missing_col_key}: actual_column_name）"
        )

    def handle_analysis_preference_dialog(self, text: str, thread_ts: str, channel_id: str, client, context: dict, run_meta_analysis_func, check_analysis_job_func):
        logger.info(f"=== handle_analysis_preference_dialog (State: {context.get('dialog_state', {}).get('state')}) ===")
        logger.info(f"Received text for parameter collection in handle_analysis_preference_dialog: '{text}'")

        # タイムアウト処理: 5分以上経過していたら強制的にフラグをクリア
        if context.get("parameter_collection_in_progress"):
            started_at = context.get("parameter_collection_started_at", 0)
            if time.time() - started_at > 300:  # 5分
                logger.warning(f"Parameter collection for thread {thread_ts} timed out after 5 minutes. Resetting flag.")
                context["parameter_collection_in_progress"] = False
                # タイムアウトしたことをユーザーに通知しても良いかもしれない

        # # 処理中フラグのチェック (ゴーストメンション対策のためコメントアウト)
        # if context.get("parameter_collection_in_progress"):
        #     # 経過時間に応じてメッセージを出し分ける
        #     started_at = context.get("parameter_collection_started_at", time.time())
        #     elapsed_time = time.time() - started_at
            
        #     if elapsed_time < 60: # 1分未満
        #         wait_message = "現在、パラメータを解析中です。少々お待ちください... 🤔"
        #     elif elapsed_time < 180: # 3分未満
        #         wait_message = "まだ考え中です。もう少しお待ちください... 💭"
        #     else: # 3分以上
        #         wait_message = "解析処理が進行中です。完了まで今しばらくお待ちください... ⏳"
            
        #     try:
        #         client.chat_postMessage(
        #             channel=channel_id,
        #             thread_ts=thread_ts,
        #             text=wait_message
        #         )
        #     except Exception as e:
        #         logger.error(f"Failed to post 'parameter collection in progress' message: {e}")
        #     self.context_manager.save_context(thread_ts, context, channel_id) # コンテキストを保存
        #     return

        data_state = context.get("data_state", {})
        data_summary = data_state.get("summary", {})
        dialog_state = context.get("dialog_state", {})
        collected_params_state = dialog_state.get("collected_params")

        if "question_history" not in context:
            context["question_history"] = {"last_question": None, "count": 0, "max_retries": 5}
            logger.info(f"Initialized question_history for thread {thread_ts}")
        elif "max_retries" not in context["question_history"]:
            context["question_history"]["max_retries"] = 5

        if not data_summary:
            logger.error("Data summary not found. Cannot proceed.")
            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="データ概要が見つからないため、分析設定を進められません。")
            self.context_manager.save_context(thread_ts, context, channel_id)
            return

        if dialog_state.get("state") == "collecting_params" and collected_params_state:
            thinking_message_ts = None
            try:
                # 処理開始
                context["parameter_collection_in_progress"] = True
                context["parameter_collection_started_at"] = time.time()
                self.context_manager.save_context(thread_ts, context, channel_id) # フラグ設定後すぐに保存

                # text がある場合のみ「検討中」メッセージを出す (Gemini呼び出しがあるため)
                if text:
                    response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="解析方法を検討中です。少々お待ちください...")
                    thinking_message_ts = response.get("ts")
            except Exception as e: 
                logger.error(f"Failed to post 'thinking' message or set progress flag: {e}")
                # フラグが設定されたままにならないように、エラー時はFalseに戻す試み
                context["parameter_collection_in_progress"] = False
                self.context_manager.save_context(thread_ts, context, channel_id)


            try:
                extracted_params_map = {}
                if text:
                    # 会話履歴と収集コンテキストを準備
                    raw_history = context.get("history", [])
                    conversation_history_for_gemini = []
                    for entry in raw_history:
                        if "user" in entry and entry["user"]:
                            conversation_history_for_gemini.append({"role": "user", "content": entry["user"]})
                        if "bot" in entry and entry["bot"]:
                             conversation_history_for_gemini.append({"role": "model", "content": entry["bot"]}) # Geminiは 'model' を期待

                    # 現在どのパラメータについて質問しているかを特定するロジック
                    current_question_target = None
                    if collected_params_state.get("missing_required"):
                        current_question_target = collected_params_state["missing_required"][0]
                    elif "subgroup_columns" not in collected_params_state.get("asked_optional", []):
                        current_question_target = "subgroup_columns"
                    elif "moderator_columns" not in collected_params_state.get("asked_optional", []):
                        current_question_target = "moderator_columns"
                    elif not self._get_missing_data_columns_question(collected_params_state.get("required", {}).get("effect_size"), collected_params_state.get("optional", {}).get("data_columns", {}), data_summary.get('columns', []), context.get("data_state", {}).get("column_mappings", {}).get("target_role_mappings", {})):
                         current_question_target = "data_columns"


                    collection_context_for_gemini = {
                        "phase": "parameter_collection",
                        "purpose": "メタアナリシスの実行に必要なパラメータ（効果量、モデルタイプ、データ列マッピング、サブグループ列、モデレーター列）を収集中です。",
                        "collected_params": {
                            "required": collected_params_state.get("required"),
                            "optional": collected_params_state.get("optional")
                        },
                        "missing_required_params": collected_params_state.get("missing_required"),
                        "asked_optional_params": collected_params_state.get("asked_optional"),
                        "last_bot_question": context.get("question_history", {}).get("last_question"),
                        "current_question_target": current_question_target
                    }
                    
                    gemini_response = extract_parameters_from_user_input(
                        user_input=text,
                        data_summary=data_summary,
                        conversation_history=conversation_history_for_gemini,
                        collection_context=collection_context_for_gemini
                    )
                    extracted_params_map = gemini_response.get("extracted_params", {}) if isinstance(gemini_response, dict) else {}
                    if not extracted_params_map:
                        logger.warning(f"Gemini Function Calling failed or returned no params for text '{text}'. Response: {gemini_response}")
                else:
                    logger.info("Text for parameter extraction was empty, skipping Gemini call.")

                parsed_model_type = None
                lower_text = text.lower() 
                if "fixed" in lower_text or "固定" in lower_text: parsed_model_type = "fixed"
                elif "random" in lower_text or "ランダム" in lower_text: parsed_model_type = "random"
                if parsed_model_type and not extracted_params_map.get("model_type"): extracted_params_map["model_type"] = parsed_model_type
                
                is_ready, next_question = self._update_collected_params_and_get_next_question(extracted_params_map, collected_params_state, data_summary, thread_ts, channel_id)
                
                dialog_state["is_initial_response"] = False
                context["dialog_state"]["collected_params"] = collected_params_state

                if is_ready:
                    final_preferences = {
                        "measure": collected_params_state["required"].get("effect_size"),
                        "model_type": collected_params_state["required"].get("model_type"),
                        "subgroup_columns": collected_params_state["optional"].get("subgroup_columns", self.OPTIONAL_PARAMS_DEFINITION.get("subgroup_columns", [])),
                        "moderator_columns": collected_params_state["optional"].get("moderator_columns", self.OPTIONAL_PARAMS_DEFINITION.get("moderator_columns", [])),
                        "sensitivity_variable": collected_params_state["optional"].get("sensitivity_variable"),
                        "sensitivity_value": collected_params_state["optional"].get("sensitivity_value"),
                        "data_columns": collected_params_state["optional"].get("data_columns", {}),
                        "is_log_transformed": collected_params_state["optional"].get("is_log_transformed"),
                        "data_format": collected_params_state["optional"].get("data_format"),
                        "ai_interpretation": True, "output_format": "detailed",
                    }
                    final_preferences["analysis_type"] = self.EFFECT_SIZE_TO_ANALYSIS_TYPE_MAP.get(final_preferences.get("measure"), "meta_analysis_basic")
                    
                    context["analysis_state"] = {"preferences": final_preferences, "stage": "running"}
                    job_id = self.async_runner.run_analysis_async( 
                        run_meta_analysis_func, 
                        {"csv_path": data_state.get("file_path"), "analysis_preferences": final_preferences, "thread_dir": data_state.get("thread_dir")},
                        None
                    )
                    context["analysis_job_id"] = job_id
                    dialog_state["state"] = "analysis_running"
                    
                    param_summary_list = [f"{k}: {v}" for k, v in final_preferences.items() if v and k in ["measure", "model_type", "subgroup_columns", "moderator_columns", "sensitivity_variable", "sensitivity_value"]]
                    confirmation_msg = f"ありがとうございます。以下の設定でメタアナリシスを開始します：\n- {', '.join(param_summary_list)}"
                    client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=confirmation_msg)
                    check_analysis_job_func(job_id, channel_id, thread_ts, client) 
                else:
                    if next_question == context["question_history"]["last_question"]: context["question_history"]["count"] += 1
                    else: context["question_history"] = {"last_question": next_question, "count": 1, "max_retries": 5}
                    
                    if context["question_history"]["count"] >= context["question_history"]["max_retries"]:
                        client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=f"申し訳ございません、パラメータの収集で問題が発生したようです（同じ質問「{next_question}」が{context['question_history']['max_retries']}回繰り返されました）。最初からやり直してください。")
                        DialogStateManager.set_dialog_state(context, "WAITING_FILE")
                        context.pop("question_history", None)
                        if collected_params_state:
                            collected_params_state.update({"required": {}, "optional": {}, "missing_required": list(self.REQUIRED_PARAMS_DEFINITION.keys()), "asked_optional": []})
                    else:
                        response = client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=next_question)
                        # Botのメッセージ送信時刻を記録 (parameter_collector内でも更新)
                        if response.get("ok"):
                            context["last_bot_message"] = {
                                "ts": response.get("ts"),
                                "timestamp": time.time(), # UNIXタイムスタンプ
                                "content": next_question
                            }
                            logger.info(f"Updated last_bot_message in parameter_collector: ts={response.get('ts')}")
                        else:
                            logger.error(f"Failed to send message in parameter_collector, not updating last_bot_message. Response: {response}")
            
            except Exception as e:
                error_message = f"Error in handle_analysis_preference_dialog: {type(e).__name__} - {str(e)}"
                logger.error(error_message, exc_info=True) # Keep exc_info for full trace if possible
                logger.info(f"PARAMETER_COLLECTOR_ERROR_DETAIL: {error_message}") # Add specific INFO log for easier finding
                client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="パラメータ処理中にエラーが発生しました。詳細はシステムログを確認してください。")
            finally:
                context["parameter_collection_in_progress"] = False # 処理完了時にフラグをクリア
                if thinking_message_ts:
                    try: client.chat_delete(channel=channel_id, ts=thinking_message_ts)
                    except Exception as e_del: logger.error(f"Failed to delete 'thinking' message: {e_del}")
        else:
            logger.warning(f"Unexpected dialog state or missing collected_params: {dialog_state}")
            client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text="分析設定の現在の状態を認識できませんでした。")
            DialogStateManager.set_dialog_state(context, "WAITING_FILE")

        self.context_manager.save_context(thread_ts, context, channel_id)
