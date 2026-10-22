#!/usr/bin/env python3
"""
测试Python模块搜索路径
"""

import sys
import os

print("Python可执行文件:", sys.executable)
print("当前工作目录:", os.getcwd())
print("Python模块搜索路径:")
for i, path in enumerate(sys.path):
    print(f"  [{i}] {path}")

print("\n尝试导入usb_device模块...")
try:
    import usb_device
    print("成功导入usb_device模块")
    print(f"模块文件路径: {usb_device.__file__}")
    
    # 检查变量是否存在
    if hasattr(usb_device, 'USB2XXXLib_available'):
        print(f"USB2XXXLib_available值: {usb_device.USB2XXXLib_available}")
    else:
        print("错误: USB2XXXLib_available变量不存在")
        
    # 检查模块的所有属性
    print("\n模块属性:")
    for attr in dir(usb_device):
        if not attr.startswith('_'):
            print(f"  {attr}")
            
except Exception as e:
    print(f"导入错误: {e}")
    import traceback
    traceback.print_exc()
