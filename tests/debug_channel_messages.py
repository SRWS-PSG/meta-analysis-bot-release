#!/usr/bin/env python3
"""
特定チャンネルのメッセージ履歴を確認するデバッグスクリプト
"""

import os
import sys
# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.errors import SlackApiError
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# .envファイルを読み込み（プロジェクトルートから）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

def check_channel_messages(wait_seconds=30):
    """テスト用チャンネルのメッセージを確認"""
    
    # ボットの応答を待つための待機
    print(f"⏳ ボットの応答を待っています（{wait_seconds}秒）...")
    import time
    time.sleep(wait_seconds)
    
    # 環境変数からトークン取得
    token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    channel_id = os.getenv('SLACK_UPLOAD_CHANNEL_ID')  # テストチャンネル
    meta_bot_id = os.getenv('META_ANALYSIS_BOT_ID')  # メタ解析ボットのID
    
    if not token:
        print("❌ SLACK_UPLOAD_BOT_TOKEN環境変数が設定されていません")
        return
    
    if not channel_id:
        print("❌ SLACK_UPLOAD_CHANNEL_ID環境変数が設定されていません")
        return
        
    if not meta_bot_id:
        print("❌ META_ANALYSIS_BOT_ID環境変数が設定されていません")
        return
    
    from slack_sdk import WebClient
    client = WebClient(token=token)
    
    try:
        print(f"🔍 チャンネル {channel_id} のメッセージ履歴を確認中...")
        
        # 過去1時間のメッセージを取得
        oldest = (datetime.now() - timedelta(hours=1)).timestamp()
        
        response = client.conversations_history(
            channel=channel_id,
            oldest=str(oldest),
            limit=50
        )
        
        messages = response.get('messages', [])
        print(f"📄 取得したメッセージ数: {len(messages)}")
        
        # メタ解析ボット関連のメッセージを抽出
        bot_messages = []
        user_mentions = []
        
        for msg in messages:
            timestamp = datetime.fromtimestamp(float(msg.get('ts', 0)))
            user_id = msg.get('user', 'unknown')
            text = msg.get('text', '')
            
            # ボットのメッセージか確認
            if user_id == meta_bot_id:  # メタ解析ボットのID
                bot_messages.append({
                    'timestamp': timestamp,
                    'text': text[:200] + '...' if len(text) > 200 else text,
                    'thread_ts': msg.get('thread_ts'),
                    'ts': msg.get('ts')
                })
            
            # ボットメンションを確認
            if f'<@{meta_bot_id}>' in text:
                user_mentions.append({
                    'timestamp': timestamp,
                    'user': user_id,
                    'text': text[:100] + '...' if len(text) > 100 else text,
                    'files': len(msg.get('files', []))
                })
        
        print("\n📤 ボットへのメンション:")
        for mention in user_mentions:
            print(f"  {mention['timestamp']} - User {mention['user']}")
            print(f"    Text: {mention['text']}")
            print(f"    Files: {mention['files']}")
            print()
        
        print("\n🤖 ボットの応答:")
        if not bot_messages:
            print("❌ チャンネル直下のボット応答が見つかりません")
            
            # 最新のメンションのスレッドを確認
            if user_mentions:
                latest_mention = user_mentions[0]
                print(f"\n🔍 最新メンション（{latest_mention['timestamp']}）のスレッドを確認中...")
                
                # スレッド内の応答を検索
                mention_ts = None
                for msg in messages:
                    text = msg.get('text', '')
                    if f'<@{meta_bot_id}>' in text and len(msg.get('files', [])) > 0:
                        mention_ts = msg.get('ts')
                        break
                
                if mention_ts:
                    try:
                        thread_response = client.conversations_replies(
                            channel=channel_id,
                            ts=mention_ts
                        )
                        
                        thread_bot_messages = []
                        for msg in thread_response.get('messages', []):
                            if msg.get('user') == meta_bot_id:
                                timestamp = datetime.fromtimestamp(float(msg.get('ts', 0)))
                                thread_bot_messages.append({
                                    'timestamp': timestamp,
                                    'text': msg.get('text', '')[:200] + ('...' if len(msg.get('text', '')) > 200 else ''),
                                    'ts': msg.get('ts')
                                })
                        
                        if thread_bot_messages:
                            print(f"✅ スレッド内でボット応答を発見（{len(thread_bot_messages)}件）:")
                            for bot_msg in thread_bot_messages:
                                print(f"  {bot_msg['timestamp']}")
                                print(f"    Text: {bot_msg['text']}")
                                print()
                            
                            latest_bot_msg = thread_bot_messages[-1]
                            print(f"🔄 最新のボット応答: {latest_bot_msg['timestamp']}")
                            print(f"📝 内容: {latest_bot_msg['text']}")
                            
                            # 対話が進行中かチェック
                            if any(keyword in latest_bot_msg['text'] for keyword in ['どの', '選択', '教えて', '？', 'ですか']):
                                print("✅ 対話が進行中のようです（質問が含まれています）")
                            else:
                                print("⏸️ 対話が完了または停止している可能性があります")
                        else:
                            print("❌ スレッド内にもボット応答が見つかりません")
                    except Exception as e:
                        print(f"❌ スレッド取得エラー: {e}")
        else:
            for bot_msg in bot_messages:
                print(f"  {bot_msg['timestamp']} - Thread: {bot_msg['thread_ts']}")
                print(f"    Text: {bot_msg['text']}")
                print()
            
    except SlackApiError as e:
        print(f"❌ Slack API エラー: {e.response['error']}")
        if e.response['error'] == 'missing_scope':
            print("💡 必要な権限: channels:history")
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='チャンネルメッセージ履歴の確認')
    parser.add_argument('--wait', type=int, default=30, help='ボット応答待機時間（秒）')
    args = parser.parse_args()
    
    # 待機時間を指定して実行
    check_channel_messages(args.wait)