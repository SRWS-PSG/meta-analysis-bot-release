#!/usr/bin/env python3
"""
Test script to debug version information issue in meta-analysis bot.
This test will upload a CSV file and monitor if version information is correctly 
included in the final result_summary.
"""

import os
import sys
import time
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_version_info():
    """Test version information propagation in meta-analysis"""
    
    # Environment variables
    upload_bot_token = os.environ.get('SLACK_UPLOAD_BOT_TOKEN')
    channel_id = os.environ.get('SLACK_UPLOAD_CHANNEL_ID')
    bot_id = os.environ.get('META_ANALYSIS_BOT_ID')  # meta-analysis-bot ID
    
    if not upload_bot_token:
        print("Error: SLACK_UPLOAD_BOT_TOKEN environment variable not set")
        return
    
    if not channel_id:
        print("Error: SLACK_UPLOAD_CHANNEL_ID environment variable not set")
        return
        
    if not bot_id:
        print("Error: META_ANALYSIS_BOT_ID environment variable not set")
        return
    
    client = WebClient(token=upload_bot_token)
    
    # Prepare test CSV content
    csv_content = """Study,Intervention_Events,Intervention_Total,Control_Events,Control_Total,Region
Study 1,15,48,10,52,Asia
Study 2,22,55,18,58,Europe
Study 3,8,32,12,40,Asia
Study 4,30,60,25,65,Europe
Study 5,19,45,14,50,Asia"""
    
    # Upload CSV and mention bot
    try:
        # Upload the CSV file
        response = client.files_upload_v2(
            channel=channel_id,
            content=csv_content,
            filename="test_version_debug.csv",
            title="Version Info Debug Test",
            initial_comment=f"<@{bot_id}> オッズ比でランダム効果モデルを使って解析してください。バージョン情報のテストです。"
        )
        
        if response["ok"]:
            file_info = response["file"]
            print(f"✅ CSV uploaded successfully: {file_info['name']}")
            print(f"📄 File ID: {file_info['id']}")
            
            # Get the message timestamp for thread tracking
            thread_ts = None
            try:
                # Get channel history to find the upload message
                history = client.conversations_history(
                    channel=channel_id,
                    limit=5
                )
                
                for message in history["messages"]:
                    if message.get("files") and any(f["id"] == file_info["id"] for f in message["files"]):
                        thread_ts = message["ts"]
                        print(f"📎 Found upload message timestamp: {thread_ts}")
                        break
                        
            except SlackApiError as e:
                print(f"Warning: Could not retrieve message timestamp: {e}")
            
            print("\n⏳ Waiting for bot response...")
            time.sleep(5)
            
            # Monitor the channel for bot responses
            monitor_version_info(client, channel_id, thread_ts, timeout=120)
            
        else:
            print(f"❌ File upload failed: {response}")
            
    except SlackApiError as e:
        print(f"❌ Slack API error: {e}")

def monitor_version_info(client, channel_id, thread_ts=None, timeout=120):
    """Monitor channel for version information in bot responses"""
    
    start_time = time.time()
    last_check_time = start_time
    
    print(f"🔍 Monitoring channel {channel_id} for version information...")
    if thread_ts:
        print(f"🧵 Focusing on thread: {thread_ts}")
    
    while time.time() - start_time < timeout:
        try:
            # Get recent messages
            if thread_ts:
                # Check thread replies
                response = client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    oldest=str(last_check_time)
                )
                messages = response.get("messages", [])[1:]  # Skip the original message
            else:
                # Check channel history
                response = client.conversations_history(
                    channel=channel_id,
                    oldest=str(last_check_time),
                    limit=10
                )
                messages = response.get("messages", [])
            
            for message in messages:
                user_id = message.get("user")
                text = message.get("text", "")
                ts = message.get("ts", "")
                
                # Check if this is from the meta-analysis bot
                if user_id == bot_id:  # meta-analysis-bot
                    print(f"\n🤖 Bot message at {ts}:")
                    print(f"📝 Content: {text[:200]}{'...' if len(text) > 200 else ''}")
                    
                    # Check for version information patterns
                    version_patterns = [
                        "R version",
                        "metafor",
                        "Statistical Analysis",
                        "Analysis Environment",
                        "解釈レポート",
                        "バージョン不明"
                    ]
                    
                    found_patterns = [p for p in version_patterns if p.lower() in text.lower()]
                    if found_patterns:
                        print(f"🔍 Found version-related patterns: {found_patterns}")
                        
                        # If this looks like the final interpretation report
                        if "解釈レポート" in text or "Statistical Analysis" in text:
                            print("\n📊 FINAL INTERPRETATION REPORT DETECTED:")
                            print("=" * 60)
                            print(text)
                            print("=" * 60)
                            
                            # Check for version information
                            if "バージョン不明" in text:
                                print("\n❌ VERSION ISSUE DETECTED: 'バージョン不明' found in report")
                            elif "R version" in text and "metafor" in text:
                                print("\n✅ VERSION INFO FOUND: Both R version and metafor version present")
                            else:
                                print("\n⚠️  PARTIAL VERSION INFO: Some version information missing")
                            
                            return  # Test complete
                    
                    # Check for analysis completion
                    if "解析が完了しました" in text or "メタ解析が完了しました" in text:
                        print("✅ Analysis completed, waiting for interpretation report...")
            
            last_check_time = time.time()
            time.sleep(5)  # Check every 5 seconds
            
        except SlackApiError as e:
            print(f"⚠️  Error checking messages: {e}")
            time.sleep(5)
    
    print(f"\n⏰ Monitoring timeout reached ({timeout}s)")

if __name__ == "__main__":
    print("🧪 Testing version information propagation in meta-analysis bot")
    print("=" * 60)
    test_version_info()