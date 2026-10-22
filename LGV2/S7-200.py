import snap7
import time
import os
from snap7.util import get_bool
import xml.etree.ElementTree as ET
from collections import defaultdict

# --- 配置参数 ---
INTERVAL = 2
RACK = 0
SLOT = 1

# 尝试不同的XML文件路径
XML_PATHS = [
    'OPCOPC.xml',
    './OPCOPC.xml',
    'D:/老化CAN通讯/OPCOPC.xml',
    'd:/老化CAN通讯/OPCOPC.xml',
    'OPC1_5.xml',
    './OPC1_5.xml',
    'D:/data/OPC1_5.xml',
    'D:/PTC LIN/OPC1_5.xml',
    os.path.join(os.path.dirname(__file__), 'OPCOPC.xml'),
    os.path.join(os.path.dirname(__file__), 'OPC1_5.xml')
]

# ===================================================================
# 核心修复：适用于 snap7 2.0+ 版本
# ===================================================================

# 内存区域枚举 - 适用于 snap7 2.0+
try:
    print("使用 snap7 2.0+ 的内存区域定义")
    PLC_MEM_AREA = snap7.Area.MK  # M区
    print(f"✅ M区类型: {PLC_MEM_AREA}")
except AttributeError as e:
    print(f"❌ 无法获取内存区域类型: {e}")
    print("尝试使用硬编码值...")
    PLC_MEM_AREA = 0x83  # M区
    print(f"使用硬编码值: M区={PLC_MEM_AREA}")


# ===================================================================
# 解析OPC配置文件，获取标签信息
# ===================================================================

