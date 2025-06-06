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
                "study_id_candidates": ["研究ID列（例: study, author, study_id）"]
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
            
            result = json.loads(json_str)
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
        """解析結果の学術的解釈を生成"""
        prompt = f"""
        以下のメタ解析結果に基づいて、学術論文の「方法」セクション、「結果」セクションの主要部分、および「考察」のポイントを日本語で記述してください。
        結果の要約も1-2文で含めてください。

        解析ジョブID: {job_id}
        解析結果サマリー:
        {json.dumps(result_summary, ensure_ascii=False, indent=2)}

        以下のJSON形式で、キーと値がダブルクォートで囲まれた厳密なJSONで回答してください:
        {{
            "methods_section": "方法セクションの記述例（どのような解析が行われたか、主要な設定など）",
            "results_section": "結果セクションの記述例（主要な統合効果量、信頼区間、異質性など）",
            "discussion_points": ["考察のポイント1（結果の意義、先行研究との比較など）", "考察のポイント2"],
            "limitations": ["本解析の限界や注意点1", "本解析の限界や注意点2"],
            "summary": "解析結果全体の簡潔な要約（1-2文）"
        }}
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

            return json.loads(json_str)
        except Exception as e:
            return {
                "methods_section": "解釈生成中にエラーが発生しました。",
                "results_section": f"エラー詳細: {str(e)}",
                "discussion_points": [],
                "limitations": [],
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
            
            # JSONとしてパース
            result = json.loads(json_str)
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
