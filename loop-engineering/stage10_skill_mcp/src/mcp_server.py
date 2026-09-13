# -*- coding: utf-8 -*-
"""
mcp_server.py —— 最小 MCP stdio server（stage10 组件二，教学子集）

MCP（Model Context Protocol，教程第 17 章）把"工具"从宿主进程里搬出去：
server 是独立进程，通过 stdio 上的 JSON-RPC 2.0 通信。本文件是一个
零依赖的教学实现，只覆盖三个方法：

    initialize   握手（交换协议版本与能力声明）
    tools/list   列出工具（name + description + inputSchema）
    tools/call   调用工具，返回 content 数组

官方协议还有 resources / prompts / 通知等概念，生产环境请用 `mcp` SDK。
运行：python src/mcp_server.py（由 mcp_client.py 以子进程方式拉起，
本文件单独运行时无界面——它在等 stdin 上的 JSON-RPC 请求）。

提供两个示例工具：
    word_count  统计文本的字符/词数（演示参数传递）
    now         返回当前时间（演示无参数工具）
"""
import json
import sys
from datetime import datetime

PROTOCOL_VERSION = "2024-11-05"


def tool_word_count(text: str) -> str:
    """统计文本：字符数 / 去空白字符数 / 词语数（按空白切分）。"""
    chars = len(text)
    nospace = len([c for c in text if not c.isspace()])
    words = len(text.split())
    return json.dumps({"chars": chars, "chars_no_space": nospace,
                       "words": words}, ensure_ascii=False)


def tool_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


TOOLS = [
    {
        "name": "word_count",
        "description": "统计给定文本的字符数、去空白字符数与词语数。",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string",
                                    "description": "要统计的文本"}},
            "required": ["text"],
        },
    },
    {
        "name": "now",
        "description": "返回服务器当前时间（本地时区，YYYY-MM-DD HH:MM:SS）。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

_HANDLERS = {"word_count": tool_word_count, "now": tool_now}


def handle(req: dict) -> dict:
    """处理一条 JSON-RPC 请求，返回响应 dict。"""
    method = req.get("method", "")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"protocolVersion": PROTOCOL_VERSION,
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "mini-mcp-server",
                                          "version": "0.1.0"}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        fn = _HANDLERS.get(name)
        if fn is None:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602,
                              "message": f"未知工具 {name}"}}
        try:
            text = fn(**args)
        except TypeError as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602,
                              "message": f"参数错误：{e}"}}
        # MCP 约定：结果包在 content 数组里，每项有 type
        return {"jsonrpc": "2.0", "id": rid,
                "result": {"content": [{"type": "text", "text": text}]}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"未知方法 {method}"}}


def main():
    # stdio 模式：每行一个 JSON-RPC 请求，逐行响应
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
