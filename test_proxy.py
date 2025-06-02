#!/usr/bin/env python3
"""
Test script for proxy functionality
Run this to verify that proxy scraping and testing is working correctly.
"""

import os
import sys
import logging
from datetime import datetime
import time

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our ProxyManager class
from youtube_summary_bot import ProxyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_proxy_manager():
    """Test the ProxyManager functionality."""
    print("=" * 50)
    print("Testing ProxyManager Functionality")
    print("=" * 50)
    
    # Create proxy manager instance
    proxy_manager = ProxyManager()
    
    print(f"\n1. Fetching proxies from {proxy_manager.api_url}")
    print("-" * 30)
    
    # Fetch proxies
    proxies = proxy_manager.fetch_proxies_from_geonode()
    
    if proxies:
        print(f"✅ Successfully fetched {len(proxies)} proxies")
        
        # Show first 5 proxies as examples
        print("\nFirst 5 proxies:")
        for i, proxy in enumerate(proxies[:5]):
            country = proxy.get('country', 'Unknown')
            uptime = proxy.get('uptime', 0)
            speed = proxy.get('speed', 0)
            anonymity = proxy.get('anonymity', 'Unknown')
            print(f"  {i+1}. {proxy['ip']}:{proxy['port']} ({proxy['protocol']}) - {country} - Uptime: {uptime}% - Speed: {speed} - {anonymity}")
        
        print(f"\n2. Testing proxy filtering...")
        print("-" * 30)
        
        # Test proxy filtering
        filtered_proxies = proxy_manager.filter_proxies(proxies)
        print(f"Filtered from {len(proxies)} to {len(filtered_proxies)} high-quality proxies")
        
        if filtered_proxies:
            print("Top 3 filtered proxies:")
            for i, proxy in enumerate(filtered_proxies[:3]):
                country = proxy.get('country', 'Unknown')
                uptime = proxy.get('uptime', 0)
                speed = proxy.get('speed', 0)
                anonymity = proxy.get('anonymity', 'Unknown')
                print(f"  {i+1}. {proxy['ip']}:{proxy['port']} - {country} - Uptime: {uptime}% - Speed: {speed} - {anonymity}")
        
        print(f"\n3. Testing a sample of proxies...")
        print("-" * 30)
        
        # Test a few proxies
        test_proxies = filtered_proxies[:5] if filtered_proxies else proxies[:5]
        working_count = 0
        
        for i, proxy in enumerate(test_proxies):
            print(f"Testing proxy {i+1}/{len(test_proxies)}: {proxy['ip']}:{proxy['port']}")
            
            if proxy_manager.test_proxy(proxy):
                print(f"  ✅ Working")
                working_count += 1
            else:
                print(f"  ❌ Not working")
        
        print(f"\nTest Results: {working_count}/{len(test_proxies)} proxies are working")
        
        print(f"\n4. Testing proxy rotation...")
        print("-" * 30)
        
        # Set the proxies in the manager for testing rotation
        proxy_manager.proxies = filtered_proxies if filtered_proxies else proxies
        proxy_manager.last_updated = time.time()
        
        # Test getting random proxies
        for i in range(3):
            random_proxy = proxy_manager.get_random_proxy()
            if random_proxy:
                print(f"Random proxy {i+1}: {random_proxy}")
            else:
                print(f"Random proxy {i+1}: None available")
        
        print(f"\n5. Testing fallback functionality...")
        print("-" * 30)
        
        # Test saving and loading fallback proxies
        working_proxies = [proxy for proxy in (filtered_proxies or proxies)[:3]]  # Take first 3 as "working"
        proxy_manager.save_fallback_proxies(working_proxies)
        print(f"✅ Saved {len(working_proxies)} fallback proxies")
        
        loaded_proxies = proxy_manager.load_fallback_proxies()
        print(f"✅ Loaded {len(loaded_proxies)} fallback proxies")
        
    else:
        print("❌ Failed to fetch any proxies")
        
        print(f"\nTesting fallback functionality...")
        print("-" * 30)
        
        # Test loading existing fallback proxies
        loaded_proxies = proxy_manager.load_fallback_proxies()
        if loaded_proxies:
            print(f"✅ Loaded {len(loaded_proxies)} fallback proxies")
        else:
            print("❌ No fallback proxies available")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)

def test_youtube_api_with_proxy():
    """Test YouTube transcript API with proxy."""
    print("\n" + "=" * 50)
    print("Testing YouTube Transcript API with Proxy")
    print("=" * 50)
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Test video ID (a popular video that should have transcripts)
        test_video_id = "dQw4w9WgXcQ"  # Rick Roll - classic test video
        
        proxy_manager = ProxyManager()
        proxy = proxy_manager.get_random_proxy()
        
        if proxy:
            print(f"Attempting to get transcript with proxy: {proxy}")
            try:
                transcript = YouTubeTranscriptApi.get_transcript(test_video_id, proxies=proxy)
                print(f"✅ Successfully fetched transcript with {len(transcript)} entries")
                if transcript:
                    print(f"First entry: {transcript[0]['text'][:100]}...")
            except Exception as e:
                print(f"❌ Failed with proxy: {e}")
                
                # Try without proxy as fallback
                print("Trying without proxy...")
                try:
                    transcript = YouTubeTranscriptApi.get_transcript(test_video_id)
                    print(f"✅ Successfully fetched transcript without proxy with {len(transcript)} entries")
                except Exception as e2:
                    print(f"❌ Failed without proxy too: {e2}")
        else:
            print("No proxy available, testing without proxy...")
            try:
                transcript = YouTubeTranscriptApi.get_transcript(test_video_id)
                print(f"✅ Successfully fetched transcript without proxy with {len(transcript)} entries")
            except Exception as e:
                print(f"❌ Failed without proxy: {e}")
    
    except ImportError:
        print("❌ youtube_transcript_api not installed")
    except Exception as e:
        print(f"❌ Error testing YouTube API: {e}")

if __name__ == "__main__":
    print(f"Proxy Test Script Started at {datetime.now()}")
    
    try:
        test_proxy_manager()
        test_youtube_api_with_proxy()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nTest script completed at {datetime.now()}") 