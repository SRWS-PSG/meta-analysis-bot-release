import asyncio
import os
import aiohttp
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

async def download_slack_file_content_async(file_url: str, bot_token: str) -> bytes:
    """
    SlackのプライベートURLからファイルの内容を非同期でダウンロードする。
    """
    headers = {"Authorization": f"Bearer {bot_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url, headers=headers) as response:
            response.raise_for_status()  # エラーがあれば例外を発生させる
            logger.info(f"Successfully initiated download from {file_url}")
            content = await response.read()
            logger.info(f"Successfully read {len(content)} bytes from {file_url}")
            return content

async def save_content_to_temp_file(
    content: bytes, 
    job_id: str, 
    original_filename: str = "uploaded_file.csv"
) -> Tuple[str, Path]:
    """
    バイトコンテンツを一時ファイルに保存し、そのパスとPathオブジェクトを返す。
    ファイル名は job_id と元のファイル名から生成する。
    """
    temp_dir_base = Path(tempfile.gettempdir()) / "meta_analysis_bot_files"
    temp_dir_job = temp_dir_base / job_id
    temp_dir_job.mkdir(parents=True, exist_ok=True)
    
    # 元のファイル名から拡張子を取得、なければ.csvをデフォルトに
    _, ext = os.path.splitext(original_filename)
    if not ext:
        ext = ".csv"
    
    # 安全なファイル名を生成
    safe_original_filename_base = "".join(c if c.isalnum() or c in ['.', '_'] else '_' for c in Path(original_filename).stem)
    temp_file_name = f"{safe_original_filename_base}_{job_id}{ext}"
    temp_file_path = temp_dir_job / temp_file_name
    
    with open(temp_file_path, 'wb') as f:
        f.write(content)
    logger.info(f"Content saved to temporary file: {temp_file_path}")
    return str(temp_file_path), temp_file_path

def get_r_output_dir(job_id: str) -> Path:
    """
    Rスクリプトの出力先となる一時ディレクトリのPathオブジェクトを返す。
    ディレクトリが存在しない場合は作成する。
    """
    temp_dir_base = Path(tempfile.gettempdir()) / "meta_analysis_bot_r_output"
    output_dir = temp_dir_base / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"R output directory prepared: {output_dir}")
    return output_dir

async def cleanup_temp_dir_async(directory_path: Path):
    """
    指定された一時ディレクトリとその内容を非同期で（実際は同期的に）削除する。
    asyncキーワードは他の非同期処理とのインターフェースを合わせるため。
    """
    import shutil
    try:
        if directory_path.exists() and directory_path.is_dir():
            shutil.rmtree(directory_path)
            logger.info(f"Successfully cleaned up temporary directory: {directory_path}")
        elif directory_path.exists():
            logger.warning(f"Path exists but is not a directory, cannot cleanup: {directory_path}")
        else:
            logger.info(f"Temporary directory not found, no cleanup needed: {directory_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temporary directory {directory_path}: {e}")

# 使用例 (直接実行された場合)
if __name__ == "__main__":
    # このテストを実行するには、有効なSLACK_BOT_TOKENとテスト用のファイルURLが必要
    # TEST_SLACK_BOT_TOKEN = os.environ.get("TEST_SLACK_BOT_TOKEN")
    # TEST_FILE_URL = os.environ.get("TEST_FILE_URL") # SlackのプライベートファイルURL

    async def test_download():
        # if not TEST_SLACK_BOT_TOKEN or not TEST_FILE_URL:
        #     print("環境変数 TEST_SLACK_BOT_TOKEN と TEST_FILE_URL を設定してください。")
        #     return
        
        # print(f"Downloading from {TEST_FILE_URL}...")
        # try:
        #     content_bytes = await download_slack_file_content_async(TEST_FILE_URL, TEST_SLACK_BOT_TOKEN)
        #     print(f"Downloaded {len(content_bytes)} bytes.")
            
        #     # 保存テスト
        #     file_path_str, file_path_obj = await save_content_to_temp_file(content_bytes, "testjob001", "example.csv")
        #     print(f"Saved to: {file_path_str}")
        #     print(f"Path object: {file_path_obj}, Exists: {file_path_obj.exists()}")

        #     # R出力ディレクトリテスト
        #     r_out_dir = get_r_output_dir("testjob001_r")
        #     print(f"R output dir: {r_out_dir}, Exists: {r_out_dir.exists()}")
            
        #     # クリーンアップテスト
        #     await cleanup_temp_dir_async(file_path_obj.parent)
        #     print(f"Cleaned up {file_path_obj.parent}, Exists: {file_path_obj.parent.exists()}")
        #     await cleanup_temp_dir_async(r_out_dir)
        #     print(f"Cleaned up {r_out_dir}, Exists: {r_out_dir.exists()}")

        # except Exception as e:
        #     print(f"Test failed: {e}")
        print("utils/file_utils.py のテストは環境変数の設定が必要です。スキップします。")


    asyncio.run(test_download())
