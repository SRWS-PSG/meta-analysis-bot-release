#!/usr/bin/env python3
"""
Simple test script to verify Gemini API functionality
"""
import asyncio
import os
import sys
from core.gemini_client import GeminiClient

async def test_gemini_csv_analysis():
    """Test the Gemini CSV analysis functionality"""
    
    # Check if API key is set
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable is not set")
        print("Please set it with: export GEMINI_API_KEY='your-api-key'")
        return False
    
    print("✓ GEMINI_API_KEY is set")
    
    # Test CSV content
    csv_content = """study,yi,vi,n
Study 1,0.5,0.1,100
Study 2,0.3,0.15,80
Study 3,0.7,0.12,120
Study 4,0.2,0.08,150
Study 5,0.6,0.11,90"""
    
    print("\nTesting CSV analysis with sample data:")
    print(csv_content[:100] + "...")
    
    try:
        # Initialize client
        client = GeminiClient()
        print("\n✓ GeminiClient initialized successfully")
        
        # Analyze CSV
        print("\nAnalyzing CSV content...")
        result = await client.analyze_csv(csv_content)
        
        print("\n✓ CSV analysis completed")
        print(f"Is suitable for meta-analysis: {result.get('is_suitable', False)}")
        print(f"Reason: {result.get('reason', 'N/A')}")
        
        if result.get('detected_columns'):
            print("\nDetected columns:")
            for key, value in result['detected_columns'].items():
                print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("=== Testing Gemini Client ===\n")
    
    success = await test_gemini_csv_analysis()
    
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())