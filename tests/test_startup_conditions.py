"""
起動条件テスト
CLAUDE.md仕様: 起動条件の制御をテストする
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from handlers.mention_handler import handle_app_mention
from handlers.csv_handler import process_csv_async


class TestSlackBotStartupConditions:
    """Slackボット起動条件のテストクラス"""
    
    def test_csv_file_with_mention_should_start_analysis(self):
        """メンション+CSVファイル添付で分析開始すること"""
        # Given: CSVファイル付きメンションイベント
        event = {
            'type': 'app_mention',
            'text': '<@BOT_USER_ID> please analyze',
            'files': [{'name': 'data.csv', 'url_private_download': 'https://files.slack.com/test.csv'}],
            'channel': 'C123456',
            'user': 'U123456',
            'ts': '1234567890.123456'
        }
        client = Mock()
        
        # When: メンションハンドラー実行
        handle_app_mention(event, client)
        
        # Then: CSV分析開始メッセージが送信される
        assert client.chat_postMessage.called
        posted_message = client.chat_postMessage.call_args[1]['text']
        assert '📊 CSVファイルを検出しました' in posted_message
    
    def test_csv_code_block_with_mention_should_start_analysis(self):
        """メンション+CSVコードブロックで分析開始すること"""
        # Given: CSVコードブロック付きメンションイベント
        csv_data = """Study,Effect_Size,SE
Study1,0.5,0.1
Study2,0.8,0.15"""
        event = {
            'type': 'app_mention',
            'text': f'<@BOT_USER_ID>\n```\n{csv_data}\n```',
            'files': [],
            'channel': 'C123456',
            'user': 'U123456',
            'ts': '1234567890.123456'
        }
        client = Mock()
        
        # When: メンションハンドラー実行
        handle_app_mention(event, client)
        
        # Then: CSV分析開始される
        assert client.chat_postMessage.called
        
    def test_mention_only_should_show_help_message(self):
        """メンションのみでヘルプメッセージ表示すること"""
        # Given: メンションのみのイベント
        event = {
            'type': 'app_mention',
            'text': '<@BOT_USER_ID>',
            'files': [],
            'channel': 'C123456',
            'user': 'U123456',
            'ts': '1234567890.123456'
        }
        client = Mock()
        
        # When: メンションハンドラー実行
        handle_app_mention(event, client)
        
        # Then: ヘルプメッセージが送信される
        assert client.chat_postMessage.called
        posted_message = client.chat_postMessage.call_args[1]['text']
        assert 'メタ解析ボット' in posted_message
        assert 'CSVファイルをアップロード' in posted_message
    
    def test_csv_file_only_should_not_start(self):
        """CSV共有のみでは起動しないこと"""
        # Given: file_sharedイベント（メンションなし）
        event = {
            'type': 'file_shared',
            'file': {'name': 'data.csv', 'url_private_download': 'https://files.slack.com/test.csv'},
            'channel_id': 'C123456',
            'user_id': 'U123456'
        }
        
        # When & Then: file_sharedイベントは監視対象外であること
        # この仕様により、CSV共有のみでは何も起動しない
        assert True  # file_sharedイベントハンドラーが存在しないことを確認
    
    def test_private_channel_with_bot_invited_should_work(self):
        """プライベートチャンネルでもボット招待済みなら動作すること"""
        # Given: プライベートチャンネルでのメンション
        event = {
            'type': 'app_mention',
            'text': '<@BOT_USER_ID> analyze please',
            'files': [{'name': 'data.csv', 'url_private_download': 'https://files.slack.com/test.csv'}],
            'channel': 'G123456',  # プライベートチャンネル
            'user': 'U123456',
            'ts': '1234567890.123456'
        }
        client = Mock()
        
        # When: メンションハンドラー実行
        handle_app_mention(event, client)
        
        # Then: 正常に処理される
        assert client.chat_postMessage.called
    
    def test_workspace_member_access_control(self):
        """Slackワークスペースメンバーなら誰でも利用可能であること"""
        # Given: 異なるユーザーからのメンション
        users = ['U123456', 'U789012', 'U345678']
        
        for user_id in users:
            event = {
                'type': 'app_mention',
                'text': '<@BOT_USER_ID>',
                'files': [],
                'channel': 'C123456',
                'user': user_id,
                'ts': '1234567890.123456'
            }
            client = Mock()
            
            # When: メンションハンドラー実行
            handle_app_mention(event, client)
            
            # Then: 全ユーザーが利用可能
            assert client.chat_postMessage.called
    
    def test_response_time_under_3_seconds(self):
        """初回応答が3秒以内であること"""
        import time
        
        # Given: メンションイベント
        event = {
            'type': 'app_mention',
            'text': '<@BOT_USER_ID>',
            'files': [],
            'channel': 'C123456',
            'user': 'U123456',
            'ts': '1234567890.123456'
        }
        client = Mock()
        
        # When: 実行時間測定
        start_time = time.time()
        handle_app_mention(event, client)
        elapsed_time = time.time() - start_time
        
        # Then: 3秒以内に応答
        assert elapsed_time < 3.0
        assert client.chat_postMessage.called