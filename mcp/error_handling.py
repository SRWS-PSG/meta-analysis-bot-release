"""
エラー処理モジュール

メタ解析Slack Botのエラー処理機能を提供します。
"""

import logging
import time
import traceback
from typing import Dict, Any, Callable, Optional, List, Tuple, Union
from functools import wraps

logger = logging.getLogger(__name__)

class RetryableError(Exception):
    """再試行可能なエラー"""
    pass

class PermanentError(Exception):
    """永続的なエラー（再試行不可）"""
    pass

def retry_with_backoff(max_retries: int = 3, 
                      initial_backoff: float = 1.0, 
                      backoff_factor: float = 2.0,
                      retryable_exceptions: List[type] = None):
    """
    指数バックオフ付きの再試行デコレータ
    
    Args:
        max_retries: 最大再試行回数
        initial_backoff: 初期バックオフ時間（秒）
        backoff_factor: バックオフ係数
        retryable_exceptions: 再試行可能な例外のリスト
    """
    if retryable_exceptions is None:
        retryable_exceptions = [RetryableError, ConnectionError, TimeoutError]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            backoff = initial_backoff
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger.info(f"再試行 {attempt}/{max_retries} ({func.__name__})")
                    
                    return func(*args, **kwargs)
                except tuple(retryable_exceptions) as e:
                    last_exception = e
                    logger.warning(f"再試行可能なエラーが発生しました ({func.__name__}, 試行 {attempt+1}/{max_retries+1}): {e}")
                    
                    if attempt < max_retries:
                        logger.info(f"{backoff}秒後に再試行します...")
                        time.sleep(backoff)
                        backoff *= backoff_factor
                    else:
                        logger.error(f"最大再試行回数に達しました ({func.__name__}): {e}")
                except PermanentError as e:
                    logger.error(f"永続的なエラーが発生しました ({func.__name__}): {e}")
                    raise
                except Exception as e:
                    logger.error(f"予期しないエラーが発生しました ({func.__name__}): {e}")
                    raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    
    return decorator

class ErrorHandler:
    """エラーハンドラークラス"""
    
    def __init__(self, max_retries: int = 3, 
                initial_backoff: float = 1.0, 
                backoff_factor: float = 2.0):
        """
        初期化
        
        Args:
            max_retries: 最大再試行回数
            initial_backoff: 初期バックオフ時間（秒）
            backoff_factor: バックオフ係数
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_factor = backoff_factor
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        エラーを処理する
        
        Args:
            error: 発生したエラー
            context: エラーコンテキスト
            
        Returns:
            Dict: エラー情報
        """
        if context is None:
            context = {}
        
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
            "timestamp": time.time(),
            "is_retryable": isinstance(error, RetryableError) or isinstance(error, (ConnectionError, TimeoutError))
        }
        
        logger.error(f"エラーが発生しました: {error_info['error_type']} - {error_info['error_message']}")
        
        return error_info
    
    def format_error_message(self, error_info: Dict[str, Any], 
                            include_traceback: bool = False) -> str:
        """
        ユーザー向けのエラーメッセージを生成する
        
        Args:
            error_info: エラー情報
            include_traceback: トレースバックを含めるかどうか
            
        Returns:
            str: フォーマットされたエラーメッセージ
        """
        message = f"エラーが発生しました: {error_info['error_type']} - {error_info['error_message']}"
        
        if include_traceback and "traceback" in error_info:
            message += f"\n\nトレースバック:\n```\n{error_info['traceback']}\n```"
        
        if error_info.get("is_retryable", False):
            message += "\n\nこのエラーは一時的なものかもしれません。もう一度試してみてください。"
        
        return message
    
    def retry_operation(self, operation: Callable, *args, **kwargs) -> Any:
        """
        再試行付きで操作を実行する
        
        Args:
            operation: 実行する操作
            *args, **kwargs: 操作に渡す引数
            
        Returns:
            Any: 操作の結果
        """
        @retry_with_backoff(
            max_retries=self.max_retries,
            initial_backoff=self.initial_backoff,
            backoff_factor=self.backoff_factor
        )
        def _wrapped_operation():
            return operation(*args, **kwargs)
        
        return _wrapped_operation()

