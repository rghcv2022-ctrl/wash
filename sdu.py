import os
import sys
import shutil
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ================= 配置区域 =================
# 大文件扫描阈值 (MB)
LARGE_FILE_THRESHOLD_MB = 500

# 清理目标配置
CLEAN_TARGETS = {
    "系统临时文件": [
        os.environ.get("TEMP"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Prefetch"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "LogFiles"),
    ],
    "Windows 更新缓存": [
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SoftwareDistribution", "Download")
    ],
    "浏览器缓存": [
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Cache"),
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Code Cache"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Cache"),
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Code Cache"),
    ],
    "开发者垃圾 (Conda/Pip/Code/NPM)": [
        os.path.expanduser(r"~\AppData\Local\pip\cache"),
        os.path.expanduser(r"~\AppData\Local\npm-cache"),
        os.path.expanduser(r"~\AppData\Roaming\Code\CachedData"),
        os.path.expanduser(r"~\AppData\Roaming\Code\User\workspaceStorage"),
        os.path.expanduser(r"~\.gradle\caches"),
    ],
    "用户崩溃转储": [
        os.path.expanduser(r"~\AppData\Local\CrashDumps"),
    ]
}

# ================= 核心逻辑类 =================

class CleanerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("zht C盘深度清理大师 v2.0")
        self.root.geometry("900x650")
        
        # 样式设置
        style = ttk.Style()
        style.theme_use('clam')
        
        # 检查权限
        if not self.is_admin():
            messagebox.showwarning("权限警告", "请以管理员身份重启本程序，否则无法清理系统文件！")
            self.restart_as_admin()

        self.create_widgets()

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def restart_as_admin(self):
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    def create_widgets(self):
        # 主选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: 垃圾清理
        self.tab_clean = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_clean, text=" 🧹 一键垃圾清理 ")
        self.setup_clean_tab()

        # Tab 2: 大文件管理
        self.tab_large = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_large, text=" 🐘 大文件扫描 ")
        self.setup_large_file_tab()

        # Tab 3: 系统工具
        self.tab_tools = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_tools, text=" 🛠️ 系统强力工具 ")
        self.setup_tools_tab()

        # 底部日志栏
        self.log_frame = ttk.LabelFrame(self.root, text="操作日志")
        self.log_frame.pack(fill='both', expand=False, padx=10, pady=5, side='bottom')
        
        self.log_text = tk.Text(self.log_frame, height=8, state='disabled', bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.log_frame, orient='vertical', command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text['yscrollcommand'] = scrollbar.set

    def log(self, message):
        """向日志框输出信息"""
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + "\n")
        self.log_text.see('end')
        self.log_text.config(state='disabled')
        self.root.update_idletasks()

    # ================= Tab 1: 垃圾清理逻辑 =================
    def setup_clean_tab(self):
        frame = ttk.Frame(self.tab_clean)
        frame.pack(fill='both', expand=True, padx=20, pady=20)

        self.check_vars = {}
        row = 0
        for category in CLEAN_TARGETS:
            var = tk.BooleanVar(value=True)
            self.check_vars[category] = var
            chk = ttk.Checkbutton(frame, text=category, variable=var)
            chk.grid(row=row, column=0, sticky="w", pady=5)
            row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, sticky="ew", pady=15)
        
        btn_scan = ttk.Button(frame, text="开始深度清理", command=self.start_clean_thread)
        btn_scan.grid(row=row+1, column=0, pady=10, ipady=5)

    def start_clean_thread(self):
        threading.Thread(target=self.run_clean, daemon=True).start()

    def run_clean(self):
        self.log(">>> 开始清理流程...")
        total_freed = 0
        
        # 特殊处理：停止 Windows 更新服务
        if self.check_vars["Windows 更新缓存"].get():
            self.log("正在停止 Windows Update 服务以释放文件锁...")
            subprocess.run("net stop wuauserv", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("net stop bits", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for category, paths in CLEAN_TARGETS.items():
            if not self.check_vars[category].get():
                continue
            
            self.log(f"正在扫描: {category}...")
            for path in paths:
                if path and os.path.exists(path):
                    freed = self.clean_directory(path)
                    total_freed += freed
        
        # 开发者工具命令清理
        if self.check_vars["开发者垃圾 (Conda/Pip/Code/NPM)"].get():
            self.clean_dev_tools()

        # 重启服务
        if self.check_vars["Windows 更新缓存"].get():
            self.log("正在重启 Windows Update 服务...")
            subprocess.run("net start wuauserv", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run("net start bits", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.log(f"=======================================")
        self.log(f"清理完成！本次释放约 {self.format_bytes(total_freed)} 空间。")
        self.log(f"=======================================")
        messagebox.showinfo("完成", f"清理结束！释放约 {self.format_bytes(total_freed)}")

    def clean_directory(self, folder_path):
        size_freed = 0
        try:
            for root, dirs, files in os.walk(folder_path, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        size = os.path.getsize(file_path)
                        os.remove(file_path)
                        size_freed += size
                    except: pass
                for name in dirs:
                    try: os.rmdir(os.path.join(root, name))
                    except: pass
        except Exception as e:
            self.log(f"错误: 无法访问 {folder_path}")
        return size_freed

    def clean_dev_tools(self):
        self.log("正在调用 Conda/Pip 清理命令...")
        if shutil.which("conda"):
            try:
                subprocess.run("conda clean --all -y", shell=True, stdout=subprocess.DEVNULL)
                self.log("  - Conda 缓存已清理")
            except: pass
        
        if shutil.which("pip"):
            try:
                subprocess.run("pip cache purge", shell=True, stdout=subprocess.DEVNULL)
                self.log("  - Pip 缓存已清理")
            except: pass

    # ================= Tab 2: 大文件扫描逻辑 =================
    def setup_large_file_tab(self):
        frame = ttk.Frame(self.tab_large)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        # 顶部控制栏
        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill='x', pady=5)
        
        ttk.Label(ctrl_frame, text="扫描 C 盘大于 (MB):").pack(side='left')
        self.entry_threshold = ttk.Entry(ctrl_frame, width=10)
        self.entry_threshold.insert(0, str(LARGE_FILE_THRESHOLD_MB))
        self.entry_threshold.pack(side='left', padx=5)
        
        btn_scan = ttk.Button(ctrl_frame, text="开始扫描", command=self.start_scan_thread)
        btn_scan.pack(side='left', padx=10)

        btn_del = ttk.Button(ctrl_frame, text="删除选中文件", command=self.delete_selected_large_file)
        btn_del.pack(side='right', padx=10)

        # 表格视图
        columns = ("size", "path")
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading("size", text="大小")
        self.tree.heading("path", text="文件路径")
        self.tree.column("size", width=100, anchor='e')
        self.tree.column("path", width=600, anchor='w')
        
        # 滚动条
        ysb = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        ysb.pack(side='right', fill='y')

    def start_scan_thread(self):
        threshold = int(self.entry_threshold.get())
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self.scan_large_files, args=(threshold,), daemon=True).start()

    def scan_large_files(self, threshold_mb):
        self.log(f">>> 正在全盘扫描 C 盘大于 {threshold_mb}MB 的文件 (请耐心等待)...")
        limit_bytes = threshold_mb * 1024 * 1024
        
        files_found = []
        # 跳过系统敏感目录，防止扫描死循环或权限报错
        skip_dirs = ["Windows\\WinSxS", "Windows\\servicing", "Windows\\System32"]
        
        for root, dirs, files in os.walk("C:\\"):
            # 过滤敏感目录
            if any(s in root for s in skip_dirs):
                continue
                
            for name in files:
                try:
                    path = os.path.join(root, name)
                    size = os.path.getsize(path)
                    if size > limit_bytes:
                        files_found.append((size, path))
                except: pass
        
        # 排序并插入表格
        files_found.sort(key=lambda x: x[0], reverse=True)
        
        for size, path in files_found:
            self.tree.insert("", "end", values=(self.format_bytes(size), path))
            
        self.log(f"扫描完成，找到 {len(files_found)} 个大文件。")

    def delete_selected_large_file(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("提示", "请先选择一个文件")
            return
            
        item = self.tree.item(selected_item)
        path = item['values'][1]
        
        if messagebox.askyesno("危险操作确认", f"确定要永久删除此文件吗？\n\n{path}"):
            try:
                os.remove(path)
                self.tree.delete(selected_item)
                self.log(f"已删除大文件: {path}")
            except Exception as e:
                messagebox.showerror("错误", str(e))

    # ================= Tab 3: 系统工具 =================
    def setup_tools_tab(self):
        frame = ttk.Frame(self.tab_tools)
        frame.pack(fill='both', expand=True, padx=30, pady=30)
        
        ttk.Label(frame, text="⚠️ 以下操作调用 Windows 系统原生命令，请按需使用", foreground="red").pack(pady=10)

        btn_dism = ttk.Button(frame, text="[推荐] 清理 WinSxS 组件 (DISM)", command=lambda: self.run_sys_cmd("dism"))
        btn_dism.pack(fill='x', pady=5)

        btn_hiber = ttk.Button(frame, text="关闭休眠 (释放 Hiberfil.sys)", command=lambda: self.run_sys_cmd("hiber"))
        btn_hiber.pack(fill='x', pady=5)
        
        btn_disk = ttk.Button(frame, text="打开 Windows 磁盘清理器", command=lambda: self.run_sys_cmd("cleanmgr"))
        btn_disk.pack(fill='x', pady=5)
        
        btn_compact = ttk.Button(frame, text="CompactOS 系统压缩 (省 2-4GB)", command=lambda: self.run_sys_cmd("compact"))
        btn_compact.pack(fill='x', pady=5)

    def run_sys_cmd(self, type_):
        if type_ == "dism":
            cmd = "dism /online /cleanup-image /startcomponentcleanup"
            msg = "正在深度清理 WinSxS 组件存储..."
        elif type_ == "hiber":
            cmd = "powercfg -h off"
            msg = "正在关闭休眠功能..."
        elif type_ == "cleanmgr":
            subprocess.Popen("cleanmgr /d c")
            self.log("已启动 Windows 磁盘清理工具")
            return
        elif type_ == "compact":
            cmd = "compact.exe /CompactOS:always"
            msg = "正在执行系统压缩..."
            
        self.log(msg)
        threading.Thread(target=self.execute_cmd_thread, args=(cmd,), daemon=True).start()

    def execute_cmd_thread(self, cmd):
        try:
            subprocess.run(cmd, shell=True, check=True)
            self.log("命令执行成功！")
            messagebox.showinfo("成功", "操作已成功完成")
        except Exception as e:
            self.log(f"执行出错: {e}")

    # ================= 辅助函数 =================
    def format_bytes(self, size):
        power = 2**10
        n = 0
        power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size > power:
            size /= power
            n += 1
        return f"{size:.2f} {power_labels[n]}B"

if __name__ == "__main__":
    root = tk.Tk()
    app = CleanerApp(root)
    root.mainloop()