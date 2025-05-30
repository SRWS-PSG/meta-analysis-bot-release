# mcp/firestore_client.py
import os
import logging
from typing import Optional # Optional をインポート
from google.cloud import firestore

logger = logging.getLogger(__name__)

def clean_env_var(var_name, default=None):
    """
    環境変数からBOMと余分な空白を除去
    Secret Managerから読み込まれた値にBOMが含まれる場合があるため
    """
    value = os.environ.get(var_name, default)
    if value:
        # BOM（\ufeff）と前後の空白を除去
        return value.strip().lstrip('\ufeff').strip()
    return value

_db: Optional[firestore.Client] = None
def get_db():
    global _db
    if _db is None:
        try:
            # 環境変数をクリーンアップ
            project_id = clean_env_var("GOOGLE_CLOUD_PROJECT")
            
            if project_id:
                logger.info(f"Initializing Firestore client with project: {project_id}")
                _db = firestore.Client(project=project_id)
            else:
                logger.info("Initializing Firestore client with default settings")
                _db = firestore.Client()
            
            logger.info("Firestore client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            _db = None
            raise
    return _db
