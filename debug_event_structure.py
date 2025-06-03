#!/usr/bin/env python3
"""
Slackイベントの構造をデバッグするためのスクリプト
app_mentionイベントで受信したデータの構造を詳細に出力
"""
import json
import logging
from slack_bolt import App

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_app_mention(body, event, logger):
    """app_mentionイベントの詳細をログ出力"""
    logger.info("=== APP_MENTION EVENT DEBUG ===")
    
    # body全体の構造
    logger.info(f"Body keys: {list(body.keys())}")
    logger.info(f"Body type: {body.get('type')}")
    
    # eventの詳細
    logger.info(f"Event keys: {list(event.keys())}")
    logger.info(f"Event type: {event.get('type')}")
    logger.info(f"Event text: {event.get('text', 'NO TEXT')}")
    
    # filesの詳細
    files = event.get('files', [])
    logger.info(f"Files count: {len(files)}")
    for i, file in enumerate(files):
        logger.info(f"File {i}: {json.dumps(file, ensure_ascii=False, indent=2)}")
    
    # blocksの詳細
    blocks = event.get('blocks', [])
    logger.info(f"Blocks count: {len(blocks)}")
    for i, block in enumerate(blocks):
        logger.info(f"Block {i} type: {block.get('type')}")
        if block.get('type') == 'rich_text':
            elements = block.get('elements', [])
            for j, elem in enumerate(elements):
                logger.info(f"  Element {j} type: {elem.get('type')}")
                if elem.get('type') == 'rich_text_preformatted':
                    for k, text_elem in enumerate(elem.get('elements', [])):
                        logger.info(f"    Text element {k}: {text_elem.get('text', '')[:100]}...")
    
    # attachmentsの詳細
    attachments = event.get('attachments', [])
    logger.info(f"Attachments count: {len(attachments)}")
    
    # HTTP mode特有の構造確認
    if 'event' in body:
        logger.info("=== HTTP MODE STRUCTURE ===")
        logger.info(f"Top-level event keys: {list(body.get('event', {}).keys())}")
        # HTTP modeではbody['event']にイベントデータが入っている
        http_event = body.get('event', {})
        http_files = http_event.get('files', [])
        logger.info(f"HTTP mode files count: {len(http_files)}")
        
    logger.info("=== END DEBUG ====")