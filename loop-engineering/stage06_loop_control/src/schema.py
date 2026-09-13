# -*- coding: utf-8 -*-
"""
schema.py —— 极简 JSON Schema 校验器（stage02）

Function Calling 把"协议税"从解析层赶走了，但没有全免：模型填的**参数值**仍可能
不合 schema（类型错、必填缺、枚举外）。本文件就是一个零依赖的最小校验器，
支撑"校验失败 → 错误信息作为 tool result 喂回 → 模型下一轮修正"的 repair loop。

真实工程里这里通常用 jsonschema 库；为了保持零强依赖，这里只实现最常用的子集：
type / required / properties / enum / items。
"""
from json import JSONDecodeError
from json import loads as json_loads

_TYPE_CHECK = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def parse_args(raw: str) -> dict:
    """把 tool_call.arguments（JSON 字符串）解析为 dict。失败抛 ValueError。"""
    try:
        args = json_loads(raw or "{}")
    except JSONDecodeError as e:
        raise ValueError(f"arguments 不是合法 JSON：{e}") from e
    if not isinstance(args, dict):
        raise ValueError("arguments 应为 JSON 对象")
    return args


def validate(args: dict, schema: dict) -> list:
    """校验参数，返回错误信息列表（空列表 = 通过）。"""
    errors = []
    for req in schema.get("required", []):
        if req not in args:
            errors.append(f"缺少必填参数「{req}」")
    for name, spec in schema.get("properties", {}).items():
        if name not in args:
            continue
        v = args[name]
        t = spec.get("type")
        if t and t in _TYPE_CHECK and not _TYPE_CHECK[t](v):
            errors.append(f"参数「{name}」应为 {t}，实际为 {type(v).__name__}")
            continue
        if "enum" in spec and v not in spec["enum"]:
            errors.append(f"参数「{name}」必须是 {spec['enum']} 之一，实际为 {v!r}")
        if t == "array" and isinstance(v, list) and "items" in spec:
            item_t = spec["items"].get("type")
            if item_t in _TYPE_CHECK:
                bad = [x for x in v if not _TYPE_CHECK[item_t](x)]
                if bad:
                    errors.append(f"参数「{name}」数组内出现非 {item_t} 项：{bad!r}")
    return errors


def repair_message(tool_name: str, errors: list) -> str:
    """校验失败后作为 tool result 喂回的修复指令（repair loop 的原料）。"""
    bullet = "\n  · ".join(errors)
    return (f"❌ 参数校验失败，本次调用未执行。\n问题：\n  · {bullet}\n"
            f"请修正参数后**重新调用 {tool_name}**。注意各参数的类型与必填要求。")
