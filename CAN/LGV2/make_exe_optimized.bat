@echo off
echo ========================================
echo LGV2测试系统 - 优化构建脚本
========================================
echo.

REM 清理旧的构建文件
echo 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist LGV2_Test_System.spec del /q LGV2_Test_System.spec

REM 优化的构建命令
echo.
echo 开始构建可执行文件...
echo.

pyinstaller ^
    --name=LGV2_Test_System ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --add-data="config.json;." ^
    --add-data="win11_logo.ico;." ^
    --add-data="libs/windows/x86_64/libusb-1.0.dll;libs/windows/x86_64" ^
    --add-data="libs/windows/x86_64/USB2XXX.dll;libs/windows/x86_64" ^
    --hidden-import=snap7 ^
    --hidden-import=snap7.client ^
    --hidden-import=snap7.util ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=sqlite3 ^
    --hidden-import=queue ^
    --hidden-import=logging.handlers ^
    --hidden-import=platform ^
    --hidden-import=ctypes ^
    --hidden-import=os ^
    --hidden-import=time ^
    --hidden-import=threading ^
    --hidden-import=json ^
    --hidden-import=socket ^
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
    --exclude-module=distutils ^
    --exclude-module=setuptools ^
    --exclude-module=pip ^
    --exclude-module=wheel ^
    --exclude-module=email ^
    --exclude-module=http ^
    --exclude-module=xml ^
    --exclude-module=html ^
    --exclude-module=urllib ^
    --exclude-module=asyncio ^
    --exclude-module=bz2 ^
    --exclude-module=csv ^
    --exclude-module=tarfile ^
    --exclude-module=zipfile ^
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

REM 复制必要的文件
echo.
echo 复制必要的文件到dist目录...

if exist dist (
    REM 复制配置文件
    if exist config.json copy config.json dist\ >nul
    echo  复制: config.json
    
    REM 复制图标文件
    if exist win11_logo.ico copy win11_logo.ico dist\ >nul
    echo  复制: win11_logo.ico
    
    REM 复制动态库目录（如果不存在）
    if not exist dist\libs ( 
        mkdir dist\libs >nul 2>&1
        mkdir dist\libs\windows >nul 2>&1
        mkdir dist\libs\windows\x86_64 >nul 2>&1
        copy libs\windows\x86_64\* dist\libs\windows\x86_64\ >nul
        echo  复制: libs\windows\x86_64\* 
    )
    
    REM 显示输出文件信息
    for %%i in (dist\LGV2_Test_System.exe) do set "EXE_SIZE=%%~zi"
    set /a EXE_SIZE_MB=%EXE_SIZE% / 1048576
    set /a EXE_SIZE_KB=(%EXE_SIZE% %% 1048576) / 1024
    
    echo.
    echo 生成的可执行文件: dist\LGV2_Test_System.exe
    echo 文件大小: %EXE_SIZE_MB%.%EXE_SIZE_KB% MB
)

echo.
echo ========================================
echo 优化构建完成!
echo ========================================
echo.
echo 优化说明:
echo 1. 移除了不必要的模块
echo 2. 包含了必要的动态库
echo 3. 优化了导入
echo 4. 清理了旧的构建文件
echo.
echo 使用方法:
echo 1. 直接运行 dist\LGV2_Test_System.exe
echo 2. 或运行 LGV2_Test_System.exe
echo.
echo 注意事项:
echo - 确保config.json文件与exe在同一目录
echo - 确保libs目录与exe在同一目录
echo - 首次运行会自动创建数据库文件
echo.
echo 按任意键退出...
pause >nul