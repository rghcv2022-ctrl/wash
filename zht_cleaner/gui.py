from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .config import (
    APP_NAME,
    APP_VERSION,
    CLEANUP_CATEGORIES,
    DEFAULT_LARGE_FILE_THRESHOLD_MB,
    DEFAULT_SCAN_ROOT,
    SYSTEM_TOOLS,
)
from .core import (
    CleanupSummary,
    LargeFileEntry,
    clean_selected_categories,
    delete_file,
    format_bytes,
    is_admin,
    restart_as_admin,
    run_system_tool,
    scan_large_files,
)


class CleanerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("900x650")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.tree: ttk.Treeview
        self.entry_threshold: ttk.Entry
        self.clean_button: ttk.Button
        self.scan_button: ttk.Button

        self._configure_style()
        self._ensure_admin()
        self._create_widgets()
        self.root.after(100, self._flush_logs)

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    def _ensure_admin(self) -> None:
        if is_admin():
            return

        should_restart = messagebox.askyesno(
            "权限警告",
            "本程序建议以管理员身份运行，否则无法清理系统目录。\n\n是否立即重启为管理员模式？",
        )
        if not should_restart:
            self.root.destroy()
            raise SystemExit(1)

        try:
            restart_as_admin()
        except RuntimeError as exc:
            messagebox.showerror("启动失败", str(exc))

        self.root.destroy()
        raise SystemExit(1)

    def _create_widgets(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_clean = ttk.Frame(notebook)
        self.tab_large = ttk.Frame(notebook)
        self.tab_tools = ttk.Frame(notebook)

        notebook.add(self.tab_clean, text=" 🧹 一键垃圾清理 ")
        notebook.add(self.tab_large, text=" 🐘 大文件扫描 ")
        notebook.add(self.tab_tools, text=" 🛠️ 系统强力工具 ")

        self._setup_clean_tab()
        self._setup_large_file_tab()
        self._setup_tools_tab()

        log_frame = ttk.LabelFrame(self.root, text="操作日志")
        log_frame.pack(fill="both", expand=False, padx=10, pady=5, side="bottom")

        self.log_text = tk.Text(log_frame, height=8, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _setup_clean_tab(self) -> None:
        frame = ttk.Frame(self.tab_clean)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        for row, category in enumerate(CLEANUP_CATEGORIES):
            variable = tk.BooleanVar(value=True)
            self.check_vars[category.name] = variable
            ttk.Checkbutton(frame, text=category.name, variable=variable).grid(
                row=row,
                column=0,
                sticky="w",
                pady=5,
            )

        ttk.Separator(frame, orient="horizontal").grid(
            row=len(CLEANUP_CATEGORIES),
            column=0,
            sticky="ew",
            pady=15,
        )

        self.clean_button = ttk.Button(frame, text="开始深度清理", command=self.start_clean_thread)
        self.clean_button.grid(row=len(CLEANUP_CATEGORIES) + 1, column=0, pady=10, ipady=5)

    def _setup_large_file_tab(self) -> None:
        frame = ttk.Frame(self.tab_large)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctrl_frame = ttk.Frame(frame)
        ctrl_frame.pack(fill="x", pady=5)

        ttk.Label(ctrl_frame, text=f"扫描目录: {DEFAULT_SCAN_ROOT}").pack(side="left")
        ttk.Label(ctrl_frame, text="  |  大于 (MB):").pack(side="left")

        self.entry_threshold = ttk.Entry(ctrl_frame, width=10)
        self.entry_threshold.insert(0, str(DEFAULT_LARGE_FILE_THRESHOLD_MB))
        self.entry_threshold.pack(side="left", padx=5)

        self.scan_button = ttk.Button(ctrl_frame, text="开始扫描", command=self.start_scan_thread)
        self.scan_button.pack(side="left", padx=10)

        ttk.Button(ctrl_frame, text="删除选中文件", command=self.delete_selected_large_file).pack(
            side="right",
            padx=10,
        )

        columns = ("size", "path")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("size", text="大小")
        self.tree.heading("path", text="文件路径")
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("path", width=680, anchor="w")

        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=y_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

    def _setup_tools_tab(self) -> None:
        frame = ttk.Frame(self.tab_tools)
        frame.pack(fill="both", expand=True, padx=30, pady=30)

        ttk.Label(
            frame,
            text="⚠️ 以下操作调用 Windows 系统原生命令，请按需使用",
            foreground="red",
        ).pack(pady=10)

        for tool in SYSTEM_TOOLS:
            ttk.Button(
                frame,
                text=tool.label,
                command=lambda tool_key=tool.key: self.run_system_tool_action(tool_key),
            ).pack(fill="x", pady=5)

    def enqueue_log(self, message: str) -> None:
        self.log_queue.put(message)

    def _flush_logs(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break

            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(100, self._flush_logs)

    def start_clean_thread(self) -> None:
        selected_categories = [
            category
            for category in CLEANUP_CATEGORIES
            if self.check_vars[category.name].get()
        ]
        if not selected_categories:
            messagebox.showwarning("提示", "请至少选择一个清理分类。")
            return

        self.clean_button.configure(state="disabled")
        self.enqueue_log(">>> 开始清理流程...")
        threading.Thread(
            target=self._run_clean_worker,
            args=(selected_categories,),
            daemon=True,
        ).start()

    def _run_clean_worker(self, selected_categories) -> None:
        try:
            summary = clean_selected_categories(selected_categories, logger=self.enqueue_log)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("清理失败", str(exc)))
        else:
            self.root.after(0, lambda: self._on_clean_finished(summary))
        finally:
            self.root.after(0, lambda: self.clean_button.configure(state="normal"))

    def _on_clean_finished(self, summary: CleanupSummary) -> None:
        self.enqueue_log("=" * 39)
        self.enqueue_log(f"清理完成！本次释放约 {format_bytes(summary.total_bytes_freed)} 空间。")
        self.enqueue_log("=" * 39)
        messagebox.showinfo("完成", f"清理结束！释放约 {format_bytes(summary.total_bytes_freed)}")

    def start_scan_thread(self) -> None:
        try:
            threshold = int(self.entry_threshold.get())
        except ValueError:
            messagebox.showwarning("输入错误", "请输入合法的整数阈值。")
            return

        if threshold <= 0:
            messagebox.showwarning("输入错误", "阈值必须大于 0。")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.scan_button.configure(state="disabled")
        threading.Thread(target=self._run_scan_worker, args=(threshold,), daemon=True).start()

    def _run_scan_worker(self, threshold: int) -> None:
        try:
            results = scan_large_files(DEFAULT_SCAN_ROOT, threshold, logger=self.enqueue_log)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("扫描失败", str(exc)))
        else:
            self.root.after(0, lambda: self._on_scan_finished(results))
        finally:
            self.root.after(0, lambda: self.scan_button.configure(state="normal"))

    def _on_scan_finished(self, results: list[LargeFileEntry]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for result in results:
            self.tree.insert("", "end", values=(format_bytes(result.size_bytes), str(result.path)))

    def delete_selected_large_file(self) -> None:
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("提示", "请先选择一个文件。")
            return

        item = self.tree.item(selected_item[0])
        path = Path(item["values"][1])

        if not messagebox.askyesno("危险操作确认", f"确定要永久删除此文件吗？\n\n{path}"):
            return

        try:
            delete_file(path)
        except OSError as exc:
            messagebox.showerror("删除失败", str(exc))
            return

        self.tree.delete(selected_item[0])
        self.enqueue_log(f"已删除大文件: {path}")

    def run_system_tool_action(self, tool_key: str) -> None:
        threading.Thread(target=self._run_system_tool_worker, args=(tool_key,), daemon=True).start()

    def _run_system_tool_worker(self, tool_key: str) -> None:
        try:
            run_system_tool(tool_key, logger=self.enqueue_log)
        except Exception as exc:
            self.root.after(0, lambda: messagebox.showerror("执行失败", str(exc)))
        else:
            self.root.after(0, lambda: messagebox.showinfo("完成", "系统工具已执行完成。"))


def main() -> None:
    root = tk.Tk()
    CleanerApp(root)
    root.mainloop()
