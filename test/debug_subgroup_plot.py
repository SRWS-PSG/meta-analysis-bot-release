#!/usr/bin/env python3
"""
サブグループフォレストプロットの問題をデバッグするスクリプト
"""

import os
import sys
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def debug_subgroup_plot():
    """最新のサブグループフォレストプロットをダウンロードして確認"""
    
    # 環境変数の確認
    token = os.getenv('SLACK_BOT_TOKEN')
    if not token:
        print("❌ SLACK_BOT_TOKEN環境変数が設定されていません")
        return
    
    client = WebClient(token=token)
    channel_id = "C066EQ49QVD"  # テストチャンネル
    
    try:
        # 最新のメッセージを取得
        result = client.conversations_history(
            channel=channel_id,
            limit=20
        )
        
        # forest_plot_subgroup_regionファイルを探す
        for message in result['messages']:
            if 'files' in message:
                for file in message['files']:
                    if 'forest_plot_subgroup' in file['name']:
                        print(f"📁 サブグループプロットファイル発見: {file['name']}")
                        print(f"🔗 URL: {file['url_private']}")
                        print(f"📊 サイズ: {file.get('size', 'N/A')} bytes")
                        print(f"🖼️ 画像サイズ: {file.get('original_w', 'N/A')}x{file.get('original_h', 'N/A')}")
                        
                        # ファイルをダウンロード
                        if download_file(client, file):
                            print("✅ ダウンロード成功")
                        
                        return
        
        print("❌ サブグループフォレストプロットファイルが見つかりません")
        
    except SlackApiError as e:
        print(f"❌ Slack API エラー: {e}")

def download_file(client, file):
    """Slackからファイルをダウンロード"""
    try:
        # ダウンロード用URLを取得
        file_info = client.files_info(file=file['id'])
        download_url = file_info['file']['url_private_download']
        
        # ファイルをダウンロード
        response = client.api_call(
            api_method='GET',
            http_verb='GET',
            file=download_url,
            headers={'Authorization': f'Bearer {client.token}'}
        )
        
        # ローカルに保存
        output_path = f"/home/youkiti/meta-analysis-bot-release/test/{file['name']}"
        with open(output_path, 'wb') as f:
            f.write(response.data)
        
        print(f"💾 ファイル保存: {output_path}")
        
        # ファイルサイズを確認
        size = os.path.getsize(output_path)
        print(f"📐 保存されたファイルサイズ: {size} bytes")
        
        if size < 1000:
            print("⚠️ ファイルサイズが小さすぎます。エラーまたは空のプロットの可能性があります")
            
        return True
        
    except Exception as e:
        print(f"❌ ダウンロードエラー: {e}")
        return False

if __name__ == "__main__":
    debug_subgroup_plot()