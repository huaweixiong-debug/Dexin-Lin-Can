#coding:utf-8
import can
import time
import os

# 尝试使用python-can库实现CAN通讯
try:
    # 打印python-can库的版本
    print(f"python-can版本: {can.__version__}")
    
    # 列出所有可用的接口
    print("\n=== 可用的CAN接口 ===")
    interfaces = can.VALID_INTERFACES
    for interface in interfaces:
        print(f"- {interface}")
    
    # 尝试列出所有可用的通道
    print("\n=== 尝试列出所有可用的通道 ===")
    try:
        # 尝试使用socketcan接口（如果可用）
        if "socketcan" in interfaces:
            print("尝试使用socketcan接口...")
            channels = can.interfaces.socketcan.SocketcanBus.list_channels()
            print(f"socketcan通道: {channels}")
        
        # 尝试使用usb2can接口（如果可用）
        if "usb2can" in interfaces:
            print("尝试使用usb2can接口...")
            # 注意：usb2can接口可能需要不同的方式列出通道
            try:
                channels = can.interfaces.usb2can.Usb2CanBus.list_channels()
                print(f"usb2can通道: {channels}")
            except Exception as e:
                print(f"无法列出usb2can通道: {str(e)}")
        
        # 尝试使用vector接口（如果可用）
        if "vector" in interfaces:
            print("尝试使用vector接口...")
            try:
                channels = can.interfaces.vector.VectorBus.list_channels()
                print(f"vector通道: {channels}")
            except Exception as e:
                print(f"无法列出vector通道: {str(e)}")
        
        # 尝试使用kvaser接口（如果可用）
        if "kvaser" in interfaces:
            print("尝试使用kvaser接口...")
            try:
                channels = can.interfaces.kvaser.KvaserBus.list_channels()
                print(f"kvaser通道: {channels}")
            except Exception as e:
                print(f"无法列出kvaser通道: {str(e)}")
        
        # 尝试使用pcan接口（如果可用）
        if "pcan" in interfaces:
            print("尝试使用pcan接口...")
            try:
                channels = can.interfaces.pcan.PcanBus.list_channels()
                print(f"pcan通道: {channels}")
            except Exception as e:
                print(f"无法列出pcan通道: {str(e)}")
        
        # 尝试使用serial接口（如果可用）
        if "serial" in interfaces:
            print("尝试使用serial接口...")
            try:
                channels = can.interfaces.serial.SerialBus.list_channels()
                print(f"serial通道: {channels}")
            except Exception as e:
                print(f"无法列出serial通道: {str(e)}")
    except Exception as e:
        print(f"无法列出通道: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用usb2can接口创建CAN总线
    print("\n=== 尝试使用usb2can接口创建CAN总线 ===")
    try:
        # 尝试使用通道0
        bus = can.interface.Bus(bustype="usb2can", channel=0, bitrate=500000)
        print("成功创建CAN总线！")
        print(f"总线类型: {bus.__class__.__name__}")
        print(f"通道: {bus.channel}")
        print(f"波特率: {bus.bitrate}")
        
        # 尝试发送一条CAN消息
        print("\n尝试发送一条CAN消息...")
        msg = can.Message(
            arbitration_id=0x4E0,  # PTC功率设置和使能的CAN ID
            data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],  # 8字节数据
            is_extended_id=False  # 标准ID
        )
        bus.send(msg)
        print("CAN消息发送成功！")
        
        # 尝试接收一条CAN消息
        print("\n尝试接收一条CAN消息（等待5秒）...")
        msg = bus.recv(5.0)
        if msg is not None:
            print(f"接收到CAN消息: {msg}")
        else:
            print("未接收到CAN消息。")
        
        # 关闭总线
        bus.shutdown()
        print("CAN总线已关闭。")
    except Exception as e:
        print(f"无法使用usb2can接口: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用其他可能的接口
    print("\n=== 尝试使用其他可能的接口 ===")
    possible_interfaces = ["socketcan", "vector", "kvaser", "pcan", "serial"]
    for interface in possible_interfaces:
        if interface in interfaces:
            print(f"\n尝试使用{interface}接口...")
            try:
                # 尝试使用默认通道
                bus = can.interface.Bus(bustype=interface, channel=0, bitrate=500000)
                print(f"成功创建{interface}总线！")
                print(f"总线类型: {bus.__class__.__name__}")
                print(f"通道: {bus.channel}")
                print(f"波特率: {bus.bitrate}")
                
                # 关闭总线
                bus.shutdown()
                print(f"{interface}总线已关闭。")
            except Exception as e:
                print(f"无法使用{interface}接口: {str(e)}")
    
    # 尝试使用虚拟接口（用于测试）
    print("\n=== 尝试使用虚拟接口（用于测试） ===")
    try:
        bus = can.interface.Bus(bustype="virtual", channel=0, bitrate=500000)
        print("成功创建虚拟CAN总线！")
        print(f"总线类型: {bus.__class__.__name__}")
        print(f"通道: {bus.channel}")
        print(f"波特率: {bus.bitrate}")
        
        # 尝试发送一条CAN消息
        print("\n尝试发送一条CAN消息...")
        msg = can.Message(
            arbitration_id=0x4E0,  # PTC功率设置和使能的CAN ID
            data=[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],  # 8字节数据
            is_extended_id=False  # 标准ID
        )
        bus.send(msg)
        print("CAN消息发送成功！")
        
        # 尝试接收一条CAN消息
        print("\n尝试接收一条CAN消息（等待5秒）...")
        msg = bus.recv(5.0)
        if msg is not None:
            print(f"接收到CAN消息: {msg}")
        else:
            print("未接收到CAN消息。")
        
        # 关闭总线
        bus.shutdown()
        print("虚拟CAN总线已关闭。")
    except Exception as e:
        print(f"无法使用虚拟接口: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用PCAN Basic接口（如果可用）
    print("\n=== 尝试使用PCAN Basic接口 ===")
    try:
        # 检查PCAN Basic DLL是否存在
        system_dir = os.environ.get("SystemRoot", "C:\Windows")
        pcan_dll_path = os.path.join(system_dir, "System32", "PCANBasic.dll")
        print(f"PCAN Basic DLL路径: {pcan_dll_path}")
        print(f"PCAN Basic DLL存在: {os.path.exists(pcan_dll_path)}")
        
        if os.path.exists(pcan_dll_path):
            # 尝试使用PCAN Basic接口
            bus = can.interface.Bus(bustype="pcan", channel="PCAN_USBBUS1", bitrate=500000)
            print("成功创建PCAN Basic总线！")
            print(f"总线类型: {bus.__class__.__name__}")
            print(f"通道: {bus.channel}")
            print(f"波特率: {bus.bitrate}")
            
            # 关闭总线
            bus.shutdown()
            print("PCAN Basic总线已关闭。")
    except Exception as e:
        print(f"无法使用PCAN Basic接口: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用CANable接口（如果可用）
    print("\n=== 尝试使用CANable接口 ===")
    try:
        # 尝试使用CANable接口
        bus = can.interface.Bus(bustype="slcan", channel="COM1", bitrate=500000)
        print("成功创建CANable总线！")
        print(f"总线类型: {bus.__class__.__name__}")
        print(f"通道: {bus.channel}")
        print(f"波特率: {bus.bitrate}")
        
        # 关闭总线
        bus.shutdown()
        print("CANable总线已关闭。")
    except Exception as e:
        print(f"无法使用CANable接口: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 尝试使用SocketCAN虚拟接口（如果可用）
    print("\n=== 尝试使用SocketCAN虚拟接口 ===")
    try:
        # 尝试使用SocketCAN虚拟接口
        bus = can.interface.Bus(bustype="socketcan", channel="vcan0", bitrate=500000)
        print("成功创建SocketCAN虚拟总线！")
        print(f"总线类型: {bus.__class__.__name__}")
        print(f"通道: {bus.channel}")
        print(f"波特率: {bus.bitrate}")
        
        # 关闭总线
        bus.shutdown()
        print("SocketCAN虚拟总线已关闭。")
    except Exception as e:
        print(f"无法使用SocketCAN虚拟接口: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 打印所有可用的总线配置
    print("\n=== 所有可用的总线配置 ===")
    try:
        configs = can.util.load_config()
        print(f"配置: {configs}")
    except Exception as e:
        print(f"无法加载配置: {str(e)}")
    
    # 尝试使用配置文件中的总线
    print("\n=== 尝试使用配置文件中的总线 ===")
    try:
        bus = can.interface.Bus()
        print("成功创建配置文件中的总线！")
        print(f"总线类型: {bus.__class__.__name__}")
        print(f"通道: {bus.channel}")
        print(f"波特率: {bus.bitrate}")
        
        # 关闭总线
        bus.shutdown()
        print("配置文件中的总线已关闭。")
    except Exception as e:
        print(f"无法使用配置文件中的总线: {str(e)}")
        import traceback
        traceback.print_exc()
    
except Exception as e:
    print(f"错误: {str(e)}")
    import traceback
    traceback.print_exc()
