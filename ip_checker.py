import requests
import json
from datetime import datetime

def get_ip_info():
    try:
        # Get IP information from ipinfo.io
        print("Attempting to connect to ipinfo.io...")
        response = requests.get('https://ipinfo.io/json', timeout=10)
        
        # Print response status for debugging
        print(f"Response Status Code: {response.status_code}")
        
        data = response.json()
        
        # Format the output
        print("\n=== IP Information ===")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"IP Address: {data.get('ip', 'N/A')}")
        print(f"City: {data.get('city', 'N/A')}")
        print(f"Region: {data.get('region', 'N/A')}")
        print(f"Country: {data.get('country', 'N/A')}")
        print(f"ISP: {data.get('org', 'N/A')}")
        print(f"Location: {data.get('loc', 'N/A')}")
        print("=====================\n")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return None

if __name__ == "__main__":
    get_ip_info() 