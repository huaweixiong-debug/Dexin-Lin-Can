import tkinter as tk
from tkinter import ttk, messagebox
import json
import os

class LoginDialog:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.top = tk.Toplevel(parent)
        self.top.title("用户登录")
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.update_idletasks()
        width = 350
        height = 220
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        
        # 创建主框架
        main_frame = ttk.Frame(self.top, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户名
        ttk.Label(main_frame, text="用户名:").pack(anchor=tk.W, pady=(0, 5))
        self.username_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.username_var, width=30).pack(pady=(0, 15))
        
        # 密码
        ttk.Label(main_frame, text="密码:").pack(anchor=tk.W, pady=(0, 5))
        self.password_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.password_var, show="*", width=30).pack(pady=(0, 20))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 创建一个内部框架来居中按钮
        inner_frame = ttk.Frame(button_frame)
        inner_frame.pack(expand=True)
        
        # 登录按钮
        ttk.Button(inner_frame, text="登录", command=self.on_login, width=10).pack(side=tk.LEFT, padx=(0, 10))
        
        # 取消按钮
        ttk.Button(inner_frame, text="取消", command=self.on_cancel, width=10).pack(side=tk.LEFT)
        
        # 绑定回车键
        self.top.bind('<Return>', lambda e: self.on_login())
    
    def on_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        
        if not username or not password:
            messagebox.showerror("错误", "用户名和密码不能为空")
            return
        
        # 验证用户
        if self.validate_user(username, password):
            # 获取用户角色
            role = self.get_user_role(username)
            self.callback(username, role)
            self.top.destroy()
        else:
            messagebox.showerror("错误", "用户名或密码错误")
    
    def on_cancel(self):
        self.top.destroy()
    
    def validate_user(self, username, password):
        """验证用户凭据"""
        # 这里使用硬编码的测试用户，实际应用中应该从数据库或配置文件读取
        test_users = {
            "admin": "0000",
            "user": "user123",
            "test": "test123"
        }
        
        return username in test_users and test_users[username] == password
    
    def get_user_role(self, username):
        """获取用户角色"""
        # 这里使用硬编码的角色映射，实际应用中应该从数据库或配置文件读取
        role_mapping = {
            "admin": "admin",
            "user": "user",
            "test": "user"
        }
        
        return role_mapping.get(username, "user")

class UserManagementDialog:
    def __init__(self, parent):
        self.parent = parent
        self.top = tk.Toplevel(parent)
        self.top.title("用户管理")
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.update_idletasks()
        width = 400
        height = 300
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        
        # 创建主框架
        main_frame = ttk.Frame(self.top, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户列表
        ttk.Label(main_frame, text="用户列表", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # 列表框
        self.user_listbox = tk.Listbox(main_frame, width=50, height=10)
        self.user_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 添加测试用户
        test_users = ["admin (管理员)", "user (普通用户)", "test (普通用户)"]
        for user in test_users:
            self.user_listbox.insert(tk.END, user)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 按钮
        ttk.Button(button_frame, text="添加用户", command=self.on_add_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="编辑用户", command=self.on_edit_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="删除用户", command=self.on_delete_user).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="关闭", command=self.on_close).pack(side=tk.RIGHT)
    
    def on_add_user(self):
        messagebox.showinfo("提示", "添加用户功能开发中")
    
    def on_edit_user(self):
        messagebox.showinfo("提示", "编辑用户功能开发中")
    
    def on_delete_user(self):
        messagebox.showinfo("提示", "删除用户功能开发中")
    
    def on_close(self):
        self.top.destroy()

class ChangePasswordDialog:
    def __init__(self, parent, username):
        self.parent = parent
        self.username = username
        self.top = tk.Toplevel(parent)
        self.top.title("修改密码")
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.update_idletasks()
        width = 300
        height = 250
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        
        # 创建主框架
        main_frame = ttk.Frame(self.top, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户名显示
        ttk.Label(main_frame, text=f"用户: {username}").pack(anchor=tk.W, pady=(0, 15))
        
        # 旧密码
        ttk.Label(main_frame, text="旧密码:").pack(anchor=tk.W, pady=(0, 5))
        self.old_password_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.old_password_var, show="*", width=30).pack(pady=(0, 10))
        
        # 新密码
        ttk.Label(main_frame, text="新密码:").pack(anchor=tk.W, pady=(0, 5))
        self.new_password_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.new_password_var, show="*", width=30).pack(pady=(0, 10))
        
        # 确认新密码
        ttk.Label(main_frame, text="确认新密码:").pack(anchor=tk.W, pady=(0, 5))
        self.confirm_password_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.confirm_password_var, show="*", width=30).pack(pady=(0, 20))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # 确定按钮
        ttk.Button(button_frame, text="确定", command=self.on_confirm).pack(side=tk.LEFT, padx=(0, 10))
        
        # 取消按钮
        ttk.Button(button_frame, text="取消", command=self.on_cancel).pack(side=tk.LEFT)
    
    def on_confirm(self):
        old_password = self.old_password_var.get().strip()
        new_password = self.new_password_var.get().strip()
        confirm_password = self.confirm_password_var.get().strip()
        
        if not old_password or not new_password or not confirm_password:
            messagebox.showerror("错误", "所有字段不能为空")
            return
        
        if new_password != confirm_password:
            messagebox.showerror("错误", "两次输入的新密码不一致")
            return
        
        # 这里应该验证旧密码并更新密码
        # 实际应用中应该从数据库或配置文件读取和更新
        messagebox.showinfo("成功", "密码修改成功")
        self.top.destroy()
    
    def on_cancel(self):
        self.top.destroy()