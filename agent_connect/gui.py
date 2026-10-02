"""Small native Tkinter controller UI for AgentConnect-PC."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from . import __version__
from .core import (
    AgentConnectError, APP_NAME, DEFAULT_TIMEOUT, config_snippets,
    create_target_bundle, discover_and_connect, list_targets, load_target,
    netcheck, ping_peer, tailscale_status, tailscale_version,
)


class AgentConnectApp(tk.Tk):
    def __init__(self, root_dir: Path | None = None) -> None:
        super().__init__()
        self.title(f"{APP_NAME} 控制端")
        self.geometry("1060x720")
        self.minsize(900, 620)
        self.root_dir = root_dir
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self._build_ui()
        self.refresh_targets()
        self.after(150, self._drain_events)

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky="ns")
        left.rowconfigure(1, weight=1)
        ttk.Label(left, text="AgentConnect-PC", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="AI Agent 远程 Windows 控制端").grid(row=0, column=1, padx=(8, 0), sticky="w")
        self.targets = tk.Listbox(left, width=31, height=18, exportselection=False)
        self.targets.grid(row=1, column=0, columnspan=2, pady=(12, 8), sticky="ns")
        self.targets.bind("<<ListboxSelect>>", lambda _event: self._show_selected())
        ttk.Button(left, text="刷新设备", command=self.refresh_targets).grid(row=2, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(left, text="打开项目目录", command=self._choose_root).grid(row=2, column=1, sticky="ew", padx=(4, 0))
        ttk.Separator(left).grid(row=3, column=0, columnspan=2, pady=12, sticky="ew")
        ttk.Label(left, text="首次使用：先用 CLI 的 new 或 GUI 生成目标包，再把整个文件夹交给受控端。", wraplength=260).grid(row=4, column=0, columnspan=2, sticky="w")

        main = ttk.Frame(self, padding=(0, 12, 14, 12))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        self.target_title = ttk.Label(main, text="请选择一个目标", font=("Segoe UI", 14, "bold"))
        self.target_title.grid(row=0, column=0, sticky="w")
        self.target_detail = ttk.Label(main, text="", justify="left")
        self.target_detail.grid(row=1, column=0, pady=(4, 10), sticky="w")

        actions = ttk.LabelFrame(main, text="控制端操作", padding=10)
        actions.grid(row=2, column=0, sticky="new")
        for index in range(3):
            actions.columnconfigure(index, weight=1)
        ttk.Button(actions, text="生成目标包", command=self._generate_dialog).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="等待并连接", command=self._wait_selected).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="刷新 Tailscale", command=self._refresh_status).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="复制 MCP 配置", command=self._copy_snippets).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="Ping 目标", command=self._ping_selected).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(actions, text="NAT/DERP 检查", command=self._netcheck).grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        output_frame = ttk.LabelFrame(main, text="运行日志", padding=8)
        output_frame.grid(row=3, column=0, pady=(12, 0), sticky="nsew")
        main.rowconfigure(3, weight=1)
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self.output = tk.Text(output_frame, height=18, wrap="word", state="disabled", background="#111827", foreground="#e5e7eb")
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)
        self._log(f"{APP_NAME} {__version__} 已启动。若看不懂项目，可让你的 AI Agent 先阅读仓库 AGENTS.md。")

    def _log(self, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", message.rstrip() + "\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "done":
                    self._log(str(payload))
                elif kind == "error":
                    self._log(f"[ERROR] {payload}")
                    messagebox.showerror(APP_NAME, str(payload))
        except queue.Empty:
            pass
        self.after(150, self._drain_events)

    def _run_async(self, fn, *args) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "已有操作正在运行，请等待它完成。")
            return
        def work() -> None:
            try:
                result = fn(*args)
                self.events.put(("done", result if result is not None else "完成"))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def refresh_targets(self) -> None:
        self.targets.delete(0, "end")
        for target in list_targets(self.root_dir):
            suffix = f"  ({target.target_ip})" if target.target_ip else "  (待连接)"
            self.targets.insert("end", target.name + suffix)
        self._show_selected()

    def _selected_name(self) -> str | None:
        selection = self.targets.curselection()
        if not selection:
            return None
        text = self.targets.get(selection[0])
        return text.split("  ", 1)[0]

    def _show_selected(self) -> None:
        name = self._selected_name()
        if not name:
            self.target_title.configure(text="请选择一个目标")
            self.target_detail.configure(text="")
            return
        try:
            target = load_target(name, self.root_dir)
        except AgentConnectError as exc:
            self.target_detail.configure(text=str(exc))
            return
        self.target_title.configure(text=f"目标：{target.name}")
        self.target_detail.configure(text=f"IP：{target.target_ip or '待发现'}\n端口：{target.port}\n配置：{target.path}")

    def _choose_root(self) -> None:
        selected = filedialog.askdirectory(title="选择 AgentConnect 项目目录")
        if selected:
            self.root_dir = Path(selected)
            self.refresh_targets()
            self._log(f"已切换项目目录：{selected}")

    def _generate_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("生成目标包")
        dialog.transient(self)
        dialog.grab_set()
        fields = {}
        for row, (label, key) in enumerate((("目标昵称", "name"), ("Tailscale Auth Key", "auth"))):
            ttk.Label(dialog, text=label).grid(row=row, column=0, padx=10, pady=8, sticky="w")
            entry = ttk.Entry(dialog, width=48, show="*" if key == "auth" else "")
            entry.grid(row=row, column=1, padx=10, pady=8)
            fields[key] = entry
        ttk.Label(dialog, text="Auth Key 只用于生成一次性目标包，不会上传。", wraplength=360).grid(row=2, column=0, columnspan=2, padx=10, sticky="w")
        def submit() -> None:
            name, auth = fields["name"].get().strip(), fields["auth"].get().strip()
            if not name or not auth:
                messagebox.showwarning(APP_NAME, "请填写目标昵称和 Auth Key", parent=dialog)
                return
            dialog.destroy()
            def create() -> str:
                output, target = create_target_bundle(name, auth, self.root_dir)
                self.after(0, self.refresh_targets)
                return f"目标包已生成：{output}\n密钥存档：{target.path}"
            self._run_async(create)
        ttk.Button(dialog, text="生成", command=submit).grid(row=3, column=0, columnspan=2, pady=12)

    def _wait_selected(self) -> None:
        name = self._selected_name()
        if not name:
            messagebox.showinfo(APP_NAME, "请先选择目标")
            return
        target = load_target(name, self.root_dir)
        self._run_async(discover_and_connect, target, DEFAULT_TIMEOUT, lambda text: self.events.put(("log", text)))

    def _refresh_status(self) -> None:
        def refresh() -> str:
            data, peers = tailscale_status()
            self.events.put(("log", json.dumps(data, ensure_ascii=False, indent=2)))
            return f"Tailscale 状态已刷新：{len(peers)} 台 peer"
        self._run_async(refresh)

    def _ping_selected(self) -> None:
        name = self._selected_name()
        if not name:
            messagebox.showinfo(APP_NAME, "请先选择目标")
            return
        target = load_target(name, self.root_dir)
        if not target.target_ip:
            messagebox.showinfo(APP_NAME, "目标还没有 TARGET_IP，请先等待并连接")
            return
        self._run_async(lambda: ping_peer(target.target_ip))

    def _netcheck(self) -> None:
        self._run_async(netcheck)

    def _copy_snippets(self) -> None:
        name = self._selected_name()
        if not name:
            messagebox.showinfo(APP_NAME, "请先选择目标")
            return
        snippets = config_snippets(load_target(name, self.root_dir))
        text = "\n\n".join(f"--- {key} ---\n{value}" for key, value in snippets.items())
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log("已复制 Claude/Cursor/OpenCode/ZCode/Codex 配置到剪贴板。")


def main() -> None:
    AgentConnectApp().mainloop()


if __name__ == "__main__":
    main()
