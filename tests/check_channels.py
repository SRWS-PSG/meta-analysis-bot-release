#!/usr/bin/env python3
"""
Check which channels the bot can access
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

token = os.getenv("SLACK_UPLOAD_BOT_TOKEN")

# Get bot info
print("🤖 ボット情報を確認中...")
url = "https://slack.com/api/auth.test"
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(url, headers=headers)
bot_info = response.json()
if bot_info.get("ok"):
    print(f"✅ ボット名: {bot_info.get('user', 'N/A')}")
    print(f"✅ ユーザーID: {bot_info.get('user_id', 'N/A')}")
    print(f"✅ チーム: {bot_info.get('team', 'N/A')}")
else:
    print(f"❌ ボット情報取得失敗: {bot_info.get('error')}")

print("\n📋 アクセス可能なチャンネル一覧:")
print("-" * 50)

# List channels
url = "https://slack.com/api/conversations.list"
params = {
    "limit": 1000,
    "types": "public_channel,private_channel"
}
response = requests.get(url, headers=headers, params=params)
data = response.json()

if data.get("ok"):
    channels = data.get("channels", [])
    if not channels:
        print("❌ チャンネルが見つかりません")
        print("💡 ボットがどのチャンネルにも参加していない可能性があります")
    else:
        for channel in channels:
            is_member = channel.get("is_member", False)
            status = "✅ 参加中" if is_member else "❌ 未参加"
            print(f"{status} {channel.get('name', 'N/A'):20} (ID: {channel.get('id', 'N/A')})")
            
    # Check specific channel
    target_channel = "" # envから取得する
    print(f"\n🔍 ターゲットチャンネル {target_channel} の確認:")
    found = False
    for channel in channels:
        if channel.get("id") == target_channel:
            found = True
            print(f"✅ チャンネル発見: {channel.get('name')}")
            print(f"   メンバー: {'はい' if channel.get('is_member') else 'いいえ'}")
            if not channel.get('is_member'):
                print(f"   💡 ボットをチャンネルに招待する必要があります")
            break
    
    if not found:
        print(f"❌ チャンネル {target_channel} が見つかりません")
        print("   プライベートチャンネルの可能性があります")
        print("   ボットをチャンネルに招待してください")
else:
    print(f"❌ チャンネル一覧取得失敗: {data.get('error', 'Unknown error')}")
    if data.get('error') == 'missing_scope':
        print("💡 必要なスコープ: channels:read, groups:read")