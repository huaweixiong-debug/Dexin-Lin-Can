# Dexin-Lin-Can

德鑫 PTC 老化测试程序（LIN / CAN）。

## 目录结构

- `CAN/`：老化 CAN 通讯程序。
  - `CAN/LGV2/`：CAN + LIN 一体化测试主程序。Python 3.13 + tkinter，负责 USB2CAN / USB2LIN 通讯、西门子 S7 PLC 交互、SQLite 数据记录和测试流程控制。
  - `CAN/USB2CAN/`：USB2CAN 设备调试、DBC 解析和通讯测试脚本。
  - `CAN/` 根目录：DBC / Excel 协议文件、`OPCOPC.xml`、`config.json`、启动与测试辅助脚本。
- `LIN/`：老化 LIN 通讯程序。`main.py` 为控制台测试序列入口，支持 A045 / A050 / A063（前风暖）/ A064（后风暖）产品、PLC 和多工位扫码。

## 运行环境

- Windows 10 / 11
- Python 3.13
- 依赖见 `CAN/LGV2/requirements.txt`（`python-snap7`、`pyinstaller` 等）
- 硬件：USB2XXX / USB2LIN 适配器、西门子 S7 系列 PLC、扫码枪

## 启动

CAN / LIN 主程序：

```bat
cd CAN\LGV2
python Main.py
```

LIN 测试序列：

```bat
cd LIN
python main.py config.json --station 1
```

`CAN/run_python.bat` / `CAN/run_python_script.bat` 是使用本机 Miniconda 解释器（`D:\miniconda3\python.exe`）的启动辅助脚本。

## 仓库说明

- 仓库只保留源码、配置和协议文件，不包含 `.venv`、`logs`、`build`、`dist`、运行数据库、日志、测试记录和打包产物。
- `CAN/LGV2/USB2XXX.dll`、`CAN/LGV2/libusb-1.0.dll`、`CAN/LGV2/snap7.dll` 为运行所需二进制依赖，已随仓库保留。
- `CAN/config.json` 和 `LIN/config.json` 含现场 PLC / 扫码枪 IP、设备 SN 等配置；仓库为私有仓库，请勿公开。
