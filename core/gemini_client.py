import os
import json
import asyncio
import google.generativeai as genai
from typing import Dict, Any

class GeminiClient:
    """Gemini APIクライアント（統合版）"""
    
    def __init__(self):
        # APIキーが設定されていない場合のエラーハンドリングを追加
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("環境変数 GEMINI_API_KEY が設定されていません。")
        genai.configure(api_key=api_key)
        
        self.model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-1.5-flash") # モデル名を修正
        self.model = genai.GenerativeModel(self.model_name)
    
    async def analyze_csv(self, csv_content: str) -> Dict[str, Any]:
        """CSV内容を分析してメタ解析への適合性を評価"""
        # プロンプトを改善し、より堅牢なJSON出力を目指す
        prompt = f"""
        以下のCSVデータの最初の50行と列名を分析し、メタ解析に適しているかを評価してください。
        特に、効果量(effect size)、その標準誤差(standard error)または分散(variance)、研究のサンプルサイズ(sample size)、研究を識別するID(study ID)として利用できそうな列があるか確認してください。

        CSV内容 (最初の50行程度):
        {csv_content[:3000]}  # 文字数制限を少し増やす

        以下のJSON形式で、キーと値がダブルクォートで囲まれた厳密なJSONで回答してください:
        {{
            "is_suitable": boolean,
            "reason": "メタ解析への適合性に関する具体的な理由（日本語）",
            "detected_columns": {{
                "effect_size_candidates": ["効果量として使えそうな列名の候補リスト"],
                "variance_candidates": ["分散/標準誤差として使えそうな列名の候補リスト"],
                "sample_size_candidates": ["サンプルサイズとして使えそうな列名の候補リスト"],
                "study_id_candidates": ["研究IDとして使えそうな列名の候補リスト"]
            }},
            "suggested_analysis": {{
                "effect_type_suggestion": "SMD, OR, RR, MDなど、検出されたデータから推測される効果量の種類（複数可、または不明）",
                "model_type_suggestion": "randomまたはfixed（通常はrandomを推奨）"
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
        data_previewにはCSVの最初の2行分のデータを含めてください。
        もしCSVデータが不適切で解析できない場合は、is_suitableをfalseにし、reasonにその旨を記載してください。
        """
        
        try:
            response = await self.model.generate_content_async(prompt)
            # Geminiからの応答がマークダウン形式のJSONブロック(` ```json ... ``` `)で返ってくる場合があるため、それをパースする
            raw_response_text = response.text
            if raw_response_text.strip().startswith("```json"):
                json_str = raw_response_text.strip()[7:-3].strip()
            elif raw_response_text.strip().startswith("```"): # 他の言語指定の場合も考慮
                json_str = raw_response_text.strip()[3:-3].strip()
            else:
                json_str = raw_response_text.strip()
            
            return json.loads(json_str)
        except Exception as e:
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
