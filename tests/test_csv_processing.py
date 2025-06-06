#!/usr/bin/env python3
"""
CSV処理のテストスクリプト
エラーがどこで発生しているかを特定するため
"""
import os
import asyncio
import logging

# ログ設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_gemini_client():
    """GeminiClientの動作テスト"""
    try:
        from core.gemini_client import GeminiClient
        
        # APIキーの確認
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("❌ GEMINI_API_KEY が設定されていません")
            return False
        else:
            logger.info(f"✅ GEMINI_API_KEY が設定されています (長さ: {len(api_key)})")
        
        # GeminiClient初期化
        logger.info("GeminiClient を初期化中...")
        client = GeminiClient()
        logger.info("✅ GeminiClient の初期化に成功")
        
        # テストCSVデータ
        test_csv = """Study,Intervention_Events,Intervention_Total,Control_Events,Control_Total
Study 1,48,73,47,64
Study 2,38,85,11,96
Study 3,24,89,30,93"""
        
        # CSV分析テスト
        logger.info("CSV分析を実行中...")
        result = await client.analyze_csv(test_csv)
        logger.info(f"✅ CSV分析完了: is_suitable={result.get('is_suitable')}")
        logger.info(f"   理由: {result.get('reason', 'なし')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}", exc_info=True)
        return False

async def test_full_flow():
    """完全な処理フローのテスト"""
    try:
        # 必要な環境変数の確認
        required_vars = ["SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET", "GEMINI_API_KEY"]
        missing_vars = []
        
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
                logger.error(f"❌ {var} が設定されていません")
            else:
                logger.info(f"✅ {var} が設定されています")
        
        if missing_vars:
            logger.error(f"必要な環境変数が不足しています: {', '.join(missing_vars)}")
            return False
        
        # Geminiクライアントテスト
        logger.info("\n=== Geminiクライアントテスト ===")
        success = await test_gemini_client()
        
        if success:
            logger.info("\n✅ すべてのテストが成功しました")
        else:
            logger.error("\n❌ テストが失敗しました")
        
        return success
        
    except Exception as e:
        logger.error(f"テスト中にエラーが発生しました: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # .envファイルがある場合は読み込む
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("✅ .env ファイルを読み込みました")
    except ImportError:
        logger.warning("⚠️  python-dotenv がインストールされていません。環境変数を手動で設定してください。")
    
    # テスト実行
    asyncio.run(test_full_flow())