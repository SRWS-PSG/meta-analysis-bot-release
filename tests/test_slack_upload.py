#!/usr/bin/env python3
"""
Slack Debug Bot - CSVファイルをアップロードしてメタ解析ボットをテストするためのスクリプト
環境変数:
- SLACK_UPLOAD_BOT_TOKEN: アップロード用ボットのトークン
- SLACK_UPLOAD_CHANNEL_ID: アップロード先のチャンネルID
"""

import os
import sys
import time
import argparse
import requests
from pathlib import Path
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_channel_id(token: str, channel_name: str) -> Optional[str]:
    """チャンネル名からチャンネルIDを取得"""
    url = "https://slack.com/api/conversations.list"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": 1000}
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"❌ チャンネル一覧取得失敗: {response.status_code}")
        return None
    
    data = response.json()
    if not data.get("ok"):
        print(f"❌ API エラー: {data.get('error', 'Unknown error')}")
        return None
    
    for channel in data.get("channels", []):
        if channel.get("name") == channel_name:
            return channel.get("id")
    
    return None

def upload_csv_with_mention(token: str, channel_id: str, file_path: str, 
                           bot_user_id: str, message: str = "") -> bool:
    """CSVファイルをアップロードし、メタ解析ボットにメンション"""
    # 新しいfiles.uploadV2 APIを使用
    # まずファイルをアップロード
    url = "https://slack.com/api/files.getUploadURLExternal"
    headers = {"Authorization": f"Bearer {token}"}
    
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    
    # アップロードURLを取得
    data = {
        "filename": filename,
        "length": file_size
    }
    
    print(f"📤 アップロード準備中: {file_path}")
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code != 200 or not response.json().get("ok"):
        print(f"❌ アップロードURL取得失敗: {response.json().get('error', 'Unknown')}")
        return False
    
    upload_url = response.json()["upload_url"]
    file_id = response.json()["file_id"]
    
    # ファイルをアップロード
    with open(file_path, "rb") as f:
        upload_response = requests.post(upload_url, files={"file": f})
        
    if upload_response.status_code != 200:
        print(f"❌ ファイルアップロード失敗")
        return False
    
    # ファイルアップロードを完了
    complete_url = "https://slack.com/api/files.completeUploadExternal"
    complete_data = {
        "files": [{"id": file_id, "title": filename}],
        "channel_id": channel_id,
        "initial_comment": f"<@{bot_user_id}> {message}" if message else f"<@{bot_user_id}>"
    }
    
    complete_response = requests.post(complete_url, headers=headers, json=complete_data)
    
    if complete_response.status_code != 200:
        print(f"❌ HTTPエラー: {complete_response.status_code}")
        return False
        
    result = complete_response.json()
    if not result.get("ok"):
        print(f"❌ 投稿失敗: {result.get('error', 'Unknown error')}")
        return False
    
    print(f"✅ アップロード成功!")
    print(f"📎 ファイル: {filename}")
    return True

def post_csv_as_codeblock(token: str, channel_id: str, csv_content: str, 
                         bot_user_id: str, message: str = "") -> bool:
    """CSVをコードブロックとして投稿"""
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # メンション付きのメッセージを作成
    text = f"<@{bot_user_id}> {message}\n```\n{csv_content}\n```"
    
    data = {
        "channel": channel_id,
        "text": text,
        "unfurl_links": False,
        "unfurl_media": False
    }
    
    print(f"📤 コードブロック投稿中...")
    print(f"📍 チャンネル: {channel_id}")
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        print(f"❌ HTTPエラー: {response.status_code}")
        return False
    
    data = response.json()
    if not data.get("ok"):
        print(f"❌ 投稿失敗: {data.get('error', 'Unknown error')}")
        return False
    
    print(f"✅ 投稿成功!")
    print(f"🔗 タイムスタンプ: {data.get('ts', 'N/A')}")
    return True

def get_bot_user_id(token: str) -> Optional[str]:
    """ボット自身のユーザーIDを取得"""
    url = "https://slack.com/api/auth.test"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    
    data = response.json()
    if data.get("ok"):
        return data.get("user_id")
    return None

def main():
    parser = argparse.ArgumentParser(description="Slackメタ解析ボットテスト用アップローダー")
    parser.add_argument("--token", help="Slack Bot Token (環境変数: SLACK_UPLOAD_BOT_TOKEN)")
    parser.add_argument("--channel", help="チャンネルID or 名前 (環境変数: SLACK_UPLOAD_CHANNEL_ID)")
    parser.add_argument("--file", help="CSVファイルパス")
    parser.add_argument("--codeblock", action="store_true", help="コードブロックとして投稿")
    parser.add_argument("--message", default="", help="追加メッセージ")
    parser.add_argument("--bot-id", help="メンションするボットのユーザーID", required=True)
    parser.add_argument("--example", choices=["binary", "continuous", "hazard", "proportion"], 
                       help="サンプルCSVを使用")
    
    args = parser.parse_args()
    
    # トークンとチャンネルの取得
    token = args.token or os.getenv("SLACK_UPLOAD_BOT_TOKEN")
    channel = args.channel or os.getenv("SLACK_UPLOAD_CHANNEL_ID")
    
    if not token:
        print("❌ エラー: Slack Bot Tokenが必要です")
        print("   --token オプションまたは SLACK_UPLOAD_BOT_TOKEN 環境変数を設定してください")
        sys.exit(1)
    
    if not channel:
        print("❌ エラー: チャンネルIDが必要です")
        print("   --channel オプションまたは SLACK_UPLOAD_CHANNEL_ID 環境変数を設定してください")
        sys.exit(1)
    
    # チャンネル名の場合はIDに変換
    if not channel.startswith("C") and not channel.startswith("D"):
        print(f"🔍 チャンネル名 '{channel}' からIDを検索中...")
        channel_id = get_channel_id(token, channel)
        if not channel_id:
            print(f"❌ チャンネル '{channel}' が見つかりません")
            sys.exit(1)
        channel = channel_id
        print(f"✅ チャンネルID: {channel}")
    
    # サンプルCSVを使用する場合
    if args.example:
        examples_dir = Path(__file__).parent / "examples"
        example_files = {
            "binary": "example_binary_meta_dataset.csv",
            "continuous": "example_continuous_meta_dataset.csv",
            "hazard": "example_hazard_ratio_meta_dataset.csv",
            "proportion": "example_proportion_meta_dataset.csv"
        }
        file_path = examples_dir / example_files[args.example]
        if not file_path.exists():
            print(f"❌ サンプルファイルが見つかりません: {file_path}")
            sys.exit(1)
    else:
        if not args.file:
            print("❌ エラー: --file または --example オプションが必要です")
            sys.exit(1)
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ ファイルが見つかりません: {file_path}")
            sys.exit(1)
    
    # テスト実行
    print(f"\n🤖 メタ解析ボットテスト")
    print(f"{'='*50}")
    
    if args.codeblock:
        # コードブロックとして投稿
        with open(file_path, "r", encoding="utf-8") as f:
            csv_content = f.read()
        
        success = post_csv_as_codeblock(token, channel, csv_content, args.bot_id, args.message)
    else:
        # ファイルをアップロード
        success = upload_csv_with_mention(token, channel, str(file_path), args.bot_id, args.message)
    
    if success:
        print(f"\n✅ テスト投稿が完了しました")
        print(f"🔍 メタ解析ボットの応答を確認してください")
    else:
        print(f"\n❌ テスト投稿に失敗しました")
        sys.exit(1)

if __name__ == "__main__":
    # Load .env file first
    from pathlib import Path
    import os
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    
    main()