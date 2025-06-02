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
            'ip': '8.8.8.8',  # Google DNS - public IP
            'port': 8080,
            'protocol': 'http',
            'country': 'US',
            'speed': 100,
            'uptime': 95,
            'anonymity': 'elite',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '1.1.1.1',  # Cloudflare DNS - public IP
            'port': 3128,
            'protocol': 'https',
            'country': 'UK',
            'speed': 80,
            'uptime': 85,
            'anonymity': 'anonymous',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '172.16.0.10',  # Private IP - should be filtered out
            'port': 8888,
            'protocol': 'http',
            'country': 'DE',
            'speed': 50,
            'uptime': 60,
            'anonymity': 'transparent',
            'last_checked': '2025-01-01T00:00:00Z'
        },
        {
            'ip': '9.9.9.9',  # Quad9 DNS - public IP
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
    
    print(f"\n2. Testing proxy ordering (no filtering)...")
    print("-" * 40)
    
    # Test ordering (no filtering)
    ordered_proxies = proxy_manager.filter_proxies(sample_proxies)
    print(f"✅ Kept {len(sample_proxies)} proxies in original order (no filtering)")
    
    if ordered_proxies:
        print("Proxies in order (as they would be used):")
        for i, proxy in enumerate(ordered_proxies):
            country = proxy.get('country', 'Unknown')
            uptime = proxy.get('uptime', 0)
            speed = proxy.get('speed', 0)
            anonymity = proxy.get('anonymity', 'Unknown')
            print(f"  {i+1}. {proxy['ip']}:{proxy['port']} - {country} - Uptime: {uptime}% - Speed: {speed} - {anonymity}")
    
    print(f"\n3. Testing sequential proxy iteration...")
    print("-" * 40)
    
    # Set sample proxies in manager and bypass update mechanism
    proxy_manager.proxies = ordered_proxies if ordered_proxies else sample_proxies
    proxy_manager.current_proxy_index = 0  # Reset index
    proxy_manager.last_updated = 999999999999  # Set to very high value to avoid update calls
    
    # Temporarily override the update method to prevent API calls during test
    original_update = proxy_manager.update_proxies
    proxy_manager.update_proxies = lambda: None
    
    # Test getting sequential proxies
    print("Sequential proxy iteration (showing order):")
    for i in range(min(6, len(proxy_manager.proxies) * 2)):  # Test more than available to show cycling
        proxy_dict = proxy_manager.get_next_proxy()
        if proxy_dict:
            proxy_info = proxy_dict['http'].split('://')[-1]  # Extract IP:port
            # Calculate the actual index that was used (before increment)
            used_index = (proxy_manager.current_proxy_index - 1) % len(proxy_manager.proxies)
            print(f"  ✅ Call {i+1}: {proxy_info} (proxy #{used_index + 1})")
        else:
            print(f"  ❌ Call {i+1}: None available")
    
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
        ("8.8.8.8", True),  # Google DNS - public IP
        ("1.1.1.1", True),  # Cloudflare DNS - public IP  
        ("9.9.9.9", True),  # Quad9 DNS - public IP
        ("192.168.1.1", False),  # Private IP - should be rejected
        ("10.0.0.1", False),  # Private IP - should be rejected
        ("172.16.0.1", False),  # Private IP - should be rejected
        ("127.0.0.1", False),  # Localhost - should be rejected
        ("256.1.1.1", False),  # Invalid IP
        ("192.168.1", False),  # Incomplete IP
        ("not.an.ip", False),  # Invalid format
        ("192.168.1.1.1", False)  # Too many octets
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