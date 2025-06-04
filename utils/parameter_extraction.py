"""
自然言語からのパラメータ抽出ユーティリティ

Gemini AIを使用してユーザーの日本語入力から解析パラメータを抽出します。
"""
import logging
import json
from typing import Dict, Any, Optional
from core.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

# パラメータ抽出用のスキーマ
PARAMETER_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "effect_size": {
            "type": "string",
            "description": "効果量の種類。ユーザーが「オッズ比」と言えば'OR'、「リスク比」は'RR'、「リスク差」は'RD'、「Petoオッズ比」は'PETO'と解釈",
            "enum": ["OR", "RR", "RD", "PETO", "SMD", "MD", "HR", "COR", "proportion", "IR", "ROM", "yi"]
        },
        "model_type": {
            "type": "string", 
            "description": "統計モデルのタイプ。「ランダム効果」は'random'、「固定効果」は'fixed'と解釈",
            "enum": ["random", "fixed"]
        },
        "method": {
            "type": "string",
            "description": "統計手法。REMLやDLなど",
            "enum": ["REML", "DL", "FE", "ML", "HE", "HS"]
        },
        "subgroup_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "サブグループ解析に使用する列名のリスト"
        },
        "moderator_columns": {
            "type": "array", 
            "items": {"type": "string"},
            "description": "メタ回帰分析に使用する列名のリスト"
        }
    },
    "required": []
}

async def extract_parameters_from_text(
    user_text: str,
    csv_columns: Optional[list] = None,
    current_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    ユーザーのテキストから解析パラメータを抽出
    
    Args:
        user_text: ユーザーの入力テキスト
        csv_columns: CSVファイルの列名リスト（サブグループ候補の参考用）
        current_params: 現在収集済みのパラメータ
        
    Returns:
        抽出されたパラメータの辞書
    """
    try:
        gemini_client = GeminiClient()
        
        # プロンプトの構築
        prompt_parts = [
            "あなたはメタ解析のパラメータ収集アシスタントです。",
            "ユーザーの日本語入力から、メタ解析に必要なパラメータを抽出してください。",
            f"\nユーザーの入力: {user_text}"
        ]
        
        if csv_columns:
            prompt_parts.append(f"\n利用可能な列名: {', '.join(csv_columns)}")
            
        if current_params:
            prompt_parts.append(f"\n現在設定済みのパラメータ: {json.dumps(current_params, ensure_ascii=False)}")
        
        prompt_parts.extend([
            "\n以下の対応で解釈してください:",
            "- オッズ比、OR → effect_size: 'OR'",
            "- リスク比、RR → effect_size: 'RR'", 
            "- リスク差、RD → effect_size: 'RD'",
            "- Petoオッズ比、PETO → effect_size: 'PETO'",
            "- ランダム効果、変量効果 → model_type: 'random'",
            "- 固定効果 → model_type: 'fixed'",
            "- REML法 → method: 'REML'",
            "- DL法、DerSimonian-Laird → method: 'DL'",
            "\nユーザーが明示的に指定したパラメータのみを抽出してください。"
        ])
        
        prompt = "\n".join(prompt_parts)
        
        # Geminiでパラメータ抽出
        result = await gemini_client.extract_structured_data(
            prompt=prompt,
            response_schema=PARAMETER_EXTRACTION_SCHEMA
        )
        
        if result:
            logger.info(f"Extracted parameters: {result}")
            return result
        else:
            logger.warning("No parameters extracted from user input")
            return {}
            
    except Exception as e:
        logger.error(f"Error extracting parameters: {e}", exc_info=True)
        return {}

def get_next_question(current_params: Dict[str, Any]) -> Optional[str]:
    """
    現在のパラメータ状態から次の質問を生成
    
    Args:
        current_params: 現在収集済みのパラメータ
        
    Returns:
        次の質問テキスト、または完了時はNone
    """
    if not current_params.get("effect_size"):
        return "どのような効果量で解析しますか？\n例：「オッズ比でお願いします」「リスク比で」「Petoオッズ比で」"
    
    if not current_params.get("model_type"):
        return "統計モデルはどちらを使用しますか？\n例：「ランダム効果モデルで」「固定効果で」"
    
    if not current_params.get("method"):
        return "統計手法を指定しますか？（省略可能）\n例：「REML法で」「DL法で」\n※指定しない場合はREMLを使用します"
    
    # すべて収集済み
    return None