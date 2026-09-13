# -*- coding: utf-8 -*-
"""
mcp_client.py —— 最小 MCP stdio client（stage10 组件二）

职责：把 MCP server 作为子进程拉起，用 JSON-RPC over stdio 通信，
并把 server 的工具"桥接"成宿主 agent 可用的 Tool 对象。

这就是 M×N 困境的解法（教程第 17 章）：宿主只需要实现一次 MCP client，
任何 MCP server 的工具即插即用——工具不再绑死在宿主的私有注册表里。
"""
import json
import subprocess
import sys
import threading
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "mcp_server.py"


class McpStdioClient:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.proc = None
        self._id = 0
        self._pending = {}                # id -> threading.Event
        self._responses = {}              # id -> response dict
        self._reader = None

    # ── 生命周期 ─────────────────────────────────────────
    def start(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace")
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mini-mcp-client", "version": "0.1.0"}})
        self.log("✅ MCP server 已连接（stdio）")

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc = None
            self.log("MCP server 已停止")

    # ── 协议方法 ─────────────────────────────────────────
    def list_tools(self) -> list:
        resp = self._request("tools/list", {})
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        resp = self._request("tools/call",
                             {"name": name, "arguments": arguments})
        if "error" in resp:
            return f"错误：{resp['error'].get('message')}"
        # 按 MCP 约定拼接 content 数组的文本项
        parts = [c.get("text", "") for c in
                 resp.get("result", {}).get("content", [])
                 if c.get("type") == "text"]
        return "\n".join(parts) or "（无输出）"

    # ── 传输层 ───────────────────────────────────────────
    def _request(self, method: str, params: dict, timeout: float = 15) -> dict:
        self._id += 1
        rid = self._id
        req = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        event = threading.Event()
        self._pending[rid] = event
        self.proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()
        if not event.wait(timeout):
            self._pending.pop(rid, None)
            raise TimeoutError(f"MCP 请求超时：{method}")
        self._pending.pop(rid, None)
        return self._responses.pop(rid)

    def _read_loop(self):
        """后台线程：逐行读 server 响应，按 id 唤醒等待者。"""
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = resp.get("id")
            if rid in self._pending:
                self._responses[rid] = resp
                self._pending[rid].set()

    def log(self, s: str):
        if self.verbose:
            print(s)
