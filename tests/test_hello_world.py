#!/usr/bin/env python3
"""
Simple hello world test for Slack bot
"""
import os
import requests

def post_hello_world():
    token = os.getenv("SLACK_UPLOAD_BOT_TOKEN")
    channel = os.getenv("SLACK_UPLOAD_CHANNEL_ID")
    
    if not token or not channel:
        print("❌ 環境変数が設定されていません")
        return
    
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "channel": channel,
        "text": "hello world"
    }
    
    print(f"📤 投稿中...")
    print(f"📍 チャンネル: {channel}")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        print(f"❌ HTTPエラー: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    if result.get("ok"):
        print(f"✅ 投稿成功!")
        print(f"🔗 タイムスタンプ: {result.get('ts', 'N/A')}")
    else:
        print(f"❌ 投稿失敗: {result.get('error', 'Unknown error')}")
        print(f"詳細: {result}")

if __name__ == "__main__":
    # Load .env file
    from pathlib import Path
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    post_hello_world()