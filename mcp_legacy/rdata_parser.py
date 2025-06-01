import json
import logging
import os
# import subprocess # subprocess は不要になる
from typing import Dict, Any # Dict は不要になるかも

logger = logging.getLogger(__name__)

def process_rdata_to_json(json_file_path: str) -> str:
    """
    指定されたJSONファイルを読み込み、その内容をJSON文字列として返す。
    以前のバージョンではRスクリプトを実行していたが、その責務は呼び出し元に移管された。
    """
    if not json_file_path or not isinstance(json_file_path, str):
        logger.error(f"無効なJSONファイルパスが指定されました: {json_file_path}")
        return json.dumps({"error": "Invalid JSON file path provided."})

    if not os.path.exists(json_file_path):
        logger.error(f"指定されたJSONファイルが見つかりません: {json_file_path}")
        return json.dumps({"error": f"JSON file not found: {json_file_path}"})

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f) # ファイルからPythonの辞書/リストとして読み込む
        logger.info(f"正常にJSONファイルを読み込みました: {json_file_path}")
        # 読み込んだPythonオブジェクトをJSON文字列に変換して返す
        return json.dumps(data, indent=2) 
    except json.JSONDecodeError as e:
        logger.error(f"JSONファイルのデコードに失敗しました: {json_file_path} - {e}")
        return json.dumps({"error": f"Failed to decode JSON file: {json_file_path} - {e}"})
    except Exception as e:
        logger.error(f"JSONファイルの読み込み中に予期せぬエラーが発生しました: {json_file_path} - {e}")
        import traceback
        logger.error(traceback.format_exc())
        return json.dumps({"error": f"Unexpected error reading JSON file: {json_file_path} - {e}"})

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # テスト用のダミーJSONファイルを作成
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dummy_json_dir = os.path.join(project_root, "debug")
    os.makedirs(dummy_json_dir, exist_ok=True)
    dummy_json_path = os.path.join(dummy_json_dir, "test_summary_for_parser.json")
    
    dummy_data = {
        "analysis_type": "basic_meta_analysis",
        "k": 10,
        "estimate": -0.5,
        "ci_lower": -0.8,
        "ci_upper": -0.2,
        "p_value": 0.001,
        "I2": 75.0,
        "tau2": 0.15
    }
    try:
        with open(dummy_json_path, 'w', encoding='utf-8') as f:
            json.dump(dummy_data, f, indent=2)
        logger.info(f"テスト用のダミーJSONファイルを作成しました: {dummy_json_path}")
    except Exception as e:
        logger.error(f"テスト用ダミーJSONファイルの作成に失敗: {e}")
        # テスト続行不可能なので終了
        sys.exit(1)

    logger.info(f"テスト実行: process_rdata_to_json('{dummy_json_path}')")
    json_output_str = process_rdata_to_json(dummy_json_path)
    
    print("\n--- JSON Output from process_rdata_to_json ---")
    print(json_output_str)
    print("--- End of JSON Output ---\n")
    
    try:
        loaded_json = json.loads(json_output_str)
        if "error" in loaded_json and isinstance(loaded_json.get("error"), str):
            logger.error(f"処理中にエラーが報告されました: {loaded_json['error']}")
        elif loaded_json == dummy_data:
            logger.info("JSON出力は有効で、期待通りの内容です。")
        else:
            logger.warning("JSON出力は有効ですが、期待される内容と異なります。")
            logger.warning(f"Expected: {dummy_data}")
            logger.warning(f"Got: {loaded_json}")

    except json.JSONDecodeError as e:
        logger.error(f"最終的なJSON文字列のパースに失敗しました: {e}")
    
    # テスト用ダミーJSONファイルを削除
    try:
        if os.path.exists(dummy_json_path):
            os.remove(dummy_json_path)
            logger.info(f"テスト用のダミーJSONファイルを削除しました: {dummy_json_path}")
    except Exception as e:
        logger.error(f"テスト用ダミーJSONファイルの削除に失敗: {e}")
