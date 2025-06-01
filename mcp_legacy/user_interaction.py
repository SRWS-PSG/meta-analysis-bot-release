import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class AnalysisPreferenceDialog:
    """ユーザーの分析設定を対話的に取得するクラス"""
    
    def __init__(self, data_summary: Dict[str, Any]):
        """
        初期化
        
        Args:
            data_summary: CSVデータの概要情報
        """
        self.data_summary = data_summary
        self.columns = data_summary.get("columns", [])
        self.preferences = {}
        self.dialog_state = "initial"
    
    def get_initial_message(self) -> str:
        """初期メッセージを取得する"""
        column_list = ", ".join(f"`{col}`" for col in self.columns)
        
        message = f"""
CSVデータを読み込みました。以下の列が含まれています：
{column_list}

どのような分析を行いますか？
1. 基本的なメタ解析
2. サブグループ解析
3. メタ回帰分析
4. 異質性解析
5. その他（具体的に指定）
        """
        return message.strip()
    
    def process_analysis_type_response(self, response: str) -> Tuple[str, str]:
        """
        分析タイプの応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        response = response.strip().lower()
        
        if "1" in response or "基本" in response or "メタ解析" in response:
            self.preferences["analysis_type"] = "basic"
            self.dialog_state = "model_type"
            return self._get_model_type_message(), "model_type"
        
        elif "2" in response or "サブグループ" in response:
            self.preferences["analysis_type"] = "subgroup"
            self.dialog_state = "subgroup_column"
            return self._get_subgroup_column_message(), "subgroup_column"
        
        elif "3" in response or "回帰" in response or "メタ回帰" in response:
            self.preferences["analysis_type"] = "regression"
            self.dialog_state = "moderator_columns"
            return self._get_moderator_columns_message(), "moderator_columns"
        
        elif "4" in response or "異質性" in response:
            self.preferences["analysis_type"] = "heterogeneity"
            self.dialog_state = "model_type"
            return self._get_model_type_message(), "model_type"
        
        elif "5" in response or "その他" in response:
            self.preferences["analysis_type"] = "custom"
            self.dialog_state = "custom_analysis"
            return "具体的にどのような分析を行いたいですか？", "custom_analysis"
        
        else:
            return "申し訳ありませんが、選択肢から選んでください（1-5）。", "initial"
    
    def _get_model_type_message(self) -> str:
        """モデルタイプのメッセージを取得する"""
        return """
どのモデルタイプを使用しますか？
1. 固定効果モデル
2. ランダム効果モデル（デフォルト）
        """.strip()
    
    def _get_subgroup_column_message(self) -> str:
        """サブグループ列のメッセージを取得する"""
        potential_columns = [col for col in self.columns if col not in ["study", "yi", "vi", "n"]]
        column_list = ", ".join(f"`{col}`" for col in potential_columns)
        
        return f"""
サブグループ解析に使用する列を選択してください。
利用可能な列: {column_list}
        """.strip()
    
    def _get_moderator_columns_message(self) -> str:
        """モデレーター列のメッセージを取得する"""
        potential_columns = [col for col in self.columns if col not in ["study", "yi", "vi", "n"]]
        column_list = ", ".join(f"`{col}`" for col in potential_columns)
        
        return f"""
メタ回帰分析に使用するモデレーター変数（共変量）を選択してください。
複数選択する場合はカンマで区切ってください。
利用可能な列: {column_list}
        """.strip()
    
    def process_model_type_response(self, response: str) -> Tuple[str, str]:
        """
        モデルタイプの応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        response = response.strip().lower()
        
        if "1" in response or "固定" in response:
            self.preferences["model_type"] = "fixed"
        else:
            self.preferences["model_type"] = "random"
        
        # self.dialog_state = "output_format" # output_format is fixed
        # return self._get_output_format_message(), "output_format"
        # Directly move to complete as ai_interpretation and output_format are fixed
        self.dialog_state = "complete"
        summary = self._get_preferences_summary()
        return f"""
設定が完了しました。以下の設定で分析を実行します：

{summary}

分析を開始します...
        """.strip(), None # End dialog
    
    def process_subgroup_column_response(self, response: str) -> Tuple[str, str]:
        """
        サブグループ列の応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        column = response.strip()
        
        if column in self.columns:
            self.preferences["subgroup_column"] = column
            self.dialog_state = "model_type"
            return self._get_model_type_message(), "model_type"
        else:
            return f"列 `{column}` が見つかりません。正確な列名を入力してください。", "subgroup_column"
    
    def process_moderator_columns_response(self, response: str) -> Tuple[str, str]:
        """
        モデレーター列の応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        columns = [col.strip() for col in response.split(",")]
        valid_columns = [col for col in columns if col in self.columns]
        
        if not valid_columns:
            return "有効な列名が指定されていません。正確な列名をカンマ区切りで入力してください。", "moderator_columns"
        
        self.preferences["moderator_columns"] = valid_columns
        self.dialog_state = "model_type"
        return self._get_model_type_message(), "model_type"
    
    def process_custom_analysis_response(self, response: str) -> Tuple[str, str]:
        """
        カスタム分析の応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        self.preferences["custom_analysis_description"] = response.strip()
        # self.dialog_state = "output_format" # output_format is fixed
        # return self._get_output_format_message(), "output_format"
        # Directly move to complete
        self.dialog_state = "complete"
        summary = self._get_preferences_summary()
        return f"""
