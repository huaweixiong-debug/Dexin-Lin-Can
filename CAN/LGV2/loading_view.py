import tkinter as tk
from tkinter import ttk
import sys
import os

class LoadingWindow:
    def __init__(self, root, title="LGV2 Test System", start_message="Initializing..."):
        self.root = root
        self.top = tk.Toplevel(root)
        self.top.title("Loading...")
        
        # Remove window decorations (splash screen style)
        self.top.overrideredirect(True)
        
        # Dimensions
        width = 400
        height = 150
        
        # Center the window
        screen_width = self.top.winfo_screenwidth()
        screen_height = self.top.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.top.geometry(f'{width}x{height}+{x}+{y}')
        
        # Styling
        self.top.configure(bg='#f0f0f0')
        self.style = ttk.Style()
        self.style.configure("TProgressbar", thickness=20)
        
        # Frame
        main_frame = tk.Frame(self.top, bg='#f0f0f0', bd=2, relief=tk.RAISED)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title Label - Use place for absolute positioning
        title_label = tk.Label(main_frame, text=title, font=("Helvetica", 16, "bold"), bg='#f0f0f0', fg='#333')
        title_label.place(relx=0.5, y=30, anchor=tk.CENTER)
        
        # Progress Bar - Use place
        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=300, mode='determinate', style="TProgressbar")
        self.progress.place(relx=0.5, y=80, anchor=tk.CENTER)
        
        # Status Label - Use place and fixed width to prevent overlap/residue
        self.status_label = tk.Label(main_frame, text=start_message, font=("Helvetica", 10), bg='#f0f0f0', fg='#666', width=40)
        self.status_label.place(relx=0.5, y=120, anchor=tk.CENTER)
        
        # Ensure it stays on top
        self.top.lift()
        self.top.attributes('-topmost', True)
        self.top.update()

    def update_progress(self, value, message):
        """Update the progress bar and status message."""
        self.progress['value'] = value
        self.status_label.config(text=message)
        self.top.update_idletasks()
        self.top.update()

    def destroy(self):
        """Close the loading window."""
        self.top.destroy()

if __name__ == "__main__":
    # Test the loading window
    root = tk.Tk()
    root.withdraw()
    loader = LoadingWindow(root)
    import time
    for i in range(101):
        loader.update_progress(i, f"Loading... {i}%")
        time.sleep(0.02)
    loader.destroy()
    root.destroy()
