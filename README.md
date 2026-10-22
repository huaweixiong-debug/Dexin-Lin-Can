# Dexin-Lin-Can

德鑫 PTC 老化测试程序（LIN / CAN）。

## 目录结构

- `LGV2/`：老化测试主程序。Python 3.13 + tkinter，负责 USB2CAN / USB2LIN 通讯、西门子 S7 PLC 交互、SQLite 数据记录和测试流程控制。
- `USB2CAN/`：USB2CAN 设备调试、DBC 解析和通讯测试脚本。
- 根目录：DBC / Excel 协议文件、OPC 配置、启动脚本和测试辅助脚本。

## 运行环境

- Windows 10 / 11
- Python 3.13
- 依赖见 `LGV2/requirements.txt`（`python-snap7`、`pyinstaller` 等）
- 硬件：USB2XXX / USB2LIN 适配器、西门子 S7 系列 PLC

## 启动

```bat
cd LGV2
python Main.py
```

也可以使用根目录的 `run_python.bat` / `run_python_script.bat`。

## 仓库说明

- 仓库只保留源码、配置和协议文件，不包含 `.venv`、`logs`、`build`、`dist`、运行数据库、日志和打包产物。
- `LGV2/USB2XXX.dll`、`LGV2/libusb-1.0.dll`、`LGV2/snap7.dll` 为运行所需二进制依赖，已随仓库保留。
- 老化测试相关的产品协议和故障判据见根目录的 DBC / Excel 文件。