設定が完了しました。以下の設定で分析を実行します：

{summary}

分析を開始します...
        """.strip(), None # End dialog
    
    # def _get_output_format_message(self) -> str: # No longer needed
    #     """出力形式のメッセージを取得する"""
    #     return """
    # 結果の出力形式を選択してください：
    # 1. 基本レポート（森林プロットのみ）
    # 2. 詳細レポート（森林プロット、漏斗プロット、異質性指標）
    # 3. 学術論文形式（Methods、Results、Discussionセクション付き）
    #     """.strip()
    
    # def process_output_format_response(self, response: str) -> Tuple[str, str]: # No longer needed
    #     """
    #     出力形式の応答を処理する
        
    #     Args:
    #         response: ユーザーの応答
        
    #     Returns:
    #         次のメッセージと次の状態
    #     """
    #     response = response.strip().lower()
        
    #     if "1" in response or "基本" in response:
    #         self.preferences["output_format"] = "basic"
    #     elif "2" in response or "詳細" in response:
    #         self.preferences["output_format"] = "detailed"
    #     else:
    #         self.preferences["output_format"] = "academic"
        
    #     self.dialog_state = "ai_interpretation"
    #     return "AIによる結果の解釈を含めますか？（はい/いいえ）", "ai_interpretation"
    
    # def process_ai_interpretation_response(self, response: str) -> Tuple[str, Optional[str]]: # No longer needed
    #     """
    #     AI解釈の応答を処理する
        
    #     Args:
    #         response: ユーザーの応答
        
    #     Returns:
    #         次のメッセージと次の状態（Noneの場合は対話終了）
    #     """
    #     response = response.strip().lower()
        
    #     if "はい" in response or "yes" in response or "y" in response:
    #         self.preferences["ai_interpretation"] = True
    #     else:
    #         self.preferences["ai_interpretation"] = False
        
    #     self.dialog_state = "complete"
        
    #     summary = self._get_preferences_summary()
    #     return f"""
    # 設定が完了しました。以下の設定で分析を実行します：

    # {summary}

    # 分析を開始します...
    #     """.strip(), None
    
    def _get_output_format_message(self) -> str:
        """出力形式のメッセージを取得する"""
        return """
結果の出力形式を選択してください：
1. 基本レポート（森林プロットのみ）
2. 詳細レポート（森林プロット、漏斗プロット、異質性指標）
3. 学術論文形式（Methods、Results、Discussionセクション付き）
        """.strip()
    
    def process_output_format_response(self, response: str) -> Tuple[str, str]:
        """
        出力形式の応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態
        """
        response = response.strip().lower()
        
        if "1" in response or "基本" in response:
            self.preferences["output_format"] = "basic"
        elif "2" in response or "詳細" in response:
            self.preferences["output_format"] = "detailed"
        else:
            self.preferences["output_format"] = "academic"
        
        self.dialog_state = "ai_interpretation"
        return "AIによる結果の解釈を含めますか？（はい/いいえ）", "ai_interpretation"
    
    def process_ai_interpretation_response(self, response: str) -> Tuple[str, Optional[str]]:
        """
        AI解釈の応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと次の状態（Noneの場合は対話終了）
        """
        response = response.strip().lower()
        
        if "はい" in response or "yes" in response or "y" in response:
            self.preferences["ai_interpretation"] = True
        else:
            self.preferences["ai_interpretation"] = False
        
        self.dialog_state = "complete"
        
        summary = self._get_preferences_summary()
        return f"""
設定が完了しました。以下の設定で分析を実行します：

{summary}

分析を開始します...
        """.strip(), None
    
    def _get_preferences_summary(self) -> str:
        """設定の概要を取得する"""
        analysis_types = {
            "basic": "基本的なメタ解析",
            "subgroup": "サブグループ解析",
            "regression": "メタ回帰分析",
            "heterogeneity": "異質性解析",
            "custom": "カスタム分析"
        }
        
        model_types = {
            "fixed": "固定効果モデル",
            "random": "ランダム効果モデル"
        }
        
        # output_formats = { # No longer needed as it's fixed to detailed
        #     "basic": "基本レポート",
        #     "detailed": "詳細レポート",
        #     "academic": "学術論文形式"
        # }
        
        summary = []
        
        analysis_type = self.preferences.get("analysis_type")
        if analysis_type:
            summary.append(f"分析タイプ: {analysis_types.get(analysis_type, analysis_type)}")
        
        subgroup_column = self.preferences.get("subgroup_column")
        if subgroup_column:
            summary.append(f"サブグループ列: {subgroup_column}")
        
        moderator_columns = self.preferences.get("moderator_columns")
        if moderator_columns:
            summary.append(f"モデレーター変数: {', '.join(moderator_columns)}")
        
        custom_description = self.preferences.get("custom_analysis_description")
        if custom_description:
            summary.append(f"カスタム分析: {custom_description}")
        
        model_type = self.preferences.get("model_type")
        if model_type:
            summary.append(f"モデルタイプ: {model_types.get(model_type, model_type)}")
        
        # output_format is fixed to "detailed"
        summary.append(f"出力形式: 詳細レポート")
        
        # ai_interpretation is fixed to True
        summary.append(f"AI解釈: あり")
        
        return "\n".join(summary)
    
    def process_response(self, response: str) -> Tuple[str, bool]:
        """
        ユーザーの応答を処理する
        
        Args:
            response: ユーザーの応答
        
        Returns:
            次のメッセージと対話が完了したかどうか
        """
        if self.dialog_state == "initial":
            next_message, next_state = self.process_analysis_type_response(response)
        elif self.dialog_state == "model_type":
            next_message, next_state = self.process_model_type_response(response)
        elif self.dialog_state == "subgroup_column":
            next_message, next_state = self.process_subgroup_column_response(response)
        elif self.dialog_state == "moderator_columns":
            next_message, next_state = self.process_moderator_columns_response(response)
        elif self.dialog_state == "custom_analysis":
            # next_message, next_state = self.process_custom_analysis_response(response) # This now directly goes to complete
            self.preferences["custom_analysis_description"] = response.strip()
            self.dialog_state = "complete"
            summary_text = self._get_preferences_summary()
            next_message = f"""
設定が完了しました。以下の設定で分析を実行します：

{summary_text}

分析を開始します...
            """.strip()
            next_state = None # End dialog
        # elif self.dialog_state == "output_format": # Removed
            # next_message, next_state = self.process_output_format_response(response)
        # elif self.dialog_state == "ai_interpretation": # Removed
            # next_message, next_state = self.process_ai_interpretation_response(response)
        else:
            next_message = "対話が完了しています。"
            next_state = None
        
        self.dialog_state = next_state if next_state else "complete"
        is_complete = next_state is None or self.dialog_state == "complete"
        
        return next_message, is_complete
    
    def get_analysis_preferences(self) -> Dict[str, Any]:
        """分析設定を取得する"""
        return self.preferences

