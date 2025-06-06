"""
Gemini駆動の対話型パラメータ収集

Geminiが会話の文脈を理解し、十分なパラメータが収集されるまで
適切な質問を生成し続ける実装です。
"""
import logging
import json
from typing import Dict, Any, List, Optional
from core.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

async def process_user_input_with_gemini(
    user_input: str,
    csv_columns: List[str],
    current_params: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    csv_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Geminiを使用してユーザー入力を処理し、パラメータ抽出と応答生成を行う
    
    Returns:
        {
            "extracted_params": {...},  # 抽出されたパラメータ
            "bot_message": "...",       # ユーザーへの応答メッセージ
            "is_ready_to_analyze": bool # 解析開始可能かどうか
        }
    """
    try:
        gemini_client = GeminiClient()
        
        # デバッグ用ログ
        logger.info(f"Gemini dialogue processing - conversation history length: {len(conversation_history)}")
        logger.info(f"Current collected params: {json.dumps(current_params, ensure_ascii=False)}")
        
        # プロンプトの構築
        prompt = f"""
あなたはメタ解析のパラメータ収集を支援する専門家です。
ユーザーとの対話を通じて、メタ解析に必要なすべてのパラメータを収集してください。

## CSV分析結果
{json.dumps(csv_analysis, ensure_ascii=False, indent=2)}

## 利用可能な列名
{', '.join(csv_columns)}

## 会話履歴
{format_conversation_history(conversation_history)}

## 現在収集済みのパラメータ
{json.dumps(current_params, ensure_ascii=False, indent=2)}

## タスク
1. ユーザーの最新の入力からパラメータを抽出する
2. 不足しているパラメータがあれば、次の質問を生成する
3. すべての必要なパラメータが揃ったら、解析開始可能と判断する

## 必須パラメータ
- effect_size: 効果量の種類（OR, RR, RD, PETO, SMD, MD, HR等）
- model_type: モデルタイプ（random または fixed）

## 応答形式
以下のJSON形式で応答してください：
{{
    "extracted_params": {{
        "effect_size": "抽出された効果量（該当する場合）",
        "model_type": "抽出されたモデルタイプ（該当する場合）",
        "method": "統計手法（該当する場合）",
        "subgroup_columns": ["サブグループ列のリスト"],
        "moderator_columns": ["モデレーター列のリスト"]
    }},
    "bot_message": "ユーザーへの応答メッセージ（日本語）",
    "is_ready_to_analyze": false,
    "reasoning": "判断理由（デバッグ用）"
}}

## 重要な指示
1. ユーザーが「オッズ比」と言ったら effect_size: "OR" と解釈
2. ユーザーが「リスク比」と言ったら effect_size: "RR" と解釈
3. ユーザーが「ランダム効果」と言ったら model_type: "random" と解釈
4. ユーザーが「固定効果」と言ったら model_type: "fixed" と解釈
5. ユーザーが「推奨設定」「デフォルト」「そのまま」「自動設定」等と言ったら、現在のパラメータで解析開始可能と判断
6. 必須パラメータ（effect_size, model_type）が揃うまで質問を続ける
7. 質問は自然で親しみやすい日本語で行う
8. ユーザーが曖昧な回答をした場合は、具体的な選択肢を提示する
9. 現在のパラメータで十分な情報が揃っている場合は、積極的に解析開始を提案する

## 対話の例
- ユーザー「オッズ比」→ Bot「オッズ比で解析しますね。次に、統計モデルはランダム効果モデルと固定効果モデルのどちらを使用しますか？」
- ユーザー「ランダムで」→ Bot「承知しました。ランダム効果モデルで解析を行います。」→ is_ready_to_analyze: true
- ユーザー「推奨設定のまま解析開始」→ Bot「承知しました。自動検出されたパラメータで解析を開始します。」→ is_ready_to_analyze: true
"""
        
        # Geminiに構造化データ抽出を依頼
        response_schema = {
            "type": "object",
            "properties": {
                "extracted_params": {
                    "type": "object",
                    "properties": {
                        "effect_size": {"type": "string"},
                        "model_type": {"type": "string"},
                        "method": {"type": "string"},
                        "subgroup_columns": {"type": "array", "items": {"type": "string"}},
                        "moderator_columns": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "bot_message": {"type": "string"},
                "is_ready_to_analyze": {"type": "boolean"},
                "reasoning": {"type": "string"}
            },
            "required": ["extracted_params", "bot_message", "is_ready_to_analyze"]
        }
        
        result = await gemini_client.extract_structured_data(
            prompt=prompt,
            response_schema=response_schema
        )
        
        if result:
            logger.info(f"Gemini dialogue response: {json.dumps(result, ensure_ascii=False)}")
            return result
        else:
            logger.error("Failed to get structured response from Gemini")
            return None
            
    except Exception as e:
        logger.error(f"Error in process_user_input_with_gemini: {e}", exc_info=True)
        return None

def format_conversation_history(history: List[Dict[str, str]]) -> str:
    """会話履歴を読みやすい形式にフォーマット"""
    formatted = []
    for entry in history[-10:]:  # 最新10件のみ表示
        role = "ユーザー" if entry.get("role") == "user" else "ボット"
        content = entry.get("content", "")
        formatted.append(f"{role}: {content}")
    return "\n".join(formatted) if formatted else "（会話履歴なし）"