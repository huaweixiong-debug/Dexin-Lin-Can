#coding:utf-8
import os
import stat
import time

# 检查DLL文件的属性
script_dir = os.path.dirname(os.path.abspath(__file__))
dll_paths = [
    os.path.join(script_dir, "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "windows", "x86_64", "USB2XXX.dll"),
    os.path.join(script_dir, "libs", "windows", "x86", "USB2XXX.dll"),
]

for path in dll_paths:
    print(f"\n=== 检查: {path} ===")
    if os.path.exists(path):
        print(f"文件存在: 是")
        print(f"文件大小: {os.path.getsize(path)} bytes")
        print(f"最后修改时间: {time.ctime(os.path.getmtime(path))}")
        print(f"是否可读: {os.access(path, os.R_OK)}")
        print(f"是否可写: {os.access(path, os.W_OK)}")
        print(f"是否可执行: {os.access(path, os.X_OK)}")
        
        # 检查文件权限
        st = os.stat(path)
        print(f"文件权限: {oct(st.st_mode)[-3:]}")
    else:
        print(f"文件存在: 否")

# 检查libs目录
print(f"\n=== 检查libs目录 ===")
libs_dir = os.path.join(script_dir, "libs")
if os.path.exists(libs_dir):
    print(f"libs目录存在: 是")
    print(f"libs目录内容:")
    for item in os.listdir(libs_dir):
        item_path = os.path.join(libs_dir, item)
        if os.path.isdir(item_path):
            print(f"  目录: {item}")
        else:
            print(f"  文件: {item} ({os.path.getsize(item_path)} bytes)")
else:
    print(f"libs目录存在: 否")