def get_prompt_id_from_preferences(preferences: Dict[str, Any]) -> str:
    """
    ユーザーの設定からプロンプトIDを取得する
    
    Args:
        preferences: ユーザーの分析設定
    
    Returns:
        プロンプトID
    """
    analysis_type = preferences.get("analysis_type")
    model_type = preferences.get("model_type")
    
    if analysis_type == "regression":
        return "meta_analysis_regression"
    elif analysis_type == "subgroup":
        return "meta_analysis_subgroup"
    elif analysis_type == "heterogeneity":
        return "meta_analysis_heterogeneity"
    elif model_type == "fixed":
        return "meta_analysis_fixed"
    elif model_type == "random":
        return "meta_analysis_random"
    else:
        return "meta_analysis_forest"

def get_report_type_from_preferences(preferences: Dict[str, Any]) -> str:
    """
    ユーザーの設定からレポートタイプを取得する
    
    Args:
        preferences: ユーザーの分析設定
    
    Returns:
        レポートタイプ
    """
    analysis_type = preferences.get("analysis_type")
    # output_format = preferences.get("output_format") # Fixed to "detailed"
    
    # Since output_format is always "detailed", the report type logic simplifies.
    # "academic" was a special case. "detailed" implies plots and heterogeneity.
    # The Rmd template used is now always basic_report.Rmd (which handles detailed content).
    if analysis_type == "regression":
        return "regression" # Keeps specific Rmd for regression if it exists and is different
    elif analysis_type == "subgroup":
        return "subgroup"   # Keeps specific Rmd for subgroup if it exists and is different
    else: # Default for "detailed" output
        return "basic" # basic_report.Rmd is used for detailed output
