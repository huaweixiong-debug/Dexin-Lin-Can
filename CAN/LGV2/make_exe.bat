@echo off
echo ========================================
echo LGV2测试系统 - 生成可执行文件
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 安装PyInstaller...
    pip install pyinstaller
)

REM 检查snap7
pip show python-snap7 >nul 2>&1
if errorlevel 1 (
    echo 安装python-snap7...
    pip install python-snap7
)

echo.
echo 开始构建可执行文件...
echo.

REM 构建命令
pyinstaller ^
    --name=LGV2_Test_System ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --add-data="config.json;." ^
    --add-data="win11_logo.ico;." ^
    --hidden-import=snap7 ^
    --hidden-import=snap7.client ^
    --hidden-import=snap7.util ^
    --hidden-import=snap7.types ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=sqlite3 ^
    --hidden-import=queue ^
    --hidden-import=logging.handlers ^
    --exclude-module=matplotlib ^
    --exclude-module=numpy ^
    --exclude-module=pandas ^
    --exclude-module=scipy ^
    --exclude-module=PyQt5 ^
    --exclude-module=PySide2 ^
    --exclude-module=wx ^
    --exclude-module=test ^
    --exclude-module=unittest ^
    --exclude-module=pytest ^
    Main.py

if errorlevel 1 (
    echo.
    echo 构建失败!
    pause
    exit /b 1
)

echo.
echo ========================================
echo 构建成功!
echo ========================================
echo.
echo 生成的可执行文件: dist\LGV2_Test_System.exe
echo.
echo 使用方法:
echo 1. 复制整个dist目录到目标计算机
echo 2. 确保config.json和win11_logo.ico在同一目录
echo 3. 运行LGV2_Test_System.exe
echo.
echo 按任意键退出...
pause >nul