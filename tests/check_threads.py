#!/usr/bin/env python3
"""
スレッド構造を確認するスクリプト
"""

import os
import sys
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slack_sdk import WebClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

# .envファイルを読み込み（プロジェクトルートから）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

def check_threads():
    token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    channel_id = os.getenv('SLACK_UPLOAD_CHANNEL_ID', 'C066EQ49QVD')
    client = WebClient(token=token)

    # 過去10分のメッセージを取得
    oldest = (datetime.now() - timedelta(minutes=10)).timestamp()
    response = client.conversations_history(channel=channel_id, oldest=str(oldest), limit=20)

    print("=== チャンネル内のメッセージとスレッド構造 ===")
    
    # メッセージをグループ化
    threads = {}
    for msg in response['messages']:
        ts = msg.get('ts', '')
        thread_ts = msg.get('thread_ts', '')
        
        if not thread_ts or thread_ts == ts:
            # チャンネル直下のメッセージ（スレッドの開始）
            threads[ts] = {
                'root': msg,
                'replies': []
            }
        else:
            # スレッド内の返信
            if thread_ts not in threads:
                threads[thread_ts] = {
                    'root': None,
                    'replies': []
                }
            threads[thread_ts]['replies'].append(msg)
    
    # スレッドごとに表示
    for thread_ts, thread_data in sorted(threads.items(), reverse=True):
        root = thread_data['root']
        replies = thread_data['replies']
        
        print(f"\n📌 スレッド開始 TS: {thread_ts}")
        
        if root:
            user = root.get('user', 'Unknown')
            text = root.get('text', '')[:100]
            print(f"   👤 User: {user}")
            print(f"   💬 Text: {text}...")
            if root.get('files'):
                print(f"   📎 Files: {len(root['files'])} file(s)")
        
        if replies:
            print(f"   ↳ 返信数: {len(replies)}")
            for reply in sorted(replies, key=lambda x: x['ts']):
                reply_ts = reply.get('ts', '')
                reply_user = reply.get('user', 'Unknown')
                reply_text = reply.get('text', '')[:80]
                print(f"      • {reply_ts} - {reply_user}: {reply_text}...")

if __name__ == "__main__":
    check_threads()