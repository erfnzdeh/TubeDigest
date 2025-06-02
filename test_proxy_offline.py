#!/usr/bin/env python3
"""
Offline test script for proxy functionality
This test demonstrates the proxy system without requiring external API calls.
"""

import os
import sys
import json
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our ProxyManager class
from youtube_summary_bot import ProxyManager

def create_sample_proxy_data():
    """Create sample proxy data for testing."""
    return [
        {
            'ip': '192.168.1.100',
            'port': 8080,
            'protocol': 'http',
            'country': 'US',
            'speed': 100,
            'uptime': 95,
            'anonymity': 'elite',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '10.0.0.50',
            'port': 3128,
            'protocol': 'https',
            'country': 'UK',
            'speed': 80,
            'uptime': 85,
            'anonymity': 'anonymous',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '172.16.0.10',
            'port': 8888,
            'protocol': 'http',
            'country': 'DE',
            'speed': 50,
            'uptime': 60,
            'anonymity': 'transparent',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '203.0.113.1',
            'port': 8080,
            'protocol': 'https',
            'country': 'JP',
            'speed': 120,
            'uptime': 98,
            'anonymity': 'elite',
            'last_checked': '2025-01-01T00:00:00Z'
        }
    ]

def test_offline_proxy_functionality():
    """Test proxy functionality with sample data."""
    print("=" * 60)
    print("Offline Proxy Functionality Test")
    print("=" * 60)
    
    # Create proxy manager instance
    proxy_manager = ProxyManager()
    
    # Create sample data
    sample_proxies = create_sample_proxy_data()
    
    print(f"\n1. Testing with {len(sample_proxies)} sample proxies")
    print("-" * 40)
    
    for i, proxy in enumerate(sample_proxies):
        print(f"  {i+1}. {proxy['ip']}:{proxy['port']} ({proxy['protocol']}) - {proxy['country']} - Uptime: {proxy['uptime']}% - Speed: {proxy['speed']} - {proxy['anonymity']}")
    
    print(f"\n2. Testing proxy filtering...")
    print("-" * 40)
    
    # Test filtering
    filtered_proxies = proxy_manager.filter_proxies(sample_proxies)
    print(f"✅ Filtered from {len(sample_proxies)} to {len(filtered_proxies)} high-quality proxies")
    
    if filtered_proxies:
        print("Filtered proxies:")
        for i, proxy in enumerate(filtered_proxies):
            print(f"  {i+1}. {proxy['ip']}:{proxy['port']} - {proxy['country']} - Uptime: {proxy['uptime']}% - Speed: {proxy['speed']} - {proxy['anonymity']}")
    
    print(f"\n3. Testing proxy format generation...")
    print("-" * 40)
    
    # Set sample proxies in manager and bypass update mechanism
    proxy_manager.proxies = filtered_proxies if filtered_proxies else sample_proxies
    proxy_manager.last_updated = 999999999999  # Set to very high value to avoid update calls
    
    # Temporarily override the update method to prevent API calls during test
    original_update = proxy_manager.update_proxies
    proxy_manager.update_proxies = lambda: None
    
    # Test getting random proxies
    for i in range(3):
        proxy_dict = proxy_manager.get_random_proxy()
        if proxy_dict:
            print(f"✅ Random proxy {i+1}: {proxy_dict}")
        else:
            print(f"❌ Random proxy {i+1}: None available")
    
    # Restore original method
    proxy_manager.update_proxies = original_update
    
    print(f"\n4. Testing fallback save/load functionality...")
    print("-" * 40)
    
    # Test saving
    proxy_manager.save_fallback_proxies(sample_proxies[:2])
    print(f"✅ Saved {len(sample_proxies[:2])} proxies to fallback")
    
    # Test loading
    loaded_proxies = proxy_manager.load_fallback_proxies()
    print(f"✅ Loaded {len(loaded_proxies)} proxies from fallback")
    
    if loaded_proxies:
        print("Loaded proxies:")
        for i, proxy in enumerate(loaded_proxies):
            print(f"  {i+1}. {proxy['ip']}:{proxy['port']} ({proxy['protocol']})")
    
    print(f"\n5. Testing format for YouTubeTranscriptApi...")
    print("-" * 40)
    
    # Show how the proxy format would be used
    if proxy_manager.proxies:
        test_proxy = proxy_manager.proxies[0]
        proxy_url = f"{test_proxy['protocol']}://{test_proxy['ip']}:{test_proxy['port']}"
        proxy_dict = {
            'http': proxy_url,
            'https': proxy_url
        }
        print(f"✅ Example proxy format for YouTubeTranscriptApi:")
        print(f"    YouTubeTranscriptApi.get_transcript(video_id, proxies={proxy_dict})")
    
    print("\n" + "=" * 60)
    print("✅ Offline test completed successfully!")
    print("=" * 60)

def test_proxy_validation():
    """Test IP and port validation functions."""
    print("\n" + "=" * 60)
    print("Testing Proxy Validation Functions")
    print("=" * 60)
    
    proxy_manager = ProxyManager()
    
    # Test IP validation
    test_ips = [
        ("192.168.1.1", True),
        ("255.255.255.255", True),
        ("0.0.0.0", True),
        ("256.1.1.1", False),
        ("192.168.1", False),
        ("not.an.ip", False),
        ("192.168.1.1.1", False)
    ]
    
    print("\nIP Validation Tests:")
    for ip, expected in test_ips:
        result = proxy_manager._is_valid_ip(ip)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {ip} -> {result} (expected: {expected})")
    
    # Test port validation
    test_ports = [
        ("80", True),
        ("8080", True),
        ("65535", True),
        ("1", True),
        ("0", False),
        ("65536", False),
        ("abc", False),
        ("", False)
    ]
    
    print("\nPort Validation Tests:")
    for port, expected in test_ports:
        result = proxy_manager._is_valid_port(port)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {port} -> {result} (expected: {expected})")

if __name__ == "__main__":
    print(f"Offline Proxy Test Script Started at {datetime.now()}")
    
    try:
        test_offline_proxy_functionality()
        test_proxy_validation()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nOffline test script completed at {datetime.now()}") 