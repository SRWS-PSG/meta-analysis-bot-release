import os
import json
import logging
from typing import List, Dict, Any # 追加

# mainモジュールからclean_env_varをインポート
# 注意: 循環参照を避けるため、main.pyが直接gemini_utilsをトップレベルでインポートしていないことを確認
try:
    from main import clean_env_var
except ImportError:
    # ローカルテストや特定の実行コンテキストでmainが直接見つからない場合のためのフォールバック
    # この場合、clean_env_varがこのモジュール内で定義されているか、
    # または他の方法で利用可能である必要がある。
    # ここでは、main.pyに定義されているものと同じものを再定義する。
    def clean_env_var(var_name, default=None):
        value = os.environ.get(var_name, default)
        if value:
            return value.strip().lstrip('\ufeff').strip()
        return value

from google import genai
from google.genai import types # Changed from GenerateContentConfig
from google.genai.types import (
    HttpOptions, # Kept HttpOptions
    # GenerateContentConfig # No longer needed directly here for extract_parameters
)
import traceback

logger = logging.getLogger(__name__)

def initialize_gemini_client():
    """Google Gemini APIクライアントを初期化する"""
    api_key = clean_env_var("GEMINI_API_KEY") # BOM除去を適用
    if not api_key:
        logger.warning("GEMINI_API_KEYが設定されていません。Gemini機能は無効になります。")
        return None
    
    try:
        # APIキー認証を優先するため、他の認証情報を一時的に退避・削除するロジックは
        # clean_env_var の適用とは独立しているため、そのまま維持します。
        original_google_application_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        original_gcloud_project = os.environ.get("GCLOUD_PROJECT")
        
        temp_env = {}
        if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            temp_env["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS")
        if "GCLOUD_PROJECT" in os.environ:
            temp_env["GCLOUD_PROJECT"] = os.environ.pop("GCLOUD_PROJECT")

        client = genai.Client(
            api_key=api_key, # BOMが除去されたAPIキーを使用
            http_options=HttpOptions(api_version="v1beta")
        )
        
        # 環境変数を復元
        os.environ.update(temp_env)
            
        logger.info("Gemini APIクライアントが正常に初期化されました（API Key認証）")
        return client
    except Exception as e:
        # 環境変数を復元（エラー時も確実に復元）
        os.environ.update(temp_env)
            
        logger.error(f"Gemini APIクライアントの初期化中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def interpret_meta_analysis_results(results_summary, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """メタアナリシス結果を解釈する"""
    client = initialize_gemini_client()
    if not client:
        return None
    
    try:
        prompt = f"""
        あなたは医学研究と統計学の専門家です。以下のメタアナリシス結果を解釈し、学術論文のResults/Discussionセクションに適した形式で英語で説明してください。
        
        結果の要約:
        {json.dumps(results_summary, ensure_ascii=False, indent=2)}
        
        以下の点について言及してください：
        1. 全体的な効果量とその統計的有意性
        2. 異質性の程度とその解釈
        3. 結果の臨床的意義
        4. 結果の限界と注意点
        
        学術的な文体で、簡潔かつ正確に記述してください。
        """
        
        response = client.models.generate_content( # Using the base client.models directly
            model=f"models/{model_name}", # Ensure "models/" prefix
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Gemini API呼び出し中にエラーが発生しました (interpret_meta_analysis_results): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def interpret_meta_regression_results(results_summary, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """メタ回帰分析結果を解釈する"""
    client = initialize_gemini_client()
    if not client:
        return None
    
    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        prompt = f"""
        あなたは医学研究と統計学の専門家です。以下のメタ回帰分析結果を解釈し、英語で学術論文のResults/Discussionセクションに適した形式で説明してください。
        
        結果の要約:
        {json.dumps(results_summary, ensure_ascii=False, indent=2)}
        
        以下の点について言及してください：
        1. モデレーター変数の効果とその統計的有意性
        2. モデレーター変数が説明する異質性の割合（R²）
        3. 異質性の程度とその解釈
        4. 結果の臨床的・学術的意義
        5. 結果の限界と注意点
        
        学術的な文体で、簡潔かつ正確に記述してください。
        """
        
        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Gemini API呼び出し中にエラーが発生しました (interpret_meta_regression_results): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def suggest_further_analyses(data_summary, current_analysis, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """さらなる分析を提案する"""
    client = initialize_gemini_client()
    if not client:
        return None
    
    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        prompt = f"""
        あなたは医学研究と統計学の専門家です。以下のデータと現在の分析に基づいて、さらに実施すべき分析を提案してください。
        
        データの概要:
        {json.dumps(data_summary, ensure_ascii=False, indent=2)}
        
        現在の分析:
        {current_analysis}
        
        以下の点について提案してください：
        1. 追加すべきモデレーター変数
        2. 感度分析の方法
        3. サブグループ解析の可能性
        4. 出版バイアスの評価方法
        5. その他の統計的手法
        
        提案は具体的かつ実行可能なものにしてください。
        """
        
        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        return response.text
    except Exception as e:
        logger.error(f"Gemini API呼び出し中にエラーが発生しました (suggest_further_analyses): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def analyze_csv_compatibility_with_mcp_prompts(data_summary, available_prompts, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """CSV構造とMCPプロンプトを照合して実行可能な解析を判定・提案する"""
    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    logger.info(f"Starting CSV compatibility analysis with model: {model_to_use}")
    client = initialize_gemini_client()
    if not client:
        logger.error("Gemini client not initialized in analyze_csv_compatibility_with_mcp_prompts")
        return None
    
    try:
        prompt_template = """
        あなたはメタアナリシスの専門家です。以下のCSVデータ構造と利用可能な解析プロンプトを照合し、実行可能な解析を判定してください。

        CSVデータの構造:
        {data_summary_json}
        
        利用可能な解析プロンプト:
        {available_prompts_json}
        
        以下の形式でJSONレスポンスを返してください：
        {{
            "suitable_for_meta_analysis": true/false,
            "recommended_analyses": [
                {{
                    "prompt_id": "解析プロンプトのID",
                    "prompt_name": "解析プロンプトの名前",
                    "confidence": 0.0-1.0の信頼度,
                    "reason": "推奨理由"
                }}
            ],
            "missing_requirements": ["不足している要素のリスト"],
            "suggested_questions": [
                {{
                    "question": "ご希望の分析方法（例：オッズ比、ランダム効果）を教えてください。",
                    "purpose": "基本的な分析パラメータの確認",
                    "variable_names": []
                }}
            ],
            "user_message": "CSVファイルの分析が完了しました。\n研究数: {data_summary_shape_0}件\nデータ形式: {data_summary_columns_str}\n\n実行可能な分析:\n- 基本的なメタ解析（オッズ比、リスク比など）\n- サブグループ解析（追加情報が必要な場合があります）\n- メタ回帰分析（追加情報が必要な場合があります）"
        }}
        
        判定基準：
        1. データ形式（バイナリ、連続、効果量など）の適合性
        2. 必要な列の存在確認
        3. サンプルサイズの妥当性
        4. 追加分析の可能性（サブグループ、メタ回帰など）
        
        `user_message` 内の `{data_summary_shape_0}` は実際の研究数（整数）、`{data_summary_columns_str}` は実際の列名のリスト（人間が読みやすい文字列形式）に置き換えてください。
        レスポンスはJSONのみを返してください。説明文は含めないでください。
        """
        
        try:
            shape_0 = data_summary.get("shape", [0])
            shape_0_val = str(shape_0[0]) if isinstance(shape_0, (list, tuple)) and len(shape_0) > 0 else "N/A"
            
            columns_list = data_summary.get("columns", [])
            columns_str_val = ", ".join(columns_list) if columns_list else "N/A" # 人間が読みやすい形式

            prompt = prompt_template.format(
                data_summary_json=json.dumps(data_summary, ensure_ascii=False, indent=2),
                available_prompts_json=json.dumps(available_prompts, ensure_ascii=False, indent=2),
                data_summary_shape_0=shape_0_val,
                data_summary_columns_str=columns_str_val 
            )
            logger.debug(f"Generated prompt for Gemini API (analyze_csv_compatibility):\n{prompt}")

        except Exception as e_prompt:
            logger.error(f"Error during prompt generation for analyze_csv_compatibility: {e_prompt}")
            import traceback
            logger.error(traceback.format_exc())
            return None

        logger.info(f"Sending request to Gemini API with model: {model_to_use}")
        
        try:
            response = client.models.generate_content(
                model=f"models/{model_to_use}",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0)
            )
            logger.info("Successfully received response from Gemini API")
        except Exception as api_error:
            logger.error(f"Gemini API call failed: {api_error}")
            logger.error(traceback.format_exc())
            return None
        
        if not response or not hasattr(response, 'text'):
            logger.error("Gemini API returned invalid response object")
            return None
        
        response_text = response.text.strip()
        logger.info(f"Raw response length: {len(response_text)} characters")
        logger.debug(f"Raw response from Gemini API (analyze_csv_compatibility):\n{response_text}")
        
        if not response_text:
            logger.error("Gemini API returned empty response")
            return None
        
        original_text = response_text
        if response_text.startswith("```json"):
            response_text = response_text[7:]
            logger.debug("Removed ```json prefix")
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            logger.debug("Removed ``` suffix")
        
        if response_text != original_text:
            logger.debug(f"Cleaned response text:\n{response_text}")
        
        try:
            result = json.loads(response_text)
            logger.info("Successfully parsed JSON response")
            return result
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse JSON response: {json_error}")
            logger.error(f"Problematic text (first 500 chars): {response_text[:500]}")
            return None
    except Exception as e:
        logger.error(f"CSV互換性分析中にエラーが発生しました (analyze_csv_compatibility_with_mcp_prompts): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def generate_academic_writing_suggestion(results_summary, analysis_type="meta-analysis", model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """メタアナリシス結果に基づいて学術論文の書き方を提案する"""
    client = initialize_gemini_client()
    if not client:
        return None
    
    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        prompt = f"""
        あなたは医学研究と統計学の専門家です。以下のメタアナリシス結果に基づいて、学術論文の「Statistical Analysis」と「Results」セクションの統計解析部分のみを作成してください。

        結果の要約:
        {json.dumps(results_summary, ensure_ascii=False, indent=2)}

        以下の指示に従って2つのセクションを執筆してください：

        【重要な指示】
        - 提供された統計結果のみに基づいて記述
        - 研究選択や特性など、結果データに含まれない情報は記載しない
        - "statistically significant"は使用せず、数値と信頼区間で客観的に記述
        - 各セクションは英語記述後に日本語訳を併記
        - 結果のセクション書くときには、点推定値、信頼区間といっしょに、Certainty of evidenceのプレースホルダーを書く
        - **Analysis Environment:** Include the R version and metafor package version used for the analysis. This information will be provided in the `results_summary` under keys like `r_version` and `metafor_version`. If available, list them under a subheading like "Analysis Environment".

        **出力形式:**

        ## Statistical Analysis
        [実際に実行された統計手法のみを記述]

        **統計解析**
        [日本語訳]

        **Results**
        [英語の結果セクション - 点推定値と95% CIを中心に記述]

        **結果**
        [日本語訳]
        [注：ここにエビデンスの確実性評価を挿入]

        【Statistical Analysis記述内容】
        結果データから判断できる以下の項目のみ：
        - 使用された効果指標（例：risk ratio, odds ratio, mean difference）
        - 適用されたメタアナリシスモデル（fixed-effect or random-effects）
        - 異質性評価に使用された指標（I², τ², Q統計量）
        - 実行されたサブグループ解析（該当する場合のサブグループ変数）
        - 実行されたメタ回帰分析（該当する場合の共変量）
        - 実行された出版バイアス検定（該当する場合）
        - 実行された感度分析（該当する場合）


        【Results記述内容】
        実際の数値結果のみ：
        - **Overall analysis:** 統合効果推定値と95%信頼区間、p値
        - **Heterogeneity:** I²値[95%CI]、τ²値、Q統計量（自由度、p値）
        - **Subgroup analysis (if performed):** 
        - 各サブグループの効果推定値と95%信頼区間
        - サブグループごとの異質性指標（I², τ²）
        - サブグループ間検定結果（QM統計量、自由度、p値）
        - **Meta-regression (if performed):**
        - 回帰係数、標準誤差、95%信頼区間、p値
        - 説明された異質性割合（R²）
        - 残差異質性（I²_res, τ²_res）
        - **Publication bias (if assessed):** 検定統計量とp値
        - 図についても言及（例：フォレストプロット、ファンネルプロット）
        - 実行された感度分析
        - **Analysis Environment:** R version (e.g., R version 4.4.0 (2024-04-24 ucrt)) and metafor package version (e.g., metafor version 4.0-0). This should be mentioned at the end of the results or in a dedicated "Methods" or "Analysis Environment" section if appropriate for the context.
        - [Note: Certainty of evidence assessment would be inserted here]

        【記述スタイル】
        - 数値は適切な精度で報告（小数点以下2-3桁）
        - 効果の方向性を明示（どちらのグループの値が高い/低いか）
        - 信頼区間とp値を併記
        - 客観的・記述的表現を使用

        結果データに基づいて判断できる統計手法と数値結果のみを記述してください。

        国際的な医学雑誌の投稿基準（ICMJE）に準拠し、簡潔かつ正確に記述してください。
        """
        
        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        return response.text
    except Exception as e:
        logger.error(f"学術論文の書き方提案生成中にエラーが発生しました: {e}")
        logger.error(traceback.format_exc()) # Added traceback
        return None

# Function Declaration for extract_parameters_from_user_input
extract_analysis_params_function = {
    "name": "extract_analysis_parameters",
    "description": "ユーザーのテキスト入力からメタアナリシスのパラメータを抽出します。効果量、モデルタイプ、サブグループ列、モデレーター列、および効果量計算に必要なデータ列のマッピングを識別します。",
    "parameters": {
        "type": "object",
        "properties": {
            "effect_size": {
                "type": "string",
                "description": "分析に使用する効果量。ユーザーが「オッズ比」と言えば'OR'と解釈します。「リスク差」は'RD'と解釈します。「ハザード比」あるいはhrは'HR'と解釈します。その他の効果量も同様に解釈します。",
                "enum": ["OR", "RR", "RD", "HR", "SMD", "MD", "COR", "proportion", "IR", "PETO", "ROM", "yi", "RD"]
            },
            "model_type": {
                "type": "string",
                "description": "メタアナリシスのモデルタイプ。",
                "enum": ["fixed", "random"]
            },
            "subgroup_columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "サブグループ解析に使用するCSVファイル内の列名リスト。指定がない場合は空のリスト。"
            },
            "moderator_columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "メタ回帰分析に使用するCSVファイル内の共変量の列名リスト。指定がない場合は空のリスト。"
            },
            "data_columns": {
                "type": "object",
                "description": "効果量計算に必要なCSVファイル内の列と、それに対応する標準的な役割（ai, bi, ci, diなど）とのマッピング。指定がない場合はnullまたは空のオブジェクト。",
                "properties": {
                    "study_label_author": {"type": "string", "description": "研究の著者名を示す列名 (任意)"},
                    "study_label_year": {"type": "string", "description": "研究の発表年を示す列名 (任意)"},
                    "study_label": {"type": "string", "description": "研究のユニークなラベルを示す列名 (任意)"},
                    "ai": {"type": "string", "description": "治療群のイベント数を示す列名"},
                    "bi": {"type": "string", "description": "治療群の非イベント数または総数からイベント数を引いたものを示す列名 (n1iとaiが利用可能な場合は不要。ORの場合も同様)"},
                    "ci": {"type": "string", "description": "対照群のイベント数を示す列名"},
                    "di": {"type": "string", "description": "対照群の非イベント数または総数からイベント数を引いたものを示す列名 (n2iとciが利用可能な場合は不要。ORの場合も同様)"},
                    "n1i": {"type": "string", "description": "治療群のサンプルサイズを示す列名"},
                    "n2i": {"type": "string", "description": "対照群のサンプルサイズを示す列名"},
                    "m1i": {"type": "string", "description": "治療群の平均値を示す列名"},
                    "m2i": {"type": "string", "description": "対照群の平均値を示す列名"},
                    "sd1i": {"type": "string", "description": "治療群の標準偏差を示す列名"},
                    "sd2i": {"type": "string", "description": "対照群の標準偏差を示す列名"},
                    "proportion_events": {"type": "string", "description": "割合計算のためのイベント数を示す列名"},
                    "proportion_total": {"type": "string", "description": "割合計算のための総数を示す列名"},
                    "proportion_time": {"type": "string", "description": "発生率計算のための追跡時間または期間を示す列名 (IRの場合)"},
                    "yi": {"type": "string", "description": "事前計算された効果量を示す列名"},
                    "vi": {"type": "string", "description": "事前計算された効果量の分散を示す列名"}
                },
                # additionalProperties を削除 (Pydantic v2 / google-generativeai ライブラリの挙動に合わせる)
            },
            "sensitivity_variable": {
                "type": "string",
                "description": "感度分析で使用するCSVファイル内の変数名。指定がない場合はnull。"
            },
            "sensitivity_value": {
                "type": "string",
                "description": "感度分析で限定対象となる値。指定がない場合はnull。"
            }
        },
    }
}

# 新しいFunction Callingの定義
map_csv_columns_to_meta_analysis_roles_function = {
    "name": "map_csv_columns_to_meta_analysis_roles",
    "description": "CSVファイルの列名とサンプルデータに基づいて、メタアナリシスで必要とされる役割マッピング、効果量、データ形式、サブグループ・モデレーター候補を返します。",
    "parameters": {
        "type": "object",
        "properties": {
            "target_role_mappings": {
                "type": "object",
                "description": "メタアナリシスの役割（ai, bi, ci, di等）とCSV列名のマッピング。該当する列がない場合は空のオブジェクトまたはキーに対応する値がnullになります。"
            },
            "suggested_subgroup_candidates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "サブグループ分析の候補となるCSV列名のリスト。候補がない場合は空のリスト。"
            },
            "suggested_moderator_candidates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "メタ回帰分析のモデレーター候補となるCSV列名のリスト。候補がない場合は空のリスト。"
            },
            "detected_effect_size": {
                "type": "string",
                "description": "列名パターンから検出された効果量のタイプ（例: OR, RR, RD, HR, SMD, MD, yi）。不明な場合はnull。",
                "enum": ["OR", "RR", "RD", "HR", "SMD", "MD", "COR", "proportion", "IR", "PETO", "ROM", "yi", "RD", None]
            },
            "is_log_transformed": {
                "type": "boolean",
                "description": "検出された効果量が対数変換されているか（例: log_hr, ln_or）。不明な場合はnull。"
            },
            "data_format": {
                "type": "string",
                "description": "検出されたデータ形式（例: 2x2_table, pre_calculated）。OR/RRの場合に特に重要。不明な場合はnull。",
                "enum": ["2x2_table", "pre_calculated", "mixed", None]
            },
            "detected_columns": {
                "type": "object",
                "description": "効果量計算やデータ形式判断に利用された主要な列とその役割のサマリー（例: {'log_hr': 'yi', 'se_log_hr': 'vi'} または {'events_treatment': 'ai', ...}）。"
                # additionalProperties: true を想定
            }
        },
        "required": ["target_role_mappings"]
    }
}

def extract_parameters_from_user_input(
    user_input: str, 
    data_summary: dict, 
    conversation_history: List[Dict] = None,
    collection_context: Dict = None,
    model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest") # BOM除去
):
    """ユーザーの入力からメタアナリシスのパラメータを抽出する (Function Calling版)"""
    client = initialize_gemini_client()
    if not client:
        logger.error("Gemini client not initialized in extract_parameters_from_user_input")
        return None

    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        logger.info(f"Sending request to Gemini API for parameter extraction (Function Calling). User input: '{user_input}'")
        
        tool = types.Tool(function_declarations=[extract_analysis_params_function])
        
        prompt_parts = [
            "あなたはメタアナリシスのパラメータ収集を支援しています。",
            "以下の会話履歴、現在の収集状況、データ概要を考慮して、ユーザーの最新の回答からメタアナリシスのパラメータを抽出してください。"
        ]

        if conversation_history:
            history_str = "\n".join([f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}" for msg in conversation_history])
            prompt_parts.append(f"\n会話履歴:\n{history_str}")

        if collection_context:
            prompt_parts.append(f"\n現在のパラメータ収集状況:\n{json.dumps(collection_context, ensure_ascii=False, indent=2)}")
        
        prompt_parts.append(f"\nCSVデータの概要:\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}")
        prompt_parts.append(f"\nユーザーの最新の回答: \"{user_input}\"")
        
        prompt_parts.append("\n抽出するパラメータは以下の通りです:")
        prompt_parts.append("- effect_size (効果量): OR, RR, SMDなど")
        prompt_parts.append("- model_type (モデルタイプ): fixed, random")
        prompt_parts.append("- subgroup_columns (サブグループ解析列): CSV列名のリスト")
        prompt_parts.append("- moderator_columns (メタ回帰列): CSV列名のリスト")
        prompt_parts.append("- data_columns (効果量計算用列マッピング): ai, bi, ci, diなどとCSV列名のマッピング")

        prompt_parts.append("\n【「はい」「いいえ」の解釈に関する重要指示】")
        prompt_parts.append("- ユーザーの最新の回答が「はい」または「いいえ」（あるいはそれに類する短い肯定/否定）のみである場合、それは会話履歴における直前のボットの質問（`collection_context` の `last_bot_question` を参照）に対する応答であると強く推測されます。")
        prompt_parts.append("- その場合、ボットの質問の意図（例：特定の解析を行わないことの確認、特定の効果量で進めることの確認など）を正確に理解してください。")
        prompt_parts.append("- もし、ボットの質問が単なる確認であり、ユーザーの「はい」という応答から新たに抽出・設定すべきパラメータがない場合は、Function Callingの `extracted_params` として空のオブジェクト `{}` を返してください。")
        prompt_parts.append("- 同様に、「いいえ」という応答で、それが特定のパラメータ設定を拒否する意図であれば、該当するパラメータを抽出しないか、あるいは以前の設定を取り消すような解釈を試みてください（ただし、Function Callingのスキーマ内で表現できる範囲で）。")
        prompt_parts.append("- ユーザーの意図を誤解釈して、無関係なパラメータを無理に抽出しようとしたり、必須パラメータが不足していると誤判断したりしないでください。")
        
        prompt_parts.append("\n【重要】パラメータ抽出のヒント:")
        prompt_parts.append("1. ユーザーの最新の回答は、`collection_context` 内の `last_bot_question`（ボットが最後にした質問）に対するものである可能性が高いです。")
        prompt_parts.append("2. `last_bot_question` が `collection_context` 内の `current_question_target`（その質問が収集しようとしていたパラメータ種別）に関連する場合、ユーザーの回答をそのパラメータ種別（例: `subgroup_columns`, `moderator_columns`, `effect_size` など）として優先的に解釈してください。")
        prompt_parts.append("3. 例えば、`last_bot_question` が「サブグループ解析に使用する変数は何ですか？」で、`current_question_target` が `subgroup_columns` の場合、ユーザーが列名を挙げれば、それらを `subgroup_columns` に割り当ててください。")
        prompt_parts.append("4. ユーザーは必ずしも直前の質問にだけ答えているとは限りません。会話の流れ全体と、`collection_context` で示される収集の全体像を考慮して、最も適切な解釈をしてください。")
        prompt_parts.append("5. ユーザーが複数のパラメータ（例: 効果量とモデルタイプ）を一度に指定することもあります。")

        enriched_user_input = "\n".join(prompt_parts)
        
        logger.debug(f"Enriched input for Gemini parameter extraction:\n{enriched_user_input}")

        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY" 
            )
        )
        
        gen_config = types.GenerateContentConfig(
            tools=[tool],
            tool_config=tool_config,
            temperature=0
        )

        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=enriched_user_input,
            config=gen_config
        )
        
        if not response or not response.candidates:
            logger.error("Gemini API returned invalid or empty response for parameter extraction (Function Calling).")
            return None

        function_call_part = None
        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_call_part = part
                break
        
        if function_call_part and function_call_part.function_call.name == "extract_analysis_parameters":
            extracted_args = dict(function_call_part.function_call.args)
            logger.info(f"Successfully extracted parameters via Function Calling: {extracted_args}")
            return {"extracted_params": extracted_args}
        else:
            logger.warning(f"No function call 'extract_analysis_parameters' found in Gemini response. Response parts: {response.candidates[0].content.parts}")
            return None
        
    except Exception as e:
        logger.error(f"Error during parameter extraction with Gemini (Function Calling): {e}")
        logger.error(traceback.format_exc())
        return None

def map_csv_columns_to_meta_analysis_roles(csv_columns: List[str], csv_sample_data: List[Dict[str, Any]], target_roles: List[str], model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """
    CSVの列名とサンプルデータに基づいて、メタアナリシスで必要とされる役割をGeminiにマッピングさせる。
    """
    client = initialize_gemini_client()
    if not client:
        logger.error("Gemini client not initialized in map_csv_columns_to_meta_analysis_roles")
        return None

    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        logger.info(f"Sending request to Gemini API for column mapping (Function Calling). Target roles: {target_roles}")
        
        tool = types.Tool(function_declarations=[map_csv_columns_to_meta_analysis_roles_function])
        
        # プロンプトでGeminiに指示を与える
        prompt_content = (
            f"あなたはメタアナリシスの専門家です。\n"
            f"以下のCSV列名とサンプルデータ、そしてメタアナリシスで必要とされる役割のリスト（target_roles）を考慮して、各役割に最も適切なCSV列名をマッピングしてください。\n"
            f"`target_role_mappings`オブジェクトには、'ai', 'bi', 'ci', 'di', 'n1i', 'n2i', 'm1i', 'm2i', 'sd1i', 'sd2i', 'yi', 'vi', 'study_label'などのキーと、それに対応するCSV列名を動的に含めてください。\n"
            f"さらに、target_rolesに明示的に指定されていない列であっても、その特性（データ型、カテゴリ数、欠損値の割合など）からサブグループ分析の候補となりうる列、およびメタ回帰分析のモデレーター候補となりうる列を積極的に特定し、それぞれ`suggested_subgroup_candidates`と`suggested_moderator_candidates`として提案してください。\n"
            f"また、列名パターンから効果量のタイプとデータ形式を自動検出し、`detected_effect_size`、`is_log_transformed`、`data_format`として返してください。\n\n"
            f"CSV列名: {json.dumps(csv_columns, ensure_ascii=False)}\n"
            f"CSVサンプルデータ (最初の数行): {json.dumps(csv_sample_data, ensure_ascii=False, indent=2)}\n"
            f"ターゲット役割: {json.dumps(target_roles, ensure_ascii=False)}\n\n"
            f"【効果量の自動検出と役割マッピングの最優先ルール】\n"
            f"CSV列に `log_hr` (または類似の対数ハザード比を示す列名、例: `log_hazard_ratio`, `ln_hr`) と `se_log_hr` (または類似の標準誤差を示す列名、例: `se_log_hazard_ratio`, `seloghr`) のペアが存在する場合、**必ず**以下の通りに検出・マッピングしてください。これは他のどのルールよりも優先されます:\n"
            f"  - `detected_effect_size`: \"HR\"\n"
            f"  - `is_log_transformed`: true\n"
            f"  - `data_format`: \"pre_calculated\"\n"
            f"  - `target_role_mappings` 内で、`log_hr` に対応するCSV列名を `yi` に、`se_log_hr` に対応するCSV列名を `vi` にマッピングしてください。\n"
            f"  - `detected_columns` にもこのマッピング (`{{'CSV列名_log_hr': 'yi', 'CSV列名_se_log_hr': 'vi'}}` の形式で) を含めてください。\n\n"
            f"【その他の効果量の自動検出ルール】\n"
            f"上記以外の場合、以下の列名パターンから効果量を検出してください:\n"
            f"- 'log_or', 'ln_or', 'logodds', 'log_odds_ratio' → OR（対数変換済み）\n"
            f"- 'or', 'odds_ratio' → OR（元のスケール）\n"
            f"- 'log_rr', 'ln_rr', 'logrisk', 'log_risk_ratio' → RR（対数変換済み）\n"
            f"- 'rr', 'risk_ratio' → RR（元のスケール）\n"
            f"- 'yi', 'effect_size', 'es' → yi（事前計算済み効果量）\n"
            f"- 'smd', 'standardized_mean_diff' → SMD\n"
            f"- 'md', 'mean_diff' → MD\n\n"
            f"【データ形式の検出ルール】\n"
            f"上記最優先ルールに該当しない場合:\n"
            f"- 2×2表形式: 'ai', 'bi', 'ci', 'di' または 'events_treatment', 'events_control' などの列がある場合。\n"
            f"- 事前計算形式: 'yi' と 'vi' (または 'effect_size' と 'variance'/'standard_error') のように、効果量とその標準誤差（または分散）のペアを示す列が存在する場合。\n"
            f"- mixed: 両方の形式の列が混在している場合。\n\n"
            f"【重要な役割マッピングルール】\n"
            f"上記最優先ルールに該当しない場合、以下の一般的な列名パターンに基づいてマッピングしてください:\n"
            f"- 'events_treatment', 'treatment_events' → 'ai' (治療群のイベント数)\n"
            f"- 'total_treatment', 'treatment_total', 'n_treatment' → 'n1i' (治療群の総数)\n"
            f"- 'events_control', 'control_events' → 'ci' (対照群のイベント数)\n"
            f"- 'total_control', 'control_total', 'n_control' → 'n2i' (対照群の総数)\n"
            f"- 'events_experimental' → 'ai' (実験群のイベント数)\n"
            f"- 'total_experimental' → 'n1i' (実験群の総数)\n\n"
            f"【役割マッピングのヒント】\n"
            f"- **最優先事項:** CSV列名に 'Study', 'study', 'STUDY', 'study_id', 'StudyID', 'study_name', 'StudyName', 'Author', 'author' のような、研究や論文を一意に識別する可能性のある単一の列が存在する場合、それを `study_label` の役割にマッピングしてください。この単一の `study_label` が見つかった場合、`study_label_author` や `study_label_year` の個別マッピングは不要です。もし適切な単一の `study_label` が見つからない場合に限り、`study_label_author` と `study_label_year` の組み合わせによるラベル生成を検討してください。\n"
            f"- 'study_id'や'author'のような研究識別子は、ユニークな値が多い文字列型の列が該当しやすいです。\n"
            f"- 'publication_year'は年を表す数値型の列が該当します。\n"
            f"- 'events_treatment', 'total_treatment', 'events_control', 'total_control' は、イベント数や総数を表す整数型の列が該当します。\n"
            f"- 'mean_age'のような連続尺度のモデレーターは数値型の列が該当します。\n"
            f"- 'region'のようなカテゴリカルなサブグループ変数は、カテゴリ数が適度（例：2～10程度）な文字列型または因子型の列が該当しやすいです。\n\n"
            f"【サブグループ・モデレーター候補の選定基準】\n"
            f"- サブグループ候補: 主にカテゴリカルなデータ（文字列型でユニークな値が少ない、または数値型でも離散的な値を取るもの）。ただし、連続尺度のデータをカテゴリ化してサブグループとすることも考慮できます。\n"
            f"- モデレーター候補: 主に数値型の連続データ、または順序のあるカテゴリカルデータ。二値変数もモデレーターになりえます。\n"
            f"- 候補を選定する際には、その列が研究間の異質性を説明しうるかどうかを考慮してください。\n"
            f"- **重要**: `suggested_subgroup_candidates` および `suggested_moderator_candidates` について、適切な候補が見つからない場合は、必ず空の配列 `[]` を返してください。\n\n"
            f"最終的な出力は、指定されたFunction Callingのスキーマに従ってください。"
        )

        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY" 
            )
        )
        
        gen_config = types.GenerateContentConfig(
            tools=[tool],
            tool_config=tool_config,
            temperature=0
        )

        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt_content,
            config=gen_config
        )
        
        if not response or not response.candidates:
            logger.error("Gemini API returned invalid or empty response for column mapping (Function Calling).")
            return None

        function_call_part = None
        for part in response.candidates[0].content.parts:
            if part.function_call:
                function_call_part = part
                break
        
        if function_call_part and function_call_part.function_call.name == "map_csv_columns_to_meta_analysis_roles":
            mapped_args = dict(function_call_part.function_call.args)
            # 候補が存在しない場合に備えてデフォルト値を設定
            mapped_args.setdefault("suggested_subgroup_candidates", [])
            mapped_args.setdefault("suggested_moderator_candidates", [])
            logger.info(f"Successfully mapped columns via Function Calling: {json.dumps(mapped_args, ensure_ascii=False)}") # DEBUG LOG
            return {"mapped_columns": mapped_args}
        else:
            logger.warning(f"No function call 'map_csv_columns_to_meta_analysis_roles' found in Gemini response. Response parts: {response.candidates[0].content.parts}")
            return None
        
    except Exception as e:
        logger.error(f"Error during column mapping with Gemini (Function Calling): {e}")
        logger.error(traceback.format_exc())
        return None

def analyze_user_response_for_analysis_selection(user_response, gemini_questions, recommended_analyses, data_summary, is_initial_response=True, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # model to model_name, BOM除去
    """ユーザーの回答を解析して適切な分析手法を選択する (簡略化または新しいロジックに置き換えられることを想定)"""
    client = initialize_gemini_client()
    if not client:
        return None
    
    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        if is_initial_response:
            prompt = f"""
            あなたはメタアナリシスの専門家です。ユーザーの初回回答を解析し、最適な分析手法を特定してください。
            【重要】初回応答では、必ずデータの内容について確認メッセージを返し、needs_clarificationをtrueにしてください。
            森林プロットとは呼ばず、フォレストプロットと呼んでください。
            同様に、ファンネルプロットと呼んでください。

            データの概要:
            {json.dumps(data_summary, ensure_ascii=False, indent=2)}
            
            事前に提案した質問:
            {json.dumps(gemini_questions, ensure_ascii=False, indent=2)}
            
            推奨分析手法:
            {json.dumps(recommended_analyses, ensure_ascii=False, indent=2)}
            
            ユーザーの回答:
            "{user_response}"
            
            以下の形式でJSONレスポンスを返してください：
            {{
                "selected_analysis": {{
                    "prompt_id": "選択された分析のプロンプトID",
                    "prompt_name": "分析名",
                    "confidence": 0.0-1.0の信頼度,
                    "reason": "選択理由"
                }},
                "parameters": {{
                    "analysis_type": "分析タイプ",
                    "model_type": "fixed または random",
                    "subgroup_column": "サブグループ列名（該当する場合）",
                    "moderator_columns": ["モデレーター変数のリスト"]
                }},
                "user_message": "ユーザーへの詳細な確認メッセージ（データの解釈と選択した分析手法について）",
                "needs_clarification": true,
                "clarification_questions": ["この内容でよろしいでしょうか？"],
                "is_ready_to_execute": false
            }}
            
            【必須】初回応答では必ず：
            1. ユーザーの回答から分析手法を特定
            2. データの解釈と選択理由を含む詳細な確認メッセージを作成
            3. needs_clarificationをtrueに設定
            4. is_ready_to_executeをfalseに設定
            
            レスポンスはJSONのみを返してください。説明文は含めないでください。
            """
        else:
            prompt = f"""
            あなたはメタアナリシスの専門家です。ユーザーの追加回答を解析し、分析実行の準備が整ったかを判断してください。

            データの概要:
            {json.dumps(data_summary, ensure_ascii=False, indent=2)}
            
            推奨分析手法:
            {json.dumps(recommended_analyses, ensure_ascii=False, indent=2)}
            
            ユーザーの回答:
            "{user_response}"
            
            以下の形式でJSONレスポンスを返してください：
            {{
                "selected_analysis": {{
                    "prompt_id": "選択された分析のプロンプトID",
                    "prompt_name": "分析名",
                    "confidence": 0.0-1.0の信頼度,
                    "reason": "選択理由"
                }},
                "parameters": {{
                    "analysis_type": "分析タイプ",
                    "model_type": "fixed または random",
                    "subgroup_column": "サブグループ列名（該当する場合）",
                    "moderator_columns": ["モデレーター変数のリスト"]
                }},
                "user_message": "ユーザーへのメッセージ",
                "needs_clarification": true/false,
                "clarification_questions": ["追加で必要な質問のリスト（該当する場合）"],
                "is_ready_to_execute": true/false
            }}
            
            判定基準：
            1. ユーザーが「はい」「よろしい」「開始してください」等の肯定的回答をした場合：needs_clarification=false, is_ready_to_execute=true
            2. ユーザーが具体的な分析パラメータ（例：「ランダム効果、オッズ比」、「固定効果、リスク比、サブグループはX列」など）を指定した場合：
               - 指定されたパラメータを "parameters" に正確にマッピングしてください。
               - "selected_analysis" は、指定されたパラメータと "recommended_analyses" を照合して最も適切なものを選択してください。もし明確に一致するものがなければ、基本的なメタアナリシス（例：prompt_id: "meta_analysis_basic"）を選択してください。
               - needs_clarification=false, is_ready_to_execute=true と設定してください。
               - "user_message" には、指定されたパラメータで分析を開始することを確認するメッセージを含めてください。
            3. 追加の情報や変更が必要な場合（上記1, 2以外）：needs_clarification=true, is_ready_to_execute=false
            4. user_messageは実行開始または追加質問に応じた内容にする
            
            レスポンスはJSONのみを返してください。説明文は含めないでください。
            """
        
        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"ユーザー回答解析中にエラーが発生しました: {e}")
        logger.error(traceback.format_exc()) # Added traceback
        return None

def generate_r_script_with_gemini(data_summary, analysis_preferences, template_info, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # model to model_name, BOM除去
    """Gemini APIを使用してRスクリプトを生成する"""
    client = initialize_gemini_client()
    if not client:
        logger.warning("Geminiクライアントが初期化されていません。Rスクリプトを生成できません。")
        return None

    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        actual_columns = data_summary.get("columns", [])
        data_head_sample = data_summary.get("head", []) 

        analysis_type = analysis_preferences.get("analysis_type", template_info.get("id", "meta_analysis_basic"))
        measure = analysis_preferences.get("measure") 
        effect_size_placeholder = measure if measure else analysis_preferences.get("effect_size_from_extract_params", "未指定")
        
        escalc_columns_placeholder = template_info.get("required_columns", [])
        if isinstance(escalc_columns_placeholder, list):
            escalc_columns_placeholder_str = ", ".join(escalc_columns_placeholder)
        else:
            escalc_columns_placeholder_str = str(escalc_columns_placeholder)

        subgroup_column_name_placeholder = analysis_preferences.get("subgroup_column", "未指定")
        model_type_placeholder = analysis_preferences.get("model_type", "未指定")
        forest_plot_path_placeholder = analysis_preferences.get("forest_plot_path", "forest.png")
        funnel_plot_path_placeholder = analysis_preferences.get("funnel_plot_path", "funnel.png")
        rdata_path_placeholder = analysis_preferences.get("result_data_path", "result.RData")
        json_summary_path_placeholder = analysis_preferences.get("json_summary_path", "summary.json")


        prompt_instruction = f"""
        あなたは、R言語とメタアナリシス、特に 'metafor' パッケージに非常に詳しい専門家です。
        ユーザーの要求に基づいて、高品質で実行可能なRスクリプトを生成してください。

        ユーザーの要求は以下の通りです。
        - 分析タイプ: {analysis_type}
        - 効果量: {effect_size_placeholder}
        - 効果量の計算に必要な列名 (ai, bi, ci, di または n1i, n2i など): {escalc_columns_placeholder_str}
        - サブグループ化に使用する列名: {subgroup_column_name_placeholder}
        - モデレーター変数(複数可): {analysis_preferences.get("moderator_columns", [])}
        - モデルタイプ: {model_type_placeholder}
        - 入力CSVファイルパス: {{csv_file_path}} (注意: Rスクリプト内では 'dat' というデータフレーム名で扱います)
        - 出力フォレストプロットパス: {forest_plot_path_placeholder}
        - 出力ファンネルプロットパス: {funnel_plot_path_placeholder}
        - 出力バブルプロットパスのプレフィックス (モデレーター変数ごとに生成する場合): bubble_plot_ (例: bubble_plot_year.png)
        - 出力RDataパス: {rdata_path_placeholder}
        - 出力JSONサマリーパス: {json_summary_path_placeholder}
        
        CSVデータの列名: {json.dumps(actual_columns, ensure_ascii=False)}
        CSVデータの最初の5行のサンプル: {json.dumps(data_head_sample, ensure_ascii=False, indent=2)}

        生成するRスクリプトは、以下の手順とベストプラクティスに従ってください。

        1.  **ライブラリのロード**:
            *   `metafor` パッケージをロードしてください。
            *   JSON出力のために `jsonlite` パッケージをロードしてください（存在確認と条件付きインストールは不要です。環境にプリインストールされている前提とします）。

        2.  **データの読み込み**:
            *   スクリプトの前提として、データは既に `dat` という名前のデータフレームに読み込まれているものとします。`dat <- read.csv(...)` のようなコードは含めないでください。

        3.  **効果量の計算**:
            *   `escalc()` 関数を使用し、指定された効果量 (`{effect_size_placeholder}`) と関連列 (`{escalc_columns_placeholder_str}`) を用いて、効果量 (`yi`) とその分散 (`vi`) を計算してください。
            *   研究ラベルを `slab` 引数で適切に設定してください（例: `paste(author, year, sep=", ")`、もし解析に使用しない `author` や `year`などの列が存在すれば）。存在しない場合は `slab` の設定は不要です。

        4.  **全体のメタアナリシス (およびメタ回帰/サブグループモデレーション)**:
            *   `rma()` 関数を使用し、計算した `yi` と `vi` を用いてメタアナリシスを実行してください。
            *   モデルは `{model_type_placeholder}` を使用してください (例: "REML", "FE")。
            *   もし `{analysis_preferences.get("moderator_columns", [])}` が空でなく、かつ `{subgroup_column_name_placeholder}` が "指定" されている場合、`mods = ~ {analysis_preferences.get("moderator_columns", [])[0]} + factor({subgroup_column_name_placeholder})` のように、最初のモデレーターとサブグループ変数を同時にモデルに含めることを検討してください。ただし、通常はメタ回帰とサブグループの差の検定は別々に行います。
            *   **優先順位**:
                *   もし `{analysis_preferences.get("moderator_columns", [])}` が空でなければ、`mods = ~ { " + ".join(analysis_preferences.get("moderator_columns", [])) }` のようにメタ回帰モデルを構築してください。結果は `res.mods` (または単に `res` で上書きも可) に格納してください。
                *   もし `{analysis_preferences.get("moderator_columns", [])}` が空で、かつ `{subgroup_column_name_placeholder}` が "指定" されている場合、`mods = ~ factor({subgroup_column_name_placeholder})` としてサブグループ間の差を検定するモデルを構築してください。結果は `res.subgroup.mods` (または `res` で上書き) に格納してください。
                *   上記以外の場合は、`mods`なしで基本的なメタアナリシスを実行してください。
            *   基本的な全体のメタアナリシス結果は常に `res` という変数に格納してください（モデレーターやサブグループ指定がない場合、またはそれらとは別に全体の結果も必要な場合）。

        5.  **フォレストプロットの作成 (metafor標準関数を使用)**:
            *   **ggplot2 は使用しないでください。** `metafor` パッケージの `forest()` 関数と `addpoly()` 関数を組み合わせて使用してください。
            *   まず、全体のメタアナリシス結果 (`res`) を用いて `forest()` 関数で基本的なフォレストプロットを描画し、`{forest_plot_path_placeholder}` に保存してください。
                *   `xlim`, `at`, `atransf=exp` (または適切な変換) を効果量に応じて設定してください。
                *   `ilab` 引数などを使用して、元データからの追加情報（例: 各群のイベント数/総数）を表示することを検討してください。
                *   `mlabfun` のようなヘルパー関数を定義し、Q統計量、I^2統計量、τ^2統計量などをプロット上に表示してください。
                *   `header` 引数や `text()` 関数で見出しや列名を追加してください。
            *   もし `{subgroup_column_name_placeholder}` が "指定" されている場合、その列の各水準について、`subset` 引数を用いて `rma()` 関数を実行し、サブグループごとのメタアナリシス結果を取得してください。
            *   `addpoly()` 関数を使用して、各サブグループの統合推定値を既存のフォレストプロットに追加してください。ここでも `mlabfun` を活用してください。
            *   プロットの行 (`rows` 引数) や `ylim` を適切に調整し、全体の結果とサブグループの結果が見やすいように配置してください。
            *   `par(cex=...)` などでフォントサイズを調整することも考慮してください。
            *   もし `{subgroup_column_name_placeholder}` が "指定" されている場合、サブグループ間の差の検定結果 (`res.subgroup.mods` などを使用) を、`text()` 関数や `bquote()` を使ってフォレストプロットの下部などに追加してください。

        6.  **ファンネルプロットの作成 (オプション)**:
            *   もしファンネルプロットが必要な場合 (`{funnel_plot_path_placeholder}` が指定されている場合)、全体のメタアナリシス結果 (`res`) を用いて `funnel()` 関数でファンネルプロットを作成し、`{funnel_plot_path_placeholder}` に保存してください。
            *   Egger's test (`regtest(res)`) の結果を `res$egger_test` のように `res` オブジェクトに含めてください。

        7.  **メタ回帰のバブルプロット作成 (メタ回帰分析の場合のみ)**:
            *   もし `{analysis_preferences.get("moderator_columns", [])}` が空でない場合:
                *   指定された各モデレーター変数（例: `mod_var`）について、`metafor::regplot(res.mods, mod=mod_var, ...)` (または `res` がメタ回帰モデルの結果を保持している場合は `regplot(res, mod=mod_var, ...)` ) を使用して個別のバブルプロットを作成してください。
                *   各バブルプロットのファイル名は、`paste0("bubble_plot_", gsub("[^[:alnum:]_]", "_", tolower(mod_var)), ".png")` のように、モデレーター変数名をファイル名に適した英語の識別子（小文字化し、英数字とアンダースコア以外をアンダースコアに置換）にして生成してください。
                *   生成した各バブルプロットを、対応するファイルパスに保存してください。

        8.  **結果の保存**:
            *   主要な結果オブジェクト（`res`、存在すれば `res.mods` や `res.subgroup.mods`、`subgroup_results_list`、`egger_test_res` など）を `{rdata_path_placeholder}` に `save()` 関数で保存してください。
            *   **JSONサマリーの出力 (最重要)**:
                *   メタアナリシスの主要な結果（全体の統合効果量、信頼区間、p値、I^2、τ^2、Q統計量、Qのp値、研究数k。もしサブグループ解析があれば、各サブグループの同様の統計量、サブグループ間差の検定結果QMとp値など。メタ回帰があれば、各モデレーターの係数、p値、残差異質性など。Egger's testの結果）を **`summary_list` という名前の構造化されたRのリスト** にまとめてください。
                *   **生成された全てのプロットファイルの情報を、`generated_plots_list` という名前の別のRリスト** にまとめてください。各要素は `list(label = "プロットの英語識別子", path = "実際のファイルパス")` という形式の名前付きリストであるべきです。
                    *   例: `generated_plots_list <- list()`
                    *   `generated_plots_list[[length(generated_plots_list) + 1]] <- list(label = "forest_plot", path = "{forest_plot_path_placeholder}")`
                    *   ファンネルプロットや各バブルプロットも同様に、実際に生成されたファイルパスと共にこのリストに追加してください。ラベルは `"funnel_plot"`, `"bubble_plot_publication_year"` のようにしてください。
                *   `summary_list` に、この `generated_plots_list` を `generated_plots` というキーで含めてください。
                *   この **`summary_list` のみを** `jsonlite::toJSON()` を使ってJSON文字列に変換し、**必ず `{json_summary_path_placeholder}` (これは "summary.json" というファイル名を指します) というパスに書き出してください。** `auto_unbox = TRUE`, `pretty = TRUE`, `null = "null"` オプションを使用してください。
                *   **JSON出力の期待構造例 (generated_plots を含む)**:
                    ```json
                    {{
                      "overall_analysis": {{ ... }},
                      "subgroup_analyses": [ ... ], // サブグループ解析がある場合のみ
                      "subgroup_moderation_test": {{ ... }}, // サブグループ解析がある場合のみ
                      "meta_regression_results": {{ // メタ回帰がある場合のみ
                        "moderators": [ {{ "name": "year", "estimate": ..., "pval": ... }}, ... ],
                        "residual_I2": ..., "R2_accounted": ...
                      }},
                      "egger_test": {{ ... }},
                      "generated_plots": [
                        {{ "label": "forest_plot", "path": "{forest_plot_path_placeholder}" }},
                        {{ "label": "funnel_plot", "path": "{funnel_plot_path_placeholder}" }},
                        {{ "label": "bubble_plot_year", "path": "bubble_plot_year.png" }}
                      ]
                    }}
                    ```

        9.  **エラーハンドリング**:
            *   基本的なエラーハンドリングはRスクリプト内では最小限とし、Python側で実行時エラーを捕捉することを想定してください。

        生成されるRスクリプトは、上記の指示に厳密に従い、冗長なコメントや不要な処理を含まない、クリーンで効率的なものであるべきです。
        特に、フォレストプロットは提示されたコードスニペット（`dat.bcg` の例）のスタイルを強く参考にしてください。
        スクリプト内で `R` という名前の変数やオブジェクトを絶対に使用しないでください。
        R/nlibraryという間に改行が入った単語も使ってはいけません。
        """
        
        logger.info(f"Gemini Rスクリプト生成プロンプト:\n{prompt_instruction}")

        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt_instruction,
            config=types.GenerateContentConfig(temperature=0)
        )
        
        r_script_code = response.text.strip()
        if r_script_code.startswith("```r"):
            r_script_code = r_script_code[4:]
        elif r_script_code.startswith("```"):
            r_script_code = r_script_code[3:]
        if r_script_code.endswith("```"):
            r_script_code = r_script_code[:-3]
        
        logger.info(f"Geminiによって生成されたRスクリプト:\n{r_script_code}")
        return r_script_code

    except Exception as e:
        logger.error(f"Gemini Rスクリプト生成中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def detect_reanalysis_intent(user_message: str, previous_analysis: dict, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # model to model_name, BOM除去
    """ユーザーのメッセージが再分析の要求かどうかを判断する"""
    client = initialize_gemini_client()
    if not client:
        return {"is_reanalysis_request": False, "reason": "Gemini client not initialized."}

    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        prompt = f"""
        あなたはメタアナリシスの専門家です。ユーザーのメッセージと前回の分析設定を考慮して、
        ユーザーが再分析を要求しているかどうかを判断してください。

        前回の分析設定:
        {json.dumps(previous_analysis, ensure_ascii=False, indent=2)}

        ユーザーのメッセージ:
        "{user_message}"

        以下の形式でJSONレスポンスを返してください：
        {{
            "is_reanalysis_request": true/false,
            "reason": "判断理由（例：ユーザーが「別の方法で」と述べている、など）"
        }}

        判断基準：
        - 「もう一度」「別の分析」「やり直す」「違う設定で」などのキーワード
        - 前回の分析とは異なる分析タイプ（サブグループ、メタ回帰など）への言及
        - 分析パラメータ（固定効果/ランダム効果など）の変更希望
        - 単なる結果への質問や解釈の要求ではないこと

        レスポンスはJSONのみを返してください。説明文は含めないでください。
        """

        response = client.models.generate_content(
            model=f"models/{model_to_use}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0)
        )

        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        result = json.loads(response_text)
        logger.info(f"Reanalysis intent detection for '{user_message}': {result}")
        return result
    except Exception as e:
        logger.error(f"Error in detect_reanalysis_intent: {e}")
        logger.error(traceback.format_exc()) # Added traceback
        return {"is_reanalysis_request": False, "reason": f"Error during intent detection: {str(e)}"}

def regenerate_r_script_with_gemini_debugging(data_summary, error_message, failed_r_code, model_name=clean_env_var("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")): # BOM除去
    """
    Gemini APIを使用して、エラーが発生したRスクリプトをデバッグ・再生成する。
    """
    client = initialize_gemini_client()
    if not client:
        logger.warning("Geminiクライアントが初期化されていません。Rスクリプトをデバッグできません。")
        return None

    model_to_use = model_name if model_name else "gemini-1.5-flash-latest" # フォールバック
    try:
        prompt = f"""
        あなたはRプログラミングとメタ解析の専門家です。
        以下の情報に基づいて、エラーが発生したRスクリプトを修正してください。
        出力は実行可能なRコードのみにしてください。コメントや説明は含めないでください。

        CSVデータの概要:
        {json.dumps(data_summary, ensure_ascii=False, indent=2)}

        エラーが発生したRスクリプト:
        ```r
        {failed_r_code}
        ```

        発生したエラーメッセージ:
        ```
        {error_message}
        ```

        修正の指示:
        1. エラーメッセージを注意深く分析し、エラーの根本原因を特定してください。
        2. 特に、`{error_message}` に関連する箇所を重点的に修正してください。
        3. 変数名、関数名、ライブラリ呼び出し、データ構造の参照が正しいか確認してください。
        4. `metafor` パッケージの関数の使用方法（特に `escalc` と `rma`）が適切か確認してください。
        5. CSVファイルの読み込み (`dat <- read.csv(...)`) はスクリプトの先頭で行われる想定ですが、もし `failed_r_code` に含まれていない場合は追加しないでください。呼び出し側で処理されます。
        6. スクリプト内で `R` という名前の変数やオブジェクトを絶対に使用しないでください。
        7. R/nlibraryという間に改行が入った単語も使ってはいけません。
        8. 修正後のスクリプトは、エラーが解決され、正しくメタ解析を実行できるものにしてください。
        9. 出力は、修正されたRコードのみとし、前後の説明や```r ```マーカーは含めないでください。

        修正されたRスクリプト:
        """

        logger.info(f"Gemini Rスクリプトデバッグプロンプト:\n{prompt}")

        response = client.models.generate_content(
            model=f"models/{model_name}",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        corrected_r_script = response.text.strip()
        
        if corrected_r_script.startswith("```r"):
            corrected_r_script = corrected_r_script[4:]
        elif corrected_r_script.startswith("```"):
            corrected_r_script = corrected_r_script[3:]
        if corrected_r_script.endswith("```"):
            corrected_r_script = corrected_r_script[:-3]
        
        logger.info(f"Geminiによってデバッグ・再生成されたRスクリプト:\n{corrected_r_script}")
        return corrected_r_script

    except Exception as e:
        logger.error(f"Gemini Rスクリプトデバッグ中にエラーが発生しました: {e}")
        logger.error(traceback.format_exc())
        return None
