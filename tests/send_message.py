#!/usr/bin/env python3
"""
チャンネルにメッセージを送信するスクリプト
"""

import os
import sys
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from slack_sdk import WebClient
import argparse

# .envファイルを読み込み（プロジェクトルートから）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

def send_message(channel_id, message, thread_ts=None):
    """メッセージを送信"""
    
    token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    if not token:
        print("❌ SLACK_UPLOAD_BOT_TOKEN環境変数が設定されていません")
        return
    
    client = WebClient(token=token)
    
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=message,
            thread_ts=thread_ts
        )
        
        print(f"✅ メッセージを送信しました")
        print(f"📝 内容: {message}")
        print(f"🆔 メッセージTS: {response['ts']}")
        
        return response['ts']
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Slackチャンネルにメッセージを送信')
    parser.add_argument('--channel', default='C066EQ49QVD', help='チャンネルID')
    parser.add_argument('--message', required=True, help='送信するメッセージ')
    parser.add_argument('--thread', help='スレッドTS（スレッド返信の場合）')
    
    args = parser.parse_args()
    
    send_message(args.channel, args.message, args.thread)