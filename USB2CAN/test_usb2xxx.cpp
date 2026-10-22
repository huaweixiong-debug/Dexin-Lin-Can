#include <iostream>
#include <windows.h>

int main() {
    // 加载USB2XXX.dll
    HMODULE hDll = LoadLibrary(L"libs\\windows\\x86_64\\USB2XXX.dll");
    if (hDll == NULL) {
        std::cout << "Failed to load USB2XXX.dll" << std::endl;
        std::cout << "Error code: " << GetLastError() << std::endl;
        return 1;
    }
    std::cout << "USB2XXX.dll loaded successfully!" << std::endl;
    
    // 尝试获取USB_ScanDevice函数
    typedef int (*USB_ScanDeviceFunc)(unsigned int*);
    USB_ScanDeviceFunc USB_ScanDevice = (USB_ScanDeviceFunc)GetProcAddress(hDll, "USB_ScanDevice");
    if (USB_ScanDevice == NULL) {
        std::cout << "Failed to get USB_ScanDevice function" << std::endl;
        std::cout << "Error code: " << GetLastError() << std::endl;
        FreeLibrary(hDll);
        return 1;
    }
    std::cout << "Got USB_ScanDevice function successfully!" << std::endl;
    
    // 扫描设备
    unsigned int DevHandles[20];
    int ret = USB_ScanDevice(DevHandles);
    std::cout << "USB_ScanDevice returned: " << ret << std::endl;
    if (ret > 0) {
        std::cout << "Found " << ret << " devices!" << std::endl;
        for (int i = 0; i < ret; i++) {
            std::cout << "Device " << i << ": " << DevHandles[i] << std::endl;
        }
    }
    
    // 释放DLL
    FreeLibrary(hDll);
    std::cout << "USB2XXX.dll unloaded successfully!" << std::endl;
    
    return 0;
}
