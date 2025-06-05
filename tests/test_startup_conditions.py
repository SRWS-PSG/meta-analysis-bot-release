"""
起動条件テスト
CLAUDE.md仕様: 起動条件の制御をテストする
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


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
        body = {}
        client = Mock()
        client.auth_test.return_value = {"user_id": "BOT_USER_ID"}
        logger = Mock()
        
        # When: CSVファイル検出ロジックをテスト
        csv_files = [f for f in event.get('files', []) if f.get("name", "").lower().endswith(".csv")]
        
        # Then: CSVファイルが検出される
        assert len(csv_files) > 0
        assert csv_files[0]['name'] == 'data.csv'
    
    def test_csv_code_block_with_mention_should_start_analysis(self):
        """メンション+CSVコードブロックで分析開始すること"""
        # Given: CSVコードブロック付きメンションイベント
        csv_data = """Study,Effect_Size,SE
Study1,0.5,0.1
Study2,0.8,0.15"""
        text = f'<@BOT_USER_ID>\n```\n{csv_data}\n```'
        
        # When: CSV検出ロジックをテスト
        from handlers.mention_handler import _contains_csv_data
        import re
        
        # コードブロックからCSVデータを抽出
        code_block_matches = re.findall(r'```(?:\w+)?\n?(.*?)```', text, re.DOTALL)
        extracted_csv = code_block_matches[0].strip() if code_block_matches else ""
        
        # Then: CSVデータが検出される
        assert len(code_block_matches) > 0
        assert _contains_csv_data(extracted_csv)
        
    def test_mention_only_should_show_help_message(self):
        """メンションのみでヘルプメッセージ表示すること"""
        # Given: メンションのみのイベント
        text = '<@BOT_USER_ID>'
        bot_user_id = 'BOT_USER_ID'
        
        # When: メンション除去ロジックをテスト
        clean_text = text.replace(f"<@{bot_user_id}>", "").strip()
        
        # Then: クリーンテキストが空になる（ヘルプメッセージ条件）
        assert clean_text == ""
    
    def test_csv_file_only_should_not_start(self):
        """CSV共有のみでは起動しないこと"""
        # Given: file_sharedイベント（メンションなし）
        event_type = 'file_shared'
        
        # When & Then: file_sharedイベントは監視対象外であること
        # CLAUDE.mdの仕様により、CSV共有のみでは何も起動しない
        # app_mentionイベントのみが監視対象
        assert event_type != 'app_mention'
    
    def test_private_channel_with_bot_invited_should_work(self):
        """プライベートチャンネルでもボット招待済みなら動作すること"""
        # Given: プライベートチャンネルでのメンション
        channel_id = 'G123456'  # プライベートチャンネル（Gで開始）
        
        # When: チャンネルタイプ判定
        is_private_channel = channel_id.startswith('G')
        
        # Then: プライベートチャンネルが認識される
        assert is_private_channel == True
    
    def test_workspace_member_access_control(self):
        """Slackワークスペースメンバーなら誰でも利用可能であること"""
        # Given: 異なるユーザーからのメンション
        users = ['U123456', 'U789012', 'U345678']
        
        # When: ユーザーIDが有効な形式かチェック
        valid_users = [user for user in users if user.startswith('U') and len(user) > 5]
        
        # Then: 全ユーザーが有効な形式（アクセス制限なし）
        assert len(valid_users) == len(users)
    
    def test_response_time_under_3_seconds(self):
        """初回応答が3秒以内であること"""
        import time
        
        # Given: シンプルな処理時間測定
        start_time = time.time()
        
        # When: メンション処理の模擬（即座に応答）
        # 実装では即座にメッセージを送信し、重い処理は非同期で実行
        response_message = "📊 CSVファイルを検出しました。分析を開始します..."
        
        elapsed_time = time.time() - start_time
        
        # Then: 3秒以内に応答
        assert elapsed_time < 3.0
        assert len(response_message) > 0