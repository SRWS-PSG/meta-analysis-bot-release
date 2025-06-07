#!/usr/bin/env python3
"""
Get meta-analysis bot user ID
"""
import os
import requests
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

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