def parse_opc_config():
    """解析OPC配置文件，提取所有M位标签"""
    tags_by_plc = defaultdict(list)

    xml_file_path = None

    # 尝试不同的文件路径
    for path in XML_PATHS:
        if os.path.exists(path):
            xml_file_path = path
            print(f"✅ 找到XML文件: {xml_file_path}")
            break

    if not xml_file_path:
        print("❌ 未找到OPC1_5.xml文件，请检查文件路径")
        print("已尝试以下路径:")
        for path in XML_PATHS:
            print(f"  - {path}")
        print("\n⚠️  使用硬编码标签配置...")

        # 硬编码标签配置（基于OPC1_5.xml内容）
        tags_by_plc = {
            '192.168.10.180': [
                # PLC 1-5 (第一个通道)
                {'name': '1测试不合格电脑-plc', 'address': 'M1.5', 'channel': '1-5', 'device': '1-5'},
                {'name': '1测试合格电脑-plc', 'address': 'M1.4', 'channel': '1-5', 'device': '1-5'},
                {'name': '1复位信号plc-电脑', 'address': 'M1.2', 'channel': '1-5', 'device': '1-5'},
                {'name': '1急停信号plc-电脑', 'address': 'M1.3', 'channel': '1-5', 'device': '1-5'},
                {'name': '1启动信号plc-电脑', 'address': 'M1.1', 'channel': '1-5', 'device': '1-5'},
                {'name': '1扫码OK', 'address': 'M1.0', 'channel': '1-5', 'device': '1-5'},
                {'name': '2测试不合格电脑-plc', 'address': 'M2.5', 'channel': '1-5', 'device': '1-5'},
                {'name': '2测试合格电脑-plc', 'address': 'M2.4', 'channel': '1-5', 'device': '1-5'},
                {'name': '2复位信号plc-电脑', 'address': 'M2.2', 'channel': '1-5', 'device': '1-5'},
                {'name': '2急停信号plc-电脑', 'address': 'M2.3', 'channel': '1-5', 'device': '1-5'},
                {'name': '2启动信号plc-电脑', 'address': 'M2.1', 'channel': '1-5', 'device': '1-5'},
                {'name': '2扫码OK', 'address': 'M2.0', 'channel': '1-5', 'device': '1-5'},
                {'name': '3测试不合格电脑-plc', 'address': 'M3.5', 'channel': '1-5', 'device': '1-5'},
                {'name': '3测试合格电脑-plc', 'address': 'M3.4', 'channel': '1-5', 'device': '1-5'},
                {'name': '3复位信号plc-电脑', 'address': 'M3.2', 'channel': '1-5', 'device': '1-5'},
                {'name': '3急停信号plc-电脑', 'address': 'M3.3', 'channel': '1-5', 'device': '1-5'},
                {'name': '3启动信号plc-电脑', 'address': 'M3.1', 'channel': '1-5', 'device': '1-5'},
                {'name': '3扫码OK', 'address': 'M3.0', 'channel': '1-5', 'device': '1-5'},
                {'name': '4测试不合格电脑-plc', 'address': 'M4.5', 'channel': '1-5', 'device': '1-5'},
                {'name': '4测试合格电脑-plc', 'address': 'M4.4', 'channel': '1-5', 'device': '1-5'},
                {'name': '4复位信号plc-电脑', 'address': 'M4.2', 'channel': '1-5', 'device': '1-5'},
                {'name': '4急停信号plc-电脑', 'address': 'M4.3', 'channel': '1-5', 'device': '1-5'},
                {'name': '4启动信号plc-电脑', 'address': 'M4.1', 'channel': '1-5', 'device': '1-5'},
                {'name': '4扫码OK', 'address': 'M4.0', 'channel': '1-5', 'device': '1-5'},
                {'name': '5测试不合格电脑-plc', 'address': 'M5.5', 'channel': '1-5', 'device': '1-5'},
                {'name': '5测试合格电脑-plc', 'address': 'M5.4', 'channel': '1-5', 'device': '1-5'},
                {'name': '5复位信号plc-电脑', 'address': 'M5.2', 'channel': '1-5', 'device': '1-5'},
                {'name': '5急停信号plc-电脑', 'address': 'M5.3', 'channel': '1-5', 'device': '1-5'},
                {'name': '5启动信号plc-电脑', 'address': 'M5.1', 'channel': '1-5', 'device': '1-5'},
                {'name': '5扫码OK', 'address': 'M5.0', 'channel': '1-5', 'device': '1-5'},
            ],
            '192.168.10.181': [
                # PLC 6-10 (第二个通道)
                {'name': '6测试不合格电脑-plc', 'address': 'M1.5', 'channel': '6-10', 'device': '6-10'},
                {'name': '6测试合格电脑-plc', 'address': 'M1.4', 'channel': '6-10', 'device': '6-10'},
                {'name': '6复位信号plc-电脑', 'address': 'M1.2', 'channel': '6-10', 'device': '6-10'},
                {'name': '6急停信号plc-电脑', 'address': 'M1.3', 'channel': '6-10', 'device': '6-10'},
                {'name': '6启动信号plc-电脑', 'address': 'M1.1', 'channel': '6-10', 'device': '6-10'},
                {'name': '6扫码OK', 'address': 'M1.0', 'channel': '6-10', 'device': '6-10'},
                {'name': '7测试不合格电脑-plc', 'address': 'M2.5', 'channel': '6-10', 'device': '6-10'},
                {'name': '7测试合格电脑-plc', 'address': 'M2.4', 'channel': '6-10', 'device': '6-10'},
                {'name': '7复位信号plc-电脑', 'address': 'M2.2', 'channel': '6-10', 'device': '6-10'},
                {'name': '7急停信号plc-电脑', 'address': 'M2.3', 'channel': '6-10', 'device': '6-10'},
                {'name': '7启动信号plc-电脑', 'address': 'M2.1', 'channel': '6-10', 'device': '6-10'},
                {'name': '7扫码OK', 'address': 'M2.0', 'channel': '6-10', 'device': '6-10'},
                {'name': '8测试不合格电脑-plc', 'address': 'M3.5', 'channel': '6-10', 'device': '6-10'},
                {'name': '8测试合格电脑-plc', 'address': 'M3.4', 'channel': '6-10', 'device': '6-10'},
                {'name': '8复位信号plc-电脑', 'address': 'M3.2', 'channel': '6-10', 'device': '6-10'},
                {'name': '8急停信号plc-电脑', 'address': 'M3.3', 'channel': '6-10', 'device': '6-10'},
                {'name': '8启动信号plc-电脑', 'address': 'M3.1', 'channel': '6-10', 'device': '6-10'},
                {'name': '8扫码OK', 'address': 'M3.0', 'channel': '6-10', 'device': '6-10'},
                {'name': '9测试不合格电脑-plc', 'address': 'M4.5', 'channel': '6-10', 'device': '6-10'},
                {'name': '9测试合格电脑-plc', 'address': 'M4.4', 'channel': '6-10', 'device': '6-10'},
                {'name': '9复位信号plc-电脑', 'address': 'M4.2', 'channel': '6-10', 'device': '6-10'},
                {'name': '9急停信号plc-电脑', 'address': 'M4.3', 'channel': '6-10', 'device': '6-10'},
                {'name': '9启动信号plc-电脑', 'address': 'M4.1', 'channel': '6-10', 'device': '6-10'},
                {'name': '9扫码OK', 'address': 'M4.0', 'channel': '6-10', 'device': '6-10'},
                {'name': '10测试不合格电脑-plc', 'address': 'M5.5', 'channel': '6-10', 'device': '6-10'},
                {'name': '10测试合格电脑-plc', 'address': 'M5.4', 'channel': '6-10', 'device': '6-10'},
                {'name': '10复位信号plc-电脑', 'address': 'M5.2', 'channel': '6-10', 'device': '6-10'},
                {'name': '10急停信号plc-电脑', 'address': 'M5.3', 'channel': '6-10', 'device': '6-10'},
                {'name': '10启动信号plc-电脑', 'address': 'M5.1', 'channel': '6-10', 'device': '6-10'},
                {'name': '10扫码OK', 'address': 'M5.0', 'channel': '6-10', 'device': '6-10'},
            ]
        }
        return dict(tags_by_plc)

    try:
        # 注册命名空间
        namespaces = {
            'servermain': 'http://www.kepware.com/schemas/servermain'
        }

        # 添加默认命名空间
        ET.register_namespace('', 'http://www.kepware.com/schemas/servermain')

        tree = ET.parse(xml_file_path)
        root = tree.getroot()

        # 查找所有通道
        channels = root.findall('.//servermain:Channel', namespaces)
        print(f"✅ 找到 {len(channels)} 个通道")

        for channel in channels:
            channel_name_elem = channel.find('servermain:Name', namespaces)
            channel_name = channel_name_elem.text if channel_name_elem is not None else "未知"

            # 查找通道下的设备列表
            device_list = channel.find('servermain:DeviceList', namespaces)
            if device_list is None:
                continue

            devices = device_list.findall('servermain:Device', namespaces)
            print(f"  通道 '{channel_name}' 有 {len(devices)} 个设备")

            for device in devices:
                # 获取PLC IP地址
                plc_ip_elem = device.find('servermain:ID', namespaces)
                if plc_ip_elem is None:
                    continue

                plc_ip = plc_ip_elem.text

                # 获取设备名称
                device_name_elem = device.find('servermain:Name', namespaces)
                device_name = device_name_elem.text if device_name_elem is not None else "未知"

                # 查找标签列表
                tag_list = device.find('servermain:TagList', namespaces)
                if tag_list is None:
                    continue

                tags = tag_list.findall('servermain:Tag', namespaces)
                print(f"    设备 '{device_name}' (IP: {plc_ip}) 有 {len(tags)} 个标签")

                for tag in tags:
                    name_elem = tag.find('servermain:Name', namespaces)
                    address_elem = tag.find('servermain:Address', namespaces)

                    if name_elem is not None and address_elem is not None:
                        name = name_elem.text
                        address = address_elem.text

                        # 只处理M位的标签
                        if address and address.startswith('M'):
                            tags_by_plc[plc_ip].append({
                                'name': name,
                                'address': address,
                                'channel': channel_name,
                                'device': device_name
                            })

        print(f"\n✅ 成功解析OPC配置文件:")
        total_tags = 0
        for plc_ip, tags in tags_by_plc.items():
            total_tags += len(tags)
            print(f"  PLC {plc_ip}: {len(tags)} 个标签")

        print(f"\n  总计: {len(tags_by_plc)} 个PLC, {total_tags} 个标签")

        return dict(tags_by_plc)

    except Exception as e:
        print(f"❌ 解析OPC配置文件失败: {e}")
        import traceback
        traceback.print_exc()
        return dict(tags_by_plc)


