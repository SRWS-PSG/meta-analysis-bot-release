#!/usr/bin/env python3
"""
特定のスレッドの詳細を確認するスクリプト
"""

import os
import sys
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slack_sdk import WebClient
from dotenv import load_dotenv
import argparse

# .envファイルを読み込み（プロジェクトルートから）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

def check_thread_details(thread_ts):
    token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    channel_id = os.getenv('SLACK_UPLOAD_CHANNEL_ID', 'C066EQ49QVD')
    meta_bot_id = os.getenv('META_ANALYSIS_BOT_ID', 'U08TKJ1JQ77')
    
    client = WebClient(token=token)

    print(f"=== スレッド {thread_ts} の詳細 ===")
    
    try:
        # スレッド内のメッセージを取得
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=100
        )
        
        messages = response.get('messages', [])
        print(f"メッセージ数: {len(messages)}")
        print("")
        
        for i, msg in enumerate(messages):
            ts = msg.get('ts', '')
            user = msg.get('user', 'Unknown')
            text = msg.get('text', '')
            
            # ユーザータイプを判定
            user_type = "📨 test-messenger" if user == "U090S37CJ2D" else f"🤖 meta-analysis-bot" if user == meta_bot_id else f"👤 User {user}"
            
            print(f"#{i+1} [{ts}] {user_type}")
            print(f"   {text}")
            
            if msg.get('files'):
                print(f"   📎 Files: {[f.get('name', 'unknown') for f in msg['files']]}")
            
            print("")
            
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='特定のスレッドの詳細を確認')
    parser.add_argument('--thread', required=True, help='スレッドTS')
    
    args = parser.parse_args()
    check_thread_details(args.thread)