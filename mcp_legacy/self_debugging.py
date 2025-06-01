import logging
import json
# from .openai_utils import generate_r_script # OpenAIからGeminiに変更
from .gemini_utils import regenerate_r_script_with_gemini_debugging # 新しいGeminiデバッグ関数

logger = logging.getLogger(__name__)

def debug_r_script(data_summary, error_message, failed_r_code, remaining_retries): # 引数を変更
    """Rスクリプトのエラーをデバッグして再生成する (Gemini版)"""
    # max_retries は呼び出し元で管理されるため、ここでは remaining_retries を使用
    # この関数は1回のデバッグ試行を行う
    
    logger.info(f"Rスクリプトのデバッグ試行を開始します。残り試行回数: {remaining_retries}")
    
    # regenerate_r_script_with_gemini_debugging は data_summary, error_message, failed_r_code, attempt_number を期待する
    # attempt_number はここでは不要かもしれないが、Gemini関数側で調整
    # ここでは、何回目のデバッグ試行かを示す情報を渡すことも検討できる
    new_script = regenerate_r_script_with_gemini_debugging(
        data_summary=data_summary,
        error_message=error_message,
        failed_r_code=failed_r_code,
        # attempt_number は regenerate_r_script_with_gemini_debugging 側で管理するか、
        # もしくは呼び出し元が現在の試行回数を渡すようにする。
        # ここでは、Gemini関数がこの情報なしで動作すると仮定するか、
        # 呼び出し元(meta_analysis.py)が試行回数を渡すように変更する必要がある。
        # 今回は、Gemini関数側でプロンプトを工夫することを期待し、追加の引数は渡さない。
        # ただし、create_debugging_prompt のようなロジックは Gemini 関数内に移設される。
    )
    
    if new_script:
        logger.info("新しいRスクリプトがGeminiによって生成されました。")
        return new_script
    else:
        logger.error("GeminiによるRスクリプトのデバッグ生成に失敗しました。")
        return None

# create_debugging_prompt 関数は regenerate_r_script_with_gemini_debugging 関数内で
# 同様のロジックが実装されるため、ここでは不要になるか、Gemini関数に統合される。
# 一旦コメントアウトまたは削除。
# def create_debugging_prompt(base_prompt, error_message, attempt):
#     """エラーメッセージに基づいてデバッグプロンプトを作成する"""
#     # ... (このロジックは Gemini Utils の新しい関数に移設)
