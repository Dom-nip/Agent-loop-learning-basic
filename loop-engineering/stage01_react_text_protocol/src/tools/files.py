# -*- coding: utf-8 -*-
"""文件类工具实现：read_file / write_file / list_dir（路径安全已在 tools/__init__ 收口）。"""


def read_file(path) -> str:
    if not path.exists():
        return f"错误：文件不存在 {path.name}"
    if not path.is_file():
        return f"错误：{path.name} 不是文件"
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"错误：{path.name} 不是 UTF-8 文本文件"


def write_file(path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    # parents[0]=workspace，显示相对 workspace 的路径更直观
    return f"已写入 workspace/{path.relative_to(path.parents[0])}（{len(content)} 字符）"


def list_dir(path) -> str:
    if not path.exists():
        return f"错误：目录不存在 {path.name}"
    items = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    if not items:
        return "（目录为空）"
    lines = []
    for it in items:
        mark = "📁" if it.is_dir() else "📄"
        size = f"  {it.stat().st_size}B" if it.is_file() else ""
        lines.append(f"{mark} {it.name}{size}")
    return "\n".join(lines)
