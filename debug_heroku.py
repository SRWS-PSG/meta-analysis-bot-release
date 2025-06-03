#!/usr/bin/env python3
"""
Heroku環境のデバッグスクリプト
環境変数と設定を確認
"""
import os
import sys
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """環境変数の確認"""
    print("=== 環境変数チェック ===")
    
    required_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET",
        "GEMINI_API_KEY",
        "STORAGE_BACKEND",
        "SOCKET_MODE"
    ]
    
    optional_vars = [
        "SLACK_APP_TOKEN",
        "LOG_LEVEL",
        "REDIS_URL",
        "PORT"
    ]
    
    print("\n必須環境変数:")
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            if "TOKEN" in var or "SECRET" in var or "KEY" in var:
                print(f"✅ {var}: *** (設定済み, 長さ: {len(value)})")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: 未設定")
    
    print("\nオプション環境変数:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            if "TOKEN" in var or "URL" in var and "REDIS" in var:
                print(f"  {var}: *** (設定済み)")
            else:
                print(f"  {var}: {value}")
        else:
            print(f"  {var}: 未設定")
    
    print("\n=== Python環境 ===")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    # インポートテスト
    print("\n=== モジュールインポートテスト ===")
    try:
        import slack_bolt
        print(f"✅ slack_bolt: {slack_bolt.__version__}")
    except Exception as e:
        print(f"❌ slack_bolt: {e}")
    
    try:
        import google.generativeai
        print(f"✅ google.generativeai: インポート成功")
    except Exception as e:
        print(f"❌ google.generativeai: {e}")
    
    try:
        import pandas
        print(f"✅ pandas: {pandas.__version__}")
    except Exception as e:
        print(f"❌ pandas: {e}")
    
    try:
        import redis
        print(f"✅ redis: {redis.__version__}")
    except Exception as e:
        print(f"❌ redis: {e}")

def test_slack_connection():
    """Slack接続テスト"""
    print("\n=== Slack接続テスト ===")
    try:
        from slack_bolt import App
        app = App(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )
        
        # ボット情報を取得
        auth_result = app.client.auth_test()
        print(f"✅ Slack接続成功")
        print(f"   Bot User ID: {auth_result['user_id']}")
        print(f"   Bot User Name: {auth_result['user']}")
        print(f"   Team: {auth_result['team']}")
        
    except Exception as e:
        print(f"❌ Slack接続エラー: {e}")

def test_gemini_connection():
    """Gemini API接続テスト"""
    print("\n=== Gemini API接続テスト ===")
    try:
        from core.gemini_client import GeminiClient
        client = GeminiClient()
        print(f"✅ GeminiClient初期化成功")
        print(f"   Model: {client.model_name}")
    except Exception as e:
        print(f"❌ Gemini接続エラー: {e}")

if __name__ == "__main__":
    print("Heroku環境デバッグ開始\n")
    
    check_environment()
    test_slack_connection()
    test_gemini_connection()
    
    print("\nデバッグ完了")