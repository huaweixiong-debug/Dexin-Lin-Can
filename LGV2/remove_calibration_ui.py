# Script to remove old voltage calibration UI from settings page

with open('test_monitor_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start and end of the old calibration UI code
start_marker = '# Voltage Calibration on the right'
end_marker = '# Wind Speed Control Section'

if start_marker in content and end_marker in content:
    # Find the positions
    start_pos = content.find(start_marker)
    end_pos = content.find(end_marker)
    
    # Remove the old calibration UI code
    new_content = content[:start_pos] + content[end_pos:]
    
    # Write the modified content back
    with open('test_monitor_ui.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("成功删除旧的电压校准UI代码")
else:
    print("未找到需要删除的代码段")
