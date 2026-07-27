"""
Update offsets from GitHub
Run this script manually or it will auto-run when needed
"""

import json
import requests
import sys
import os
from datetime import datetime

def update_offsets(url="https://raw.githubusercontent.com/sezzyaep/CS2-OFFSETS/main/offsets.json", 
                   local_file="offsets.json"):
    """Fetch latest offsets from GitHub"""
    print(f"🔄 Updating offsets from {url}...")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Save to file
            with open(local_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            print("✅ Offsets updated successfully!")
            print(f"   Build: {data.get('build', 'Unknown')}")
            print(f"   Timestamp: {data.get('timestamp', 'Unknown')}")
            return True
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='URL for offsets JSON file',
                       default="https://raw.githubusercontent.com/sezzyaep/CS2-OFFSETS/main/offsets.json")
    parser.add_argument('--output', help='Output file name', default="offsets.json")
    args = parser.parse_args()
    
    update_offsets(args.url, args.output)
