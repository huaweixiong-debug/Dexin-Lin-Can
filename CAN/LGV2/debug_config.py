import json
import os

config_file = r"d:\老化CAN通讯\LGV2\config.json"

if os.path.exists(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("Config loaded successfully!")
        print(f"Keys: {list(config.keys())}")
        print(f"Products count: {len(config.get('products', []))}")
        print(f"Hardware settings count: {len(config.get('hardware_settings', []))}")
    except Exception as e:
        print(f"Error loading config with utf-8: {e}")
        
        # Try GBK
        try:
            with open(config_file, 'r', encoding='gbk') as f:
                config = json.load(f)
            print("Config loaded successfully with GBK!")
        except Exception as e2:
             print(f"Error loading config with GBK: {e2}")
else:
    print("Config file not found")
