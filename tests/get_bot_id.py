#!/usr/bin/env python3
"""
Get meta-analysis bot user ID
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# プロジェクトルートの.envファイルを読み込み
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

# メタ解析ボットのトークンを使用
token = os.getenv("SLACK_BOT_TOKEN")

if not token:
    print("❌ SLACK_BOT_TOKEN が設定されていません")
    exit(1)

# Get bot info
url = "https://slack.com/api/auth.test"
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(url, headers=headers)
bot_info = response.json()

if bot_info.get("ok"):
    print(f"🤖 メタ解析ボット情報:")
    print(f"   名前: {bot_info.get('user', 'N/A')}")
    print(f"   ユーザーID: {bot_info.get('user_id', 'N/A')}")
    print(f"   チーム: {bot_info.get('team', 'N/A')}")
    print(f"\n💡 このユーザーIDを --bot-id パラメータに使用してください")
else:
    print(f"❌ ボット情報取得失敗: {bot_info.get('error')}")