# ===================================================================

def connect_to_plc(client, plc_ip):
    """连接到指定IP的PLC"""
    try:
        print(f"正在尝试连接到 PLC ({plc_ip})...")
        if client.get_connected():
            client.disconnect()

        client.connect(plc_ip, RACK, SLOT)

        if client.get_connected():
            print(f"✅ 已连接到 PLC ({plc_ip})")
            return True
        else:
            print(f"❌ 连接失败，请检查 IP 地址、网络连接或 PLC 状态。")
            return False
    except Exception as e:
        print(f"❌ 连接时发生错误: {e}")
        return False


def parse_m_address(address):
    """解析M地址，例如 M1.5 -> (1, 5)"""
    try:
        if address.startswith('M'):
            parts = address[1:].split('.')
            if len(parts) == 2:
                byte_addr = int(parts[0])
                bit_addr = int(parts[1])
                return byte_addr, bit_addr
    except:
        pass
    return None, None


def read_m_bits(client, tags):
    """读取指定标签列表的M位状态"""
    results = {}

    if not tags:
        return results

    # 找出需要读取的字节范围
    byte_addresses = set()
    for tag in tags:
        byte_addr, _ = parse_m_address(tag['address'])
        if byte_addr is not None:
            byte_addresses.add(byte_addr)

    if not byte_addresses:
        return results

    # 计算读取范围
    min_byte = min(byte_addresses)
    max_byte = max(byte_addresses)
    byte_count = max_byte - min_byte + 1

    try:
        # 读取连续的字节块
        data = client.read_area(PLC_MEM_AREA, 0, min_byte, byte_count)

        # 解析每个标签的状态
        for tag in tags:
            byte_addr, bit_addr = parse_m_address(tag['address'])
            if byte_addr is not None and bit_addr is not None:
                # 计算在读取数据中的索引
                data_index = byte_addr - min_byte
                if 0 <= data_index < byte_count and 0 <= bit_addr <= 7:
                    state = get_bool(data, data_index, bit_addr)
                    results[tag['name']] = {
                        'address': tag['address'],
                        'state': state,
                        'channel': tag.get('channel', ''),
                        'device': tag.get('device', '')
                    }

        return results
    except Exception as e:
        print(f"读取M位时发生错误: {e}")
        return None


