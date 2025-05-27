import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

def generate_r_script(data_summary, prompt=None, max_retries=1):
    """OpenAIを使用してRスクリプトを生成する"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEYが設定されていません。デフォルトのRスクリプトを使用します。")
        return None
    
    try:
        system_prompt = """あなたはRプログラミングとメタ解析の専門家です。
        CSVデータの概要を基に、metaforパッケージを使用したメタ解析を実行するRスクリプトを生成してください。
        出力は実行可能なRコードのみにしてください。コメントは必要ありません。"""
        
        if prompt:
            system_prompt = prompt
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下のCSVデータを使用してメタ解析を実行するRスクリプトを生成してください：\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}"}
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": "gpt-3.5-turbo",
                "messages": messages,
                "temperature": 0.2
            }
        )
        
        response.raise_for_status()
        result = response.json()
        
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenAI APIリクエスト中にエラーが発生しました: {e}")
        return None
