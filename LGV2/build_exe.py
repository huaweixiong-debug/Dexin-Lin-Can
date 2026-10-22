#!/usr/bin/env python3
"""
构建LGV2测试系统可执行文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    print("检查依赖...")
    
    required_packages = ['python-snap7']
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_').split('==')[0])
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} 未安装")
            print(f"  请运行: pip install {package}")
            return False
    
    return True

def collect_data_files():
    """收集需要包含的数据文件"""
    print("\n收集数据文件...")
    
    data_files = []
    
    # 配置文件
    if os.path.exists('config.json'):
        data_files.append(('config.json', '.'))
        print("  ✓ config.json")
    else:
        print("  ⚠ config.json 不存在")
    
    # 图标文件
    if os.path.exists('win11_logo.ico'):
        data_files.append(('win11_logo.ico', '.'))
        print("  ✓ win11_logo.ico")
    else:
        print("  ⚠ win11_logo.ico 不存在")
    
    # 数据库文件（如果存在）
    if os.path.exists('test_results.db'):
        data_files.append(('test_results.db', '.'))
        print("  ✓ test_results.db")
    else:
        print("  ⚠ test_results.db 不存在（新数据库将在运行时创建）")
    
    return data_files

def build_executable():
    """构建可执行文件"""
    print("\n开始构建可执行文件...")
    
    # PyInstaller命令参数
    args = [
        'pyinstaller',
        '--name=LGV2_Test_System',
        '--onefile',  # 单文件可执行
        '--windowed',  # 无控制台窗口
        '--clean',     # 清理临时文件
        '--noconfirm', # 不确认覆盖
    ]
    
    # 添加图标
    if os.path.exists('win11_logo.ico'):
        args.append('--icon=win11_logo.ico')
        print("  使用图标: win11_logo.ico")
    
    # 添加数据文件
    data_files = collect_data_files()
    for src, dst in data_files:
        args.append(f'--add-data={src};{dst}')
    
    # 添加隐藏导入
    hidden_imports = [
        'snap7',
        'snap7.client',
        'snap7.util',
        'snap7.types',
        'tkinter',
        'tkinter.ttk',
        'sqlite3',
        'queue',
        'logging.handlers',
    ]
    
    for imp in hidden_imports:
        args.append(f'--hidden-import={imp}')
    
    # 排除不必要的模块
    excludes = [
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PyQt5',
        'PySide2',
        'wx',
        'test',
        'unittest',
        'pytest',
    ]
    
    for exc in excludes:
        args.append(f'--exclude-module={exc}')
    
    # 使用UPX压缩（如果可用）
    args.append('--upx-dir=upx')  # 假设UPX在upx目录中
    
    # 主程序文件
    args.append('Main.py')
    
    # 显示构建命令
    print(f"\n构建命令: {' '.join(args)}")
    
    # 执行构建
    try:
        print("\n执行PyInstaller...")
        result = subprocess.run(args, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ 构建成功!")
            
            # 显示输出文件信息
            exe_path = os.path.join('dist', 'LGV2_Test_System.exe')
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
                print(f"\n生成的可执行文件: {exe_path}")
                print(f"文件大小: {size:.2f} MB")
                
                # 复制到当前目录
                shutil.copy(exe_path, '.')
                print("✓ 已复制到当前目录: LGV2_Test_System.exe")
            else:
                print("⚠ 可执行文件未找到在dist目录中")
        else:
            print("✗ 构建失败!")
            print(f"错误输出:\n{result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ 构建过程中发生错误: {e}")
        return False
    
    return True

def cleanup():
    """清理临时文件"""
    print("\n清理临时文件...")
    
    # 删除构建目录
    for dir_name in ['build', '__pycache__']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  删除目录: {dir_name}")
    
    # 删除spec文件
    spec_file = 'LGV2_Test_System.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"  删除文件: {spec_file}")
    
    # 删除pycache文件
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                pycache_path = os.path.join(root, dir_name)
                shutil.rmtree(pycache_path)
        
        for file_name in files:
            if file_name.endswith('.pyc'):
                pyc_path = os.path.join(root, file_name)
                os.remove(pyc_path)

def main():
    """主函数"""
    print("=" * 60)
    print("LGV2测试系统 - 可执行文件构建工具")
    print("=" * 60)
    
    # 检查当前目录
    if not os.path.exists('Main.py'):
        print("错误: 请在包含Main.py的目录中运行此脚本")
        return 1
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 构建可执行文件
    if not build_executable():
        return 1
    
    # 清理临时文件
    cleanup()
    
    print("\n" + "=" * 60)
    print("构建完成!")
    print("=" * 60)
    print("\n使用方法:")
    print("1. 直接运行 LGV2_Test_System.exe")
    print("2. 或运行 dist/LGV2_Test_System.exe")
    print("\n注意事项:")
    print("- 确保config.json文件与exe在同一目录")
    print("- 确保PLC和扫码枪网络配置正确")
    print("- 首次运行会自动创建数据库文件")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())