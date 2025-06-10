import os
import json
import asyncio
import logging
import google.generativeai as genai
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiClient:
    """Gemini APIクライアント（統合版）"""
    
    def __init__(self):
        logger.info("Initializing GeminiClient...")
        # APIキーが設定されていない場合のエラーハンドリングを追加
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            raise ValueError("環境変数 GEMINI_API_KEY が設定されていません。")
        logger.info("GEMINI_API_KEY found, configuring...")
        genai.configure(api_key=api_key)
        
        self.model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash") # モデル名を修正
        logger.info(f"Using model: {self.model_name}")
        self.model = genai.GenerativeModel(self.model_name)
        logger.info("GeminiClient initialized successfully")
    
    async def analyze_csv(self, csv_content: str) -> Dict[str, Any]:
        """CSV内容を分析してメタ解析への適合性を評価"""
        logger.info(f"analyze_csv called with content length: {len(csv_content)}")
        # プロンプトを改善し、より堅牢なJSON出力を目指す
        # CSVの行数をカウント（空行を除外し、より堅牢に）
        csv_lines = [line.strip() for line in csv_content.strip().split('\n') if line.strip()]
        data_rows = len(csv_lines) - 1 if csv_lines else 0  # ヘッダーを除く
        logger.info(f"CSV analysis: {len(csv_lines)} total lines, {data_rows} data rows")
        logger.info(f"CSV content preview: {csv_content[:500]}...")
        
        prompt = f"""
        以下のCSVデータを分析し、メタ解析に適しているかを評価してください。
        メタ解析で使用可能な列の種類を特定してください：

        1. 事前計算済み効果量データ: 
           - 一般的な効果量列: effect_size, yi, estimate, smd, md
           - ログ変換済みデータ: log_hr, log_or, log_rr, ln_hr, logHR, logOR, logRR
           - 分散/標準誤差列: variance, vi, standard_error, se, se_log_hr, se_log_or, stderr
        2. 二値アウトカムデータ: 介入群・対照群のイベント数と総数
        3. 連続アウトカムデータ: 各群の平均値、標準偏差、サンプルサイズ
        4. 単一群比率データ: イベント数と総数
        5. 発生率データ: イベント数と観察時間

        CSV内容 (全{data_rows}行のデータ):
        {csv_content[:3000]}

        データ変換の自動検出:
        - 列名に「log」「ln」が含まれる場合、ログ変換済みデータとして識別
        - HR、OR、RRなどの比率系効果量は通常ログ変換が必要
        - 列の値の範囲も考慮（例：負の値を含む場合はログ変換済みの可能性）

        以下のJSON形式で、キーと値がダブルクォートで囲まれた厳密なJSONで回答してください:
        {{
            "is_suitable": boolean,
            "reason": "メタ解析への適合性に関する具体的な理由（日本語）。必ず「{data_rows}件の研究」のように実際の研究数を明記してください。",
            "num_studies": {data_rows},
            "detected_columns": {{
                "effect_size_candidates": ["事前計算済み効果量列（例: effect_size, logOR, SMD, log_hr）"],
                "variance_candidates": ["分散/標準誤差列（例: variance, SE, standard_error, se_log_hr）"],
                "transformation_status": {{
                    "is_log_transformed": boolean,
                    "detected_log_columns": ["検出されたログ変換済み列名"],
                    "transformation_indicators": ["ログ変換を示す指標（列名パターン、値の範囲など）"],
                    "needs_transformation": boolean
                }},
                "binary_intervention_events": ["介入群のイベント数列（例: intervention_events, treatment_success）"],
                "binary_intervention_total": ["介入群の総数列（例: intervention_total, treatment_n）"],
                "binary_control_events": ["対照群のイベント数列（例: control_events, control_success）"],
                "binary_control_total": ["対照群の総数列（例: control_total, control_n）"],
                "continuous_intervention_mean": ["介入群平均列（例: intervention_mean, treatment_mean）"],
                "continuous_intervention_sd": ["介入群標準偏差列（例: intervention_sd, treatment_sd）"],
                "continuous_intervention_n": ["介入群サンプルサイズ列（例: intervention_n, treatment_n）"],
                "continuous_control_mean": ["対照群平均列（例: control_mean, placebo_mean）"],
                "continuous_control_sd": ["対照群標準偏差列（例: control_sd, placebo_sd）"],
                "continuous_control_n": ["対照群サンプルサイズ列（例: control_n, placebo_n）"],
                "proportion_events": ["単一群の比率データ：イベント数列（例: events, successes）"],
                "proportion_total": ["単一群の比率データ：総数列（例: total, n, sample_size）"],
                "proportion_time": ["発生率データ：観察時間列（例: time, person_years）"],
                "sample_size_candidates": ["全体サンプルサイズ列（例: total_n, sample_size）"],
                "study_id_candidates": ["研究ID列（例: study, author, study_id）"],
                "subgroup_candidates": ["サブグループ解析に使える文字列/カテゴリ型列（例: region, country, intervention_type, risk_of_bias）"],
                "moderator_candidates": ["メタ回帰に使える数値型列（例: year, age, dose, follow_up_months）"]
            }},
            "suggested_analysis": {{
                "effect_type_suggestion": "データの種類に基づいた推奨効果量（OR, RR, SMD, MD, HR, PRE等、単一の文字列）",
                "model_type_suggestion": "randomまたはfixed（通常はrandomを推奨）",
                "transformation_recommendation": "必要な変換の説明（例：「HRデータは既にログ変換済みです」「ORデータの対数変換が必要です」）"
            }},
            "column_descriptions": {{
                "column_name1": "列1の内容の簡単な説明とデータ型（例: 数値、文字列）",
                "column_name2": "列2の内容の簡単な説明とデータ型"
            }},
            "data_preview": [
                {{"column1": "row1_val1", "column2": "row1_val2"}},
                {{"column1": "row2_val1", "column2": "row2_val2"}}
            ]
        }}
        
        重要な注意点：
        - 列名は大文字小文字を区別して正確に記載してください
        - ログ変換の検出: 列名に「log」「ln」が含まれる、または効果量が負の値を含む場合
        - HR、OR、RRデータの場合、ログ変換済みかどうかを明確に識別してください
        - SE列は分散計算のため2乗が必要（se_log_hr → vi）
        - 事前計算済み効果量の場合、変換状態を正確に把握してください
        - データの種類に応じて適切な効果量タイプを推奨してください（二値→OR/RR、連続→SMD/MD、ハザード比→HR等）
        - 実際の研究数は{data_rows}件です
        """
        
        try:
            logger.info("Sending request to Gemini API...")
            response = await self.model.generate_content_async(prompt)
            logger.info("Received response from Gemini API")
            # Geminiからの応答がマークダウン形式のJSONブロック(` ```json ... ``` `)で返ってくる場合があるため、それをパースする
            raw_response_text = response.text
            logger.info(f"Raw response length: {len(raw_response_text)}")
            if raw_response_text.strip().startswith("```json"):
                json_str = raw_response_text.strip()[7:-3].strip()
            elif raw_response_text.strip().startswith("```"): # 他の言語指定の場合も考慮
                json_str = raw_response_text.strip()[3:-3].strip()
            else:
                json_str = raw_response_text.strip()
            
            # 制御文字を除去してからJSONをパース
            import re
            cleaned_json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            result = json.loads(cleaned_json_str)
            logger.info(f"Successfully parsed JSON response: is_suitable={result.get('is_suitable')}")
            return result
        except Exception as e:
            logger.error(f"Error in analyze_csv: {e}", exc_info=True)
            # エラー時はフォールバック用の情報を返す
            return {
                "is_suitable": False,
                "reason": f"Gemini APIによるCSV分析中にエラーが発生しました: {str(e)}",
                "detected_columns": {},
                "suggested_analysis": {},
                "column_descriptions": {},
                "data_preview": []
            }

    async def generate_interpretation(self, result_summary: Dict[str, Any], job_id: str) -> Dict[str, Any]:
        """解析結果の学術的解釈を生成（統計解析とGRADE準拠結果のみ）"""
        prompt = f"""
        あなたは医学研究と統計学の専門家です。以下のメタアナリシス結果に基づいて、学術論文の「Statistical Analysis」と「Results」セクションの統計解析部分のみを作成してください。

        解析ジョブID: {job_id}
        解析結果サマリー:
        {json.dumps(result_summary, ensure_ascii=False, indent=2)}

        以下の指示に従って2つのセクションを執筆してください：

        【重要な指示】
        - 提供された統計結果のみに基づいて記述
        - 研究選択や特性など、結果データに含まれない情報は記載しない
        - "statistically significant"は使用せず、数値と信頼区間で客観的に記述
        - 各セクションは英語記述後に日本語訳を併記
        - 結果のセクション書くときには、点推定値、信頼区間といっしょに、Certainty of evidenceのプレースホルダーを書く
        - **Analysis Environment:** 必ずR version and metafor package versionを記載してください。この情報は`result_summary`の`r_version`と`metafor_version`キーに含まれています。

        【Statistical Analysis記述内容】
        結果データから判断できる以下の項目のみ：
        - 使用された効果指標（例：risk ratio, odds ratio, mean difference）
        - 適用されたメタアナリシスモデル（fixed-effect or random-effects）
        - 異質性評価に使用された指標（I², τ², Q統計量）
        - 実行されたサブグループ解析（該当する場合のサブグループ変数）
        - 実行されたメタ回帰分析（該当する場合の共変量）
        - 実行された出版バイアス検定（該当する場合）
        - 実行された感度分析（該当する場合）
        - **Analysis Environment:** `result_summary`の`r_version`と`metafor_version`を必ず記載（例：All analyses were conducted using {result_summary.get('r_version', 'R version not available')} with the metafor package {result_summary.get('metafor_version', 'metafor version not available')}.）

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
        - **Analysis Environment:** 必ずR version（例：R version 4.4.0 (2024-04-24 ucrt)）とmetafor package version（例：metafor version 4.0-0）を記載してください。`result_summary`の`r_version`と`metafor_version`の実際の値を使用してください。Statistical Analysisセクションの最後に記載してください。
        - [Note: Certainty of evidence assessment would be inserted here]

        【記述スタイル】
        - 数値は適切な精度で報告（小数点以下2-3桁）
        - 効果の方向性を明示（どちらのグループの値が高い/低いか）
        - 信頼区間とp値を併記
        - 客観的・記述的表現を使用

        以下のJSON形式で、キーと値がダブルクォートで囲まれた厳密なJSONで回答してください:
        {{
            "methods_section": "Statistical Analysis セクションの記述（英語記述後に日本語訳を併記、必ずAnalysis Environment情報を含む）",
            "results_section": "Results セクションの記述（英語記述後に日本語訳を併記、エビデンス確実性のプレースホルダー含む）",
            "summary": "解析結果全体の簡潔な要約（1-2文）"
        }}

        【重要】Statistical Analysisセクションには必ずAnalysis Environment情報を含めてください：
        - 英語例：All statistical analyses were performed using {result_summary.get('r_version', 'R version not available')} with the metafor package version {result_summary.get('metafor_version', 'metafor version not available')}.
        - 日本語例：統計解析は{result_summary.get('r_version', 'R version not available')}、metaforパッケージversion {result_summary.get('metafor_version', 'metafor version not available')}を用いて実施しました。

        結果データに基づいて判断できる統計手法と数値結果のみを記述してください。
        国際的な医学雑誌の投稿基準（ICMJE）に準拠し、簡潔かつ正確に記述してください。
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            raw_response_text = response.text
            if raw_response_text.strip().startswith("```json"):
                json_str = raw_response_text.strip()[7:-3].strip()
            elif raw_response_text.strip().startswith("```"):
                json_str = raw_response_text.strip()[3:-3].strip()
            else:
                json_str = raw_response_text.strip()

            # 制御文字を除去してからJSONをパース
            import re
            cleaned_json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            return json.loads(cleaned_json_str)
        except Exception as e:
            return {
                "methods_section": "解釈生成中にエラーが発生しました。",
                "results_section": f"エラー詳細: {str(e)}",
                "summary": "解釈レポートの生成に失敗しました。"
            }
    
    async def extract_structured_data(self, prompt: str, response_schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        構造化データを抽出する汎用メソッド
        
        Args:
            prompt: Geminiに送信するプロンプト
            response_schema: 期待するレスポンスのスキーマ
            
        Returns:
            抽出されたデータの辞書、またはエラー時はNone
        """
        try:
            # スキーマ情報をプロンプトに追加
            enhanced_prompt = f"""{prompt}

以下のJSONスキーマに従って、必ず有効なJSON形式で回答してください：
{json.dumps(response_schema, ensure_ascii=False, indent=2)}

注意：
- レスポンスは純粋JSONのみで、他のテキストは含めないでください
- ```json マーカーなどは使用しないでください
- 適切な値がない場合はフィールドを省略してください"""
            
            logger.info(f"Sending structured data extraction request to Gemini")
            response = await self.model.generate_content_async(enhanced_prompt)
            raw_response_text = response.text.strip()
            
            # JSONマーカーを削除
            if raw_response_text.startswith("```json"):
                json_str = raw_response_text[7:-3].strip()
            elif raw_response_text.startswith("```"):
                json_str = raw_response_text[3:-3].strip()
            else:
                json_str = raw_response_text
            
            # 制御文字を除去してからJSONをパース
            import re
            cleaned_json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
            result = json.loads(cleaned_json_str)
            logger.info(f"Successfully extracted structured data: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in structured data extraction: {e}")
            logger.error(f"Raw response: {raw_response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error in structured data extraction: {e}", exc_info=True)
            return None

# 動作確認用の簡単なコード (直接実行された場合)
if __name__ == '__main__':
    async def main():
        # 環境変数 GEMINI_API_KEY が設定されている必要がある
        if not os.environ.get("GEMINI_API_KEY"):
            print("環境変数 GEMINI_API_KEY を設定してください。")
            return

        client = GeminiClient()
        
        # analyze_csv のテスト
        dummy_csv_content = "study,year,effect,stderr\nStudyA,2020,0.5,0.1\nStudyB,2021,0.8,0.2\nStudyC,2022,-0.2,0.15"
        print("--- CSV分析テスト ---")
        analysis = await client.analyze_csv(dummy_csv_content)
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        
        # generate_interpretation のテスト
        dummy_result_summary = {
            "pooled_effect": 0.35,
            "ci_lower": 0.10,
            "ci_upper": 0.60,
            "i2_statistic": 65.7,
            "heterogeneity_p_value": 0.02,
            "num_studies": 15
        }
        print("\n--- 解釈生成テスト ---")
        interpretation = await client.generate_interpretation(dummy_result_summary, "test_job_123")
        print(json.dumps(interpretation, indent=2, ensure_ascii=False))

    asyncio.run(main())
