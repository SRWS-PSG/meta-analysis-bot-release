#!/usr/bin/env python3
"""
自動的に正しいスレッドにメッセージを送信するスクリプト
"""

import os
import sys
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from slack_sdk import WebClient
from datetime import datetime, timedelta
import argparse

# .envファイルを読み込み（プロジェクトルートから）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

def find_latest_thread_and_respond(message, wait_seconds=5):
    """最新のボットスレッドを見つけて応答"""
    
    token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    channel_id = os.getenv('SLACK_UPLOAD_CHANNEL_ID')
    meta_bot_id = os.getenv('META_ANALYSIS_BOT_ID')
    
    if not token:
        print("❌ SLACK_UPLOAD_BOT_TOKEN環境変数が設定されていません")
        return
    
    if not channel_id:
        print("❌ SLACK_UPLOAD_CHANNEL_ID環境変数が設定されていません")
        return
        
    if not meta_bot_id:
        print("❌ META_ANALYSIS_BOT_ID環境変数が設定されていません")
        return
    
    client = WebClient(token=token)
    
    # 少し待機してボットの応答を待つ
    if wait_seconds > 0:
        print(f"⏳ ボット応答待機中（{wait_seconds}秒）...")
        import time
        time.sleep(wait_seconds)
    
    try:
        # 過去1時間のメッセージを取得
        oldest = (datetime.now() - timedelta(hours=1)).timestamp()
        
        response = client.conversations_history(
            channel=channel_id,
            oldest=str(oldest),
            limit=50
        )
        
        messages = response.get('messages', [])
        
        # ボットへのメンション（ファイル付き）を探す
        bot_mentions_with_files = []
        for msg in messages:
            text = msg.get('text', '')
            files = msg.get('files', [])
            user_id = msg.get('user', '')
            
            if f'<@{meta_bot_id}>' in text and len(files) > 0:
                timestamp = datetime.fromtimestamp(float(msg.get('ts', 0)))
                bot_mentions_with_files.append({
                    'ts': msg.get('ts'),
                    'timestamp': timestamp,
                    'text': text[:100] + '...' if len(text) > 100 else text,
                    'user': user_id
                })
        
        if not bot_mentions_with_files:
            print("❌ ファイル付きボットメンションが見つかりません")
            return
        
        # 最新のメンションを取得
        latest_mention = bot_mentions_with_files[0]  # リストは新しい順
        print(f"🎯 最新メンション発見: {latest_mention['timestamp']}")
        print(f"📝 内容: {latest_mention['text']}")
        
        # そのメンションのスレッドでボット応答を確認
        thread_response = client.conversations_replies(
            channel=channel_id,
            ts=latest_mention['ts']
        )
        
        # ボットの応答があるかチェック
        bot_responses = []
        for msg in thread_response.get('messages', []):
            if msg.get('user') == meta_bot_id:
                timestamp = datetime.fromtimestamp(float(msg.get('ts', 0)))
                bot_responses.append({
                    'timestamp': timestamp,
                    'text': msg.get('text', '')[:150] + ('...' if len(msg.get('text', '')) > 150 else ''),
                    'ts': msg.get('ts')
                })
        
        if bot_responses:
            print(f"✅ ボット応答を確認（{len(bot_responses)}件）")
            latest_response = bot_responses[-1]
            print(f"📝 最新応答: {latest_response['text']}")
            
            # CSV分析完了を確認
            if '分析しました' in latest_response['text'] or 'CSV' in latest_response['text']:
                print("✅ CSV分析完了を確認。応答を送信します...")
                
                # メッセージを送信
                reply_response = client.chat_postMessage(
                    channel=channel_id,
                    text=message,
                    thread_ts=latest_mention['ts']  # 元のメンションに対してスレッド応答
                )
                
                print(f"✅ メッセージ送信成功")
                print(f"📝 送信内容: {message}")
                print(f"🆔 メッセージTS: {reply_response['ts']}")
                print(f"🧵 スレッドTS: {latest_mention['ts']}")
                
                return latest_mention['ts']
            else:
                print("⏳ まだCSV分析が完了していないようです")
                return None
        else:
            print("❌ ボット応答が見つかりません")
            return None
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='最新ボットスレッドに自動応答')
    parser.add_argument('--message', required=True, help='送信するメッセージ')
    parser.add_argument('--wait', type=int, default=5, help='応答前の待機時間（秒）')
    
    args = parser.parse_args()
    
    find_latest_thread_and_respond(args.message, args.wait)