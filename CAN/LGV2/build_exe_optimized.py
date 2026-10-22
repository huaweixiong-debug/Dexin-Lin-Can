#!/usr/bin/env python3
"""
构建优化的LGV2测试系统可执行文件
"""

import os
import sys
import shutil
import subprocess

def main():
    """主函数"""
    print("=" * 60)
    print("LGV2测试系统 - 优化构建脚本")
    print("=" * 60)
    
    # 清理旧的构建文件
    print("\n清理旧的构建文件...")
    for dir_name in ['build', 'dist']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  删除目录: {dir_name}")
    
    # 优化的构建命令
    build_cmd = [
        'pyinstaller',
        # 基本配置
        '--name=LGV2_Test_System',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        
        # 数据文件
        '--add-data="config.json;."',
        '--add-data="win11_logo.ico;."',
        
        # 动态库文件
        '--add-data="libs/windows/x86_64/libusb-1.0.dll;libs/windows/x86_64"',
        '--add-data="libs/windows/x86_64/USB2XXX.dll;libs/windows/x86_64"',
        
        # 隐藏导入 - 只包含必要的模块
        '--hidden-import=snap7',
        '--hidden-import=snap7.client',
        '--hidden-import=snap7.util',
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=sqlite3',
        '--hidden-import=queue',
        '--hidden-import=logging.handlers',
        '--hidden-import=platform',
        '--hidden-import=ctypes',
        '--hidden-import=os',
        '--hidden-import=time',
        '--hidden-import=threading',
        '--hidden-import=json',
        '--hidden-import=socket',
        
        # 排除不必要的模块
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=PyQt5',
        '--exclude-module=PySide2',
        '--exclude-module=wx',
        '--exclude-module=test',
        '--exclude-module=unittest',
        '--exclude-module=pytest',
        '--exclude-module=distutils',
        '--exclude-module=setuptools',
        '--exclude-module=pip',
        '--exclude-module=wheel',
        '--exclude-module=email',
        '--exclude-module=http',
        '--exclude-module=xml',
        '--exclude-module=html',
        '--exclude-module=urllib',
        '--exclude-module=asyncio',
        '--exclude-module=bz2',
        '--exclude-module=csv',
        '--exclude-module=tarfile',
        '--exclude-module=zipfile',
        '--exclude-module=sqlite3.dump',
        '--exclude-module=tkinter.colorchooser',
        '--exclude-module=tkinter.commondialog',
        '--exclude-module=tkinter.filedialog',
        '--exclude-module=tkinter.font',
        '--exclude-module=tkinter.messagebox',
        '--exclude-module=tkinter.scrolledtext',
        '--exclude-module=tkinter.simpledialog',
        '--exclude-module=tkinter.tix',
        '--exclude-module=tkinter.ttk',
        '--exclude-module=tkinter.constants',
        '--exclude-module=tkinter.dnd',
        '--exclude-module=tkinter.tkfiledialog',
        '--exclude-module=tkinter.tksimpledialog',
        '--exclude-module=tkinter.test',
        
        # 优化选项
        '--strip',  # 移除调试信息
        '--upx-dir=upx',  # 使用UPX压缩
        '--key=lgv2_test_system',  # 加密打包
        
        # 主程序文件
        'Main.py'
    ]
    
    # 执行构建
    print(f"\n执行优化构建...")
    
    # 构建命令字符串
    cmd_str = ' '.join(build_cmd)
    print(f"命令: {cmd_str}")
    
    # 执行构建
    result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("构建成功!")
        print("=" * 60)
        
        # 复制必要的文件
        print("\n复制必要的文件到dist目录...")
        if os.path.exists('dist'):
            # 复制配置文件
            if os.path.exists('config.json'):
                shutil.copy('config.json', 'dist/')
                print("  复制: config.json")
            
            # 复制图标文件
            if os.path.exists('win11_logo.ico'):
                shutil.copy('win11_logo.ico', 'dist/')
                print("  复制: win11_logo.ico")
            
            # 复制动态库目录
            if os.path.exists('libs'):
                if not os.path.exists('dist/libs'):
                    shutil.copytree('libs', 'dist/libs')
                    print("  复制: libs/")
            
            # 显示输出文件信息
            exe_path = os.path.join('dist', 'LGV2_Test_System.exe')
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
                print(f"\n生成的可执行文件: {exe_path}")
                print(f"文件大小: {size:.2f} MB")
        
    else:
        print("\n" + "=" * 60)
        print("构建失败!")
        print("=" * 60)
        print(f"错误输出:\n{result.stderr}")
        print(f"标准输出:\n{result.stdout}")
        return 1
    
    print("\n" + "=" * 60)
    print("优化构建完成!")
    print("=" * 60)
    print("\n优化说明:")
    print("1. 移除了不必要的模块")
    print("2. 包含了必要的动态库")
    print("3. 使用了UPX压缩")
    print("4. 移除了调试信息")
    print("5. 优化了导入")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())