def monitor_all_plcs_complete():
    """监控所有PLC数据，完整显示所有标签"""
    print("\n" + "=" * 80)
    print("开始监控所有PLC (完整日志模式)")
    print("=" * 80)

    # 解析OPC配置文件
    tags_by_plc = parse_opc_config()

    if not tags_by_plc:
        print("❌ 没有找到可监控的PLC")
        return

    print(f"\n✅ 发现 {len(tags_by_plc)} 个PLC，开始连接...")

    # 为每个PLC创建独立的客户端
    clients = {}
    connected_plcs = []

    for plc_ip, tags in tags_by_plc.items():
        client = snap7.Client()
        if connect_to_plc(client, plc_ip):
            clients[plc_ip] = {
                'client': client,
                'tags': tags
            }
            connected_plcs.append(plc_ip)
        else:
            print(f"❌ 无法连接到 PLC {plc_ip}，跳过")
            if plc_ip in clients:
                del clients[plc_ip]

    if not clients:
        print("❌ 没有成功连接到任何PLC")
        return

    print(f"\n✅ 已成功连接到 {len(connected_plcs)} 个PLC: {', '.join(connected_plcs)}")
    print("按 Ctrl+C 停止监控...\n")

    try:
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                print(f"\n[第{cycle_count}次读取] {timestamp}")
                print("=" * 80)

                all_results = {}

                # 读取所有PLC的数据
                for plc_ip, plc_info in clients.items():
                    client = plc_info['client']
                    tags = plc_info['tags']

                    # 读取该PLC的M位状态
                    m_bits = read_m_bits(client, tags)

                    if m_bits is not None:
                        all_results[plc_ip] = m_bits
                        print(f"\nPLC: {plc_ip} ({len(tags)}个标签)")
                        print("-" * 60)

                        # 完整显示所有标签
                        for tag_name in sorted(m_bits.keys()):
                            tag_info = m_bits[tag_name]
                            status = "ON" if tag_info['state'] else "OFF"
                            status_symbol = "🔴" if tag_info['state'] else "⚪"
                            print(f"{status_symbol} {tag_name:25} [{tag_info['address']:5}] : {status}")
                    else:
                        print(f"\nPLC: {plc_ip} - 读取失败")
                        print("-" * 60)

                print("\n" + "=" * 80)

                # 显示摘要信息
                print("📊 摘要统计:")
                for plc_ip, m_bits in all_results.items():
                    if m_bits:
                        on_count = sum(1 for tag_info in m_bits.values() if tag_info['state'])
                        off_count = len(m_bits) - on_count
                        print(f"  {plc_ip}: {on_count}个ON, {off_count}个OFF")

                time.sleep(INTERVAL)

            except KeyboardInterrupt:
                print("\n\n🛑 用户中断，正在断开所有连接...")
                break

            except Exception as e:
                print(f"\n⚠️  读取数据时发生错误: {e}")
                print("等待5秒后重试...")
                time.sleep(5)

                # 尝试重新连接所有PLC
                print("尝试重新连接所有PLC...")
                for plc_ip, plc_info in list(clients.items()):
                    client = plc_info['client']
                    if client.get_connected():
                        client.disconnect()

                    new_client = snap7.Client()
                    if connect_to_plc(new_client, plc_ip):
                        clients[plc_ip]['client'] = new_client
                        print(f"✅ 重新连接到 {plc_ip}")
                    else:
                        print(f"❌ 重新连接到 {plc_ip} 失败")
                        del clients[plc_ip]

    finally:
        # 关闭所有连接
        print("\n" + "=" * 80)
        print("正在关闭所有PLC连接...")
        for plc_ip, plc_info in clients.items():
            client = plc_info['client']
            if client.get_connected():
                client.disconnect()
                print(f"✅ PLC {plc_ip} 连接已关闭")

        print("\n📋 监控结束")
        print("=" * 80)


def test_snap7_connection():
    """测试 snap7 连接的基本功能"""
    print("测试 snap7 连接...")

    # 测试读取枚举
    print("测试可用的 Area 枚举:")
    try:
        for area_name in dir(snap7.Area):
            if not area_name.startswith('_'):
                area_value = getattr(snap7.Area, area_name)
                print(f"  {area_name}: {area_value}")
    except:
        print("  无法访问 Area 枚举")

    # 创建一个简单的客户端
    client = snap7.Client()
    print(f"\n创建的客户端: {client}")
    print(f"客户端类型: {type(client)}")


if __name__ == "__main__":
    # 先测试 snap7 功能
    test_snap7_connection()

    print("\n" + "=" * 80)
    print("PLC 数据监控系统 - 完整日志模式")
    print("=" * 80)

    # 直接开始监控所有PLC（完整日志模式）
    monitor_all_plcs_complete()