class RScriptErrorHandler:
    """Rスクリプトのエラーハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.common_errors = {
            "object .* not found": "指定されたオブジェクトが見つかりません。データセットの列名を確認してください。",
            "non-numeric argument to binary operator": "数値でない引数が演算子に渡されました。データ型を確認してください。",
            "subscript out of bounds": "インデックスが範囲外です。データセットのサイズを確認してください。",
            "no applicable method for .* applied to an object of class": "指定されたクラスのオブジェクトに適用できるメソッドがありません。",
            "could not find function": "指定された関数が見つかりません。必要なパッケージがインストールされているか確認してください。",
            "package .* not found": "指定されたパッケージが見つかりません。パッケージをインストールしてください。",
            "there is no package called": "指定されたパッケージがインストールされていません。",
            "cannot allocate vector of size": "メモリ不足です。データサイズを小さくするか、より多くのメモリを確保してください。",
            "cannot open file": "ファイルを開けません。ファイルパスとアクセス権を確認してください。",
            "cannot open the connection": "接続を開けません。ネットワーク設定を確認してください。"
        }
    
    def parse_error(self, error_message: str) -> Dict[str, Any]:
        """
        Rスクリプトのエラーメッセージを解析する
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            Dict: 解析されたエラー情報
        """
        import re
        
        error_info = {
            "original_message": error_message,
            "matched_pattern": None,
            "user_friendly_message": None,
            "is_package_error": False,
            "is_data_error": False,
            "is_syntax_error": False
        }
        
        if "package" in error_message.lower() and ("not found" in error_message.lower() or "there is no package called" in error_message.lower()):
            error_info["is_package_error"] = True
            
            package_match = re.search(r"package ['\"]?([a-zA-Z0-9.]+)['\"]? not found|there is no package called ['\"]?([a-zA-Z0-9.]+)['\"]?", error_message)
            if package_match:
                package_name = package_match.group(1) or package_match.group(2)
                error_info["package_name"] = package_name
                error_info["user_friendly_message"] = f"パッケージ '{package_name}' がインストールされていません。R環境に必要なパッケージをインストールしてください。"
        
        elif any(keyword in error_message.lower() for keyword in ["object", "not found", "subscript", "non-numeric"]):
            error_info["is_data_error"] = True
            
            object_match = re.search(r"object ['\"]?([a-zA-Z0-9_.]+)['\"]? not found", error_message)
            if object_match:
                object_name = object_match.group(1)
                error_info["object_name"] = object_name
                error_info["user_friendly_message"] = f"オブジェクト '{object_name}' が見つかりません。データセットの列名や変数名を確認してください。"
        
        elif any(keyword in error_message.lower() for keyword in ["syntax error", "unexpected", "incomplete"]):
            error_info["is_syntax_error"] = True
            error_info["user_friendly_message"] = "Rスクリプトに構文エラーがあります。コードを確認してください。"
        
        if not error_info["user_friendly_message"]:
            for pattern, message in self.common_errors.items():
                if re.search(pattern, error_message):
                    error_info["matched_pattern"] = pattern
                    error_info["user_friendly_message"] = message
                    break
        
        if not error_info["user_friendly_message"]:
            error_info["user_friendly_message"] = "Rスクリプトの実行中にエラーが発生しました。詳細なエラーメッセージを確認してください。"
        
        return error_info
    
    def suggest_fix(self, error_info: Dict[str, Any], r_script: str) -> Optional[str]:
        """
        エラーの修正案を提案する
        
        Args:
            error_info: エラー情報
            r_script: Rスクリプト
            
        Returns:
            Optional[str]: 修正されたRスクリプト（修正案がない場合はNone）
        """
        if error_info["is_package_error"] and "package_name" in error_info:
            package_name = error_info["package_name"]
            install_code = f"if (!requireNamespace('{package_name}', quietly = TRUE)) {{ install.packages('{package_name}', repos='https://cran.rstudio.com/') }}\n"
            
            import re
            library_pattern = re.compile(rf"library\(['\"]?{package_name}['\"]?\)")
            if library_pattern.search(r_script):
                return re.sub(library_pattern, f"{install_code}library({package_name})", r_script)
            else:
                return install_code + r_script
        
        elif error_info["is_data_error"] and "object_name" in error_info:
            object_name = error_info["object_name"]
            
            check_code = f"""
cat("データフレームの列名:", paste(names(dat), collapse=", "), "\\n")

similar_cols <- names(dat)[agrep('{object_name}', names(dat), max.distance=0.3)]
if (length(similar_cols) > 0) {{
  cat("'{object_name}' に似た列名:", paste(similar_cols, collapse=", "), "\\n")
  {object_name} <- dat[[similar_cols[1]]]
  cat("'{similar_cols[1]}' を '{object_name}' として使用します\\n")
}}
"""
            import re
            data_load_pattern = re.compile(r"dat\s*<-\s*read\.csv\([^)]+\)")
            if data_load_pattern.search(r_script):
                return re.sub(data_load_pattern, f"\\g<0>\n{check_code}", r_script)
            else:
                return check_code + r_script
        
        return None


if __name__ == "__main__":
    error_handler = ErrorHandler()
    
    def test_operation(fail_count):
        """テスト操作"""
        global attempt # nonlocal から global に変更、またはこの行を削除して下の初期化と合わせる
        attempt += 1
        
        if attempt <= fail_count:
            raise RetryableError(f"テストエラー（試行 {attempt}/{fail_count+1}）")
        
        return "成功"
    
    attempt = 0
    try:
        result = error_handler.retry_operation(test_operation, 2)
        print(f"結果: {result}")
    except Exception as e:
        print(f"エラー: {e}")
    
    attempt = 0
    try:
        result = error_handler.retry_operation(test_operation, 5)
        print(f"結果: {result}")
    except Exception as e:
        error_info = error_handler.handle_error(e)
        print(f"エラー情報: {error_info}")
        print(f"ユーザー向けメッセージ: {error_handler.format_error_message(error_info)}")
