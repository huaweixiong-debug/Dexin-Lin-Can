import sqlite3
import json
import os
import sys
from datetime import datetime

# Use absolute path relative to this file or executable
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "test_data.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Create table if not exists
        c.execute('''CREATE TABLE IF NOT EXISTS test_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        completion_time TEXT,
                        product_model TEXT,
                        scan_result TEXT,
                        station_id INTEGER,
                        details_json TEXT,
                        label_qr TEXT
                    )''')
        
        # Add label_qr column if it doesn't exist
        c.execute("PRAGMA table_info(test_records)")
        columns = [column[1] for column in c.fetchall()]
        if 'label_qr' not in columns:
            c.execute("ALTER TABLE test_records ADD COLUMN label_qr TEXT")
            print("Added label_qr column to test_records table.")
        
        # Add indexes for better query performance
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_completion_time ON test_records(completion_time)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_station_id ON test_records(station_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_product_model ON test_records(product_model)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_scan_result ON test_records(scan_result)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_label_qr ON test_records(label_qr)")
            print("Added indexes to test_records table.")
        except Exception as e:
            print(f"Error creating indexes: {e}")
        
        # Create users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password TEXT,
                        role TEXT
                    )''')
        
        # Check if admin exists, if not create default
        c.execute("SELECT * FROM users WHERE username=?", ('admin',))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ('admin', '0000', 'admin'))
            print("Created default admin user.")
            
        conn.commit()
        conn.close()
        print(f"Database initialized at: {DB_FILE}")
    except Exception as e:
        print(f"Database Init Error: {e}")

def authenticate_user(username, password):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        conn.close()
        if result:
            return result[0] # Return role
        return None
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

def add_user(username, password, role='user'):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        print("User already exists")
        return False
    except Exception as e:
        print(f"Add User Error: {e}")
        return False

def delete_user(username):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Delete User Error: {e}")
        return False

def change_password(username, new_password):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Change Password Error: {e}")
        return False

def get_all_users():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        c.execute("SELECT username, role FROM users")
        rows = c.fetchall()
        conn.close()
        return [{"username": r[0], "role": r[1]} for r in rows]
    except Exception as e:
        print(f"Get Users Error: {e}")
        return []

def save_test_record(product_model, scan_result, station_id, data_dict, label_qr=None, fault_info=None):
    """
    data_dict: dictionary of row_idx -> value
    label_qr: label QR code content
    fault_info: fault information dictionary
    """
    try:
        # Increase timeout for concurrent writes
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        
        # Filter data to only include required fields
        # 只保存用户确认的字段
        filtered_data = {}
        
        # 保存用户确认的测试数据项
        # 100%功率相关数据
        if '3' in data_dict:  # 100%功率
            filtered_data["100%功率"] = data_dict['3']
        if '4' in data_dict:  # 100%功率反馈电压
            filtered_data["100%功率反馈电压"] = data_dict['4']
        if '5' in data_dict:  # 100%功率反馈电流
            filtered_data["100%功率反馈电流"] = data_dict['5']
        
        # 80%功率相关数据
        if '7' in data_dict:  # 80%功率
            filtered_data["80%功率"] = data_dict['7']
        if '8' in data_dict:  # 80%功率反馈电压
            filtered_data["80%功率反馈电压"] = data_dict['8']
        if '9' in data_dict:  # 80%功率反馈电流
            filtered_data["80%功率反馈电流"] = data_dict['9']
        
        # 60%功率相关数据
        if '11' in data_dict:  # 60%功率
            filtered_data["60%功率"] = data_dict['11']
        if '12' in data_dict:  # 60%功率反馈电压
            filtered_data["60%功率反馈电压"] = data_dict['12']
        if '13' in data_dict:  # 60%功率反馈电流
            filtered_data["60%功率反馈电流"] = data_dict['13']
        
        # 40%功率相关数据
        if '15' in data_dict:  # 40%功率
            filtered_data["40%功率"] = data_dict['15']
        if '16' in data_dict:  # 40%功率反馈电压
            filtered_data["40%功率反馈电压"] = data_dict['16']
        if '17' in data_dict:  # 40%功率反馈电流
            filtered_data["40%功率反馈电流"] = data_dict['17']
        
        # 故障状态
        if '22' in data_dict:  # 故障状态
            filtered_data["故障状态"] = data_dict['22']
        
        # 保存故障信息
        if fault_info:
            filtered_data["fault"] = fault_info
        
        completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details_json = json.dumps(filtered_data, ensure_ascii=False)
        
        c.execute('''INSERT INTO test_records (completion_time, product_model, scan_result, station_id, details_json, label_qr)
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                     (completion_time, product_model, scan_result, station_id, details_json, label_qr))
        
        conn.commit()
        conn.close()
        print(f"Saved record for {scan_result} at {completion_time}")
        if label_qr:
            print(f"Saved label QR: {label_qr}")
        if fault_info:
            print(f"Saved fault info: {fault_info}")
        return True
    except Exception as e:
        print(f"Database Save Error: {e}")
        raise e

def query_records(start_time=None, end_time=None, scan_result=None, station_id=None, label_qr=None):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=20)
        c = conn.cursor()
        
        # 首先测试不使用时间条件的查询
        test_query = "SELECT COUNT(*) FROM test_records"
        test_params = []
        
        if station_id:
            test_query += " WHERE station_id = ?"
            test_params.append(station_id)
        
        c.execute(test_query, test_params)
        test_count = c.fetchone()[0]
        print(f"Test query count: {test_count}")
        
        # 实际查询
        query = "SELECT id, completion_time, product_model, scan_result, station_id, details_json, label_qr FROM test_records WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND completion_time >= ?"
            params.append(start_time)
        if end_time:
            query += " AND completion_time <= ?"
            params.append(end_time)
        if scan_result:
            query += " AND scan_result LIKE ?"
            params.append(f"%{scan_result}%")
        if station_id:
            query += " AND station_id = ?"
            params.append(station_id)
        if label_qr:
            query += " AND label_qr LIKE ?"
            params.append(f"%{label_qr}%")
            
        query += " ORDER BY completion_time DESC"
        
        print(f"Executing query: {query}")
        print(f"Params: {params}")
        
        c.execute(query, params)
        rows = c.fetchall()
        print(f"Query returned {len(rows)} rows")
        
        conn.close()
        
        results = []
        for row in rows:
            result_dict = {
                "id": row[0],
                "completion_time": row[1],
                "product_model": row[2],
                "scan_result": row[3],
                "station_id": row[4],
                "details": json.loads(row[5]),
                "label_qr": row[6] if len(row) > 6 else None
            }
            results.append(result_dict)
        return results
    except Exception as e:
        print(f"Query Error: {e}")
        import traceback
        traceback.print_exc()
        return []
