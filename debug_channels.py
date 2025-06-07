#!/usr/bin/env python3
"""
Debug script to list all channels accessible by the Slack bot
and diagnose channel_not_found errors
"""

import os
import sys
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_channels(token_name, token):
    """List all channels accessible with the given token"""
    print(f"\n{'='*60}")
    print(f"Checking channels with {token_name}")
    print(f"{'='*60}")
    
    if not token:
        print(f"❌ {token_name} not found in environment variables")
        return
    
    client = WebClient(token=token)
    
    try:
        # Get bot info first
        auth_response = client.auth_test()
        print(f"✅ Authenticated as: {auth_response['user']} (Team: {auth_response['team']})")
        print(f"Bot ID: {auth_response['user_id']}")
        
        # List all channels (public)
        print("\n📋 Public Channels:")
        print("-" * 40)
        
        channels_response = client.conversations_list(
            types="public_channel",
            limit=1000
        )
        
        channels = channels_response['channels']
        for channel in sorted(channels, key=lambda x: x['name']):
            member_status = "✅ Member" if channel.get('is_member', False) else "❌ Not a member"
            print(f"  #{channel['name']:<20} ID: {channel['id']} {member_status}")
        
        # List private channels the bot is in
        print("\n🔒 Private Channels (bot is member):")
        print("-" * 40)
        
        private_response = client.conversations_list(
            types="private_channel",
            limit=1000
        )
        
        private_channels = private_response['channels']
        if private_channels:
            for channel in sorted(private_channels, key=lambda x: x['name']):
                print(f"  #{channel['name']:<20} ID: {channel['id']} ✅ Member")
        else:
            print("  No private channels accessible")
        
        # Check specific channel
        target_channel =  "" # envから取得する　絶対直接指定しない
        print(f"\n🔍 Checking target channel: {target_channel}")
        print("-" * 40)
        
        try:
            channel_info = client.conversations_info(channel=target_channel)
            channel_data = channel_info['channel']
            print(f"✅ Channel found: #{channel_data.get('name', 'Unknown')}")
            print(f"   Type: {'Private' if channel_data.get('is_private') else 'Public'}")
            print(f"   Archived: {channel_data.get('is_archived', False)}")
            
            # Check if bot is member
            is_member = channel_data.get('is_member', False)
            print(f"   Bot is member: {'✅ Yes' if is_member else '❌ No'}")
            
            if not is_member:
                print("\n⚠️  The bot is not a member of this channel!")
                print("   Solution: Invite the bot to the channel using /invite @botname")
                
        except SlackApiError as e:
            print(f"❌ Error accessing channel {target_channel}: {e.response['error']}")
            if e.response['error'] == 'channel_not_found':
                print("   Possible reasons:")
                print("   1. Channel doesn't exist")
                print("   2. Bot doesn't have permission to view this channel")
                print("   3. Channel is in a different workspace")
        
        # List recent conversations to help identify the correct channel
        print("\n📅 Recent conversations (to help identify correct channel):")
        print("-" * 40)
        
        try:
            # Get recent messages from the bot
            conversations_response = client.conversations_list(
                types="public_channel,private_channel",
                limit=20
            )
            
            for channel in conversations_response['channels'][:10]:
                if channel.get('is_member'):
                    try:
                        # Get last message timestamp
                        history = client.conversations_history(
                            channel=channel['id'],
                            limit=1
                        )
                        if history['messages']:
                            last_msg = history['messages'][0]
                            print(f"  #{channel['name']:<20} Last activity: {last_msg.get('ts', 'Unknown')}")
                    except:
                        pass
                        
        except Exception as e:
            print(f"Could not fetch recent conversations: {e}")
            
    except SlackApiError as e:
        print(f"❌ Slack API Error: {e.response['error']}")
        print(f"   Details: {e.response.get('needed', 'No additional details')}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Main function to check all available tokens"""
    
    print("🤖 Slack Bot Channel Diagnostic Tool")
    print("=" * 60)
    
    # Check main bot token
    bot_token = os.getenv('SLACK_BOT_TOKEN')
    if bot_token:
        list_channels("SLACK_BOT_TOKEN", bot_token)
    
    # Check upload bot token if different
    upload_token = os.getenv('SLACK_UPLOAD_BOT_TOKEN')
    if upload_token and upload_token != bot_token:
        list_channels("SLACK_UPLOAD_BOT_TOKEN", upload_token)
    elif not upload_token:
        print("\n⚠️  SLACK_UPLOAD_BOT_TOKEN not set, using SLACK_BOT_TOKEN for uploads")
    
    # Summary and recommendations
    print("\n" + "="*60)
    print("📌 Summary and Recommendations:")
    print("="*60)
    print("\nIf you're getting 'channel_not_found' errors:")
    print("1. Verify the channel ID is correct (e.g., CXXXXXXXXXX)")
    print("2. Ensure the bot is invited to the channel (/invite @botname)")
    print("3. Check if the channel is in the same workspace")
    print("4. Verify the bot has the necessary OAuth scopes:")
    print("   - channels:read (for public channels)")
    print("   - groups:read (for private channels)")
    print("   - channels:join (to join public channels)")
    print("   - chat:write (to send messages)")
    print("\nRequired OAuth scopes for full functionality:")
    print("- app_mentions:read")
    print("- channels:history")
    print("- channels:read")
    print("- chat:write")
    print("- files:read")
    print("- files:write")
    print("- groups:history")
    print("- groups:read")
    print("- im:history")
    print("- im:read")
    print("- reactions:write")

if __name__ == "__main__":
    main()
