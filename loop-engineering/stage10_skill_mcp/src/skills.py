# -*- coding: utf-8 -*-
"""
skills.py —— Agent Skills：三层渐进式披露（stage10 组件一）

领域知识全塞 prompt 的下场：每轮 token 成本高、知识之间互相干扰
（失败模式 #9）。Skills 的答案是三层披露（教程第 14 章）：

  第一层  元数据（name + description，~50 token/技能）
          → 常驻 system prompt，让模型知道"有什么可用"
  第二层  正文（SKILL.md 的主体，几百 token）
          → 模型调用 load_skill 才加载——"决定用了才读"
  第三层  参考文件（references/*.md）
          → 正文里指路，模型调用 read_skill_ref 按需深读

token 账本：2 个技能常驻 ≈ 100 token；全量塞入 ≈ 4000+ token。
技能越多，差距越大——这就是渐进披露的存在意义。
"""
import re
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = STAGE_ROOT / "skills"


def _parse_frontmatter(text: str) -> tuple:
    """解析 SKILL.md 头部的 --- 包围 frontmatter（键: 值 简单格式）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


class SkillLoader:
    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.dir = skills_dir
        self.reload()

    def reload(self):
        """扫描 skills/*/SKILL.md，只保留第一层元数据在内存里。"""
        self.skills = {}
        if not self.dir.exists():
            return
        for d in sorted(self.dir.iterdir()):
            md = d / "SKILL.md"
            if d.is_dir() and md.exists():
                meta, body = _parse_frontmatter(
                    md.read_text(encoding="utf-8"))
                self.skills[meta.get("name", d.name)] = {
                    "dir": d, "description": meta.get("description", ""),
                    "body": body.strip()}

    # ── 第一层：元数据块（注入 system prompt）──────────────
    def metadata_block(self) -> str:
        if not self.skills:
            return "（无可用技能）"
        lines = [f"- {name}: {s['description']}"
                 for name, s in self.skills.items()]
        return "\n".join(lines)

    # ── 第二层：正文 ──────────────────────────────────────
    def load_skill(self, name: str) -> str:
        s = self.skills.get(name)
        if not s:
            return (f"错误：技能 {name} 不存在。"
                    f"可用：{', '.join(self.skills)}")
        body = s["body"]
        refs = self.list_references(name)
        if refs:
            body += ("\n\n【可用参考文件（用 read_skill_ref 按需读取）】\n"
                     + "\n".join(f"- {name}/references/{r}" for r in refs))
        return body

    # ── 第三层：参考文件 ──────────────────────────────────
    def list_references(self, name: str) -> list:
        s = self.skills.get(name)
        if not s:
            return []
        ref_dir = s["dir"] / "references"
        if not ref_dir.exists():
            return []
        return sorted(p.name for p in ref_dir.glob("*.md"))

    def read_reference(self, skill: str, filename: str) -> str:
        s = self.skills.get(skill)
        if not s:
            return f"错误：技能 {skill} 不存在"
        p = (s["dir"] / "references" / Path(filename).name).resolve()
        # 路径安全：只允许 references/ 下的 .md
        if not str(p).startswith(str((s["dir"] / "references").resolve())):
            return "错误：参考文件路径越界"
        if not p.exists():
            return (f"错误：参考文件不存在。可用："
                    f"{', '.join(self.list_references(skill)) or '（无）'}")
        return p.read_text(encoding="utf-8")
