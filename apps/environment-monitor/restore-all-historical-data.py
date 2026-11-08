#!/usr/bin/env python3
"""
Script to restore and merge all historical sensor data from backups
"""

import json
import os
import sys
import tarfile
import tempfile
from datetime import datetime
from typing import List, Dict, Any
import shutil

def load_json_from_tar(tar_path: str, json_filename: str) -> List[Dict[str, Any]]:
    """Extract and load JSON data from a tar.gz file"""
    try:
        with tarfile.open(tar_path, 'r:gz') as tar:
            # Extract the JSON file to a temporary location
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
                tar_member = tar.getmember(f'./{json_filename}')
                extracted_file = tar.extractfile(tar_member)
                if extracted_file:
                    content = extracted_file.read().decode('utf-8')
                    temp_file.write(content)
                    temp_file.flush()
                    
                    # Load JSON from the temporary file
                    with open(temp_file.name, 'r') as f:
                        data = json.load(f)
                    
                    os.unlink(temp_file.name)  # Clean up temp file
                    return data
    except Exception as e:
        print(f"Error loading {json_filename} from {tar_path}: {e}")
        return []

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime object"""
    # Handle both formats: with and without 'Z'
    if timestamp_str.endswith('Z'):
        return datetime.fromisoformat(timestamp_str[:-1])
    else:
        return datetime.fromisoformat(timestamp_str)

def merge_historical_data(backup_dir: str, current_data_file: str, output_file: str):
    """Merge all historical data from backups with current data"""
    
    print("🔍 Scanning for backup files...")
    backup_files = []
    
    # Find all backup files
    for filename in os.listdir(backup_dir):
        if filename.startswith('sensor-data-') and filename.endswith('.tar.gz'):
            backup_path = os.path.join(backup_dir, filename)
            backup_files.append((filename, backup_path))
    
    # Sort backup files by date (filename contains timestamp)
    backup_files.sort(key=lambda x: x[0])
    
    print(f"📦 Found {len(backup_files)} backup files")
    
    # Collect all historical data
    all_data = []
    
    # Load data from each backup
    for filename, backup_path in backup_files:
        print(f"📖 Processing {filename}...")
        historical_data = load_json_from_tar(backup_path, 'historical_data.json')
        
        if historical_data:
            print(f"   └─ Found {len(historical_data)} records")
            all_data.extend(historical_data)
        else:
            print(f"   └─ No data found or error loading")
    
    # Load current data if it exists
    if os.path.exists(current_data_file):
        print(f"📖 Loading current data from {current_data_file}...")
        try:
            with open(current_data_file, 'r') as f:
                current_data = json.load(f)
                print(f"   └─ Found {len(current_data)} current records")
                all_data.extend(current_data)
        except Exception as e:
            print(f"   └─ Error loading current data: {e}")
    
    print(f"📊 Total records before deduplication: {len(all_data)}")
    
    # Remove duplicates and sort by timestamp
    print("🔄 Removing duplicates and sorting...")
    
    # Create a dictionary with timestamp as key to remove duplicates
    unique_data = {}
    for entry in all_data:
        timestamp = entry.get('timestamp')
        if timestamp:
            # Use timestamp as key, keeping the most complete entry
            if timestamp not in unique_data or len(entry) > len(unique_data[timestamp]):
                unique_data[timestamp] = entry
    
    # Convert back to list and sort by timestamp
    final_data = list(unique_data.values())
    final_data.sort(key=lambda x: parse_timestamp(x['timestamp']))
    
    print(f"✨ Final dataset: {len(final_data)} unique records")
    
    if final_data:
        first_date = parse_timestamp(final_data[0]['timestamp'])
        last_date = parse_timestamp(final_data[-1]['timestamp'])
        print(f"📅 Date range: {first_date.strftime('%Y-%m-%d %H:%M:%S')} to {last_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save the merged data
    print(f"💾 Saving merged data to {output_file}...")
    
    # Create backup of current file if it exists
    if os.path.exists(output_file):
        backup_current = f"{output_file}.pre-restore-backup"
        shutil.copy2(output_file, backup_current)
        print(f"📋 Current data backed up to {backup_current}")
    
    # Write the merged data
    with open(output_file, 'w') as f:
        json.dump(final_data, f, indent=2)
    
    print(f"✅ Data restoration complete!")
    print(f"📈 Restored {len(final_data)} records spanning {(last_date - first_date).days} days")
    
    return len(final_data)

if __name__ == "__main__":
    backup_dir = "/home/leo/sensor-backups"
    current_data_file = "/tmp/current_historical_data.json"  # We'll copy from container
    output_file = "/tmp/merged_historical_data.json"
    
    if not os.path.exists(backup_dir):
        print(f"❌ Backup directory not found: {backup_dir}")
        sys.exit(1)
    
    try:
        record_count = merge_historical_data(backup_dir, current_data_file, output_file)
        print(f"\n🎉 Successfully merged {record_count} historical records!")
        print(f"📁 Output file: {output_file}")
        
    except Exception as e:
        print(f"❌ Error during data restoration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
