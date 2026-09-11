#!/usr/bin/env python3
"""PRD 交付前扫描：把「靠人记」的收尾检查变成一条命令。

用法：
    python3 scripts/scan_prd.py <PRD 文件或目录> [更多路径 ...]
    python3 scripts/scan_prd.py --strict <路径>   # 待人工确认项也按失败处理

与 validate_skills.py 的分工：
    validate_skills.py 检查「技能仓库自身」（结构、frontmatter、策略标记）。
    scan_prd.py 检查「产出的 PRD 文档」（残留词、图片引用、链接可达性、编号连续性）。
    注意：本脚本面向 PRD，不要拿它扫技能自身的文档 —— 技能文档里出现「本期不做」等
    字样是正常的策略描述。

退出码：0 无错误（或仅有待确认项）；1 存在错误，或 --strict 下有待确认项；2 未找到可扫文件。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

# ---------------------------------------------------------------- 词表

# 范围排除：规则是「默认不写」，命中即需人工确认（可能是合规/合同类硬约束，属允许保留）
SCOPE_WORDS = [
    r"本期不做", r"本期不含", r"本期不涉及", r"不在本期", r"范围排除",
    r"暂不(?:做|支持|考虑)", r"非[^，。；]{0,6}版", r"不再(?:展示|支持|提供)",
]

# 迭代痕迹：被否方案、会话残留、编辑过程（正常 PRD 不应出现）
# 「占位」只作迭代痕迹看，放行「不占位」「占位符」「占位文案」这类正常产品措辞
TRACE_WORDS = [
    r"原[「『\"]", r"（原", r"已改为", r"已调整", r"已删除", r"已清理",
    r"曾考虑", r"之前(?:的|是)", r"(?<!不)占位(?!符|文案)", r"草稿", r"待补",
]

# 占位残留：未完成标记
PLACEHOLDER_WORDS = [
    r"截图占位", r"待补图", r"图片占位", r"\bTODO\b", r"\bFIXME\b", r"\bTBD\b", r"XXX",
]

# 交付物与实现细节：PRD 正文默认不交代（项目有要求附原型链接时按项目惯例）
ARTIFACT_WORDS = [
    r"本文截图取自", r"截图取自该原型", r"中台返回的文件\s*URL",
]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)")
HTML_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
HTML_ATTR = re.compile(r"""(src|alt)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*([^)\s]+)")
LEADING_NUM = re.compile(r"^(\d+)")


class Finding:
    def __init__(self, level: str, line: int | None, message: str) -> None:
        self.level = level  # error | review
        self.line = line
        self.message = message


def is_external(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "data:", "#"))


def is_absolute(target: str) -> bool:
    lowered = target.lower()
    return (
        target.startswith("/")
        or lowered.startswith("file:")
        or re.match(r"^[a-z]:[\\/]", lowered) is not None
    )


def scan_words(text: str, patterns: list[str], level: str, label: str) -> list[Finding]:
    findings: list[Finding] = []
    compiled = [re.compile(p) for p in patterns]
    for index, line in enumerate(text.splitlines(), start=1):
        for pattern in compiled:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(level, index, f"{label}「{match.group(0)}」：{line.strip()[:60]}")
                )
    return findings


def scan_file(path: Path) -> tuple[list[Finding], dict[str, int]]:
    findings: list[Finding] = []
    stats = {"images": 0, "links": 0}

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [Finding("error", None, "非 UTF-8 编码，无法读取")], stats

    if "\ufffd" in text:
        findings.append(Finding("error", None, "含无效编码字符 (U+FFFD)，文本已损坏"))

    findings += scan_words(text, SCOPE_WORDS, "review", "疑似范围排除")
    findings += scan_words(text, TRACE_WORDS, "review", "疑似迭代痕迹")
    findings += scan_words(text, ARTIFACT_WORDS, "review", "疑似交付物/实现细节")

    for pattern in PLACEHOLDER_WORDS:
        for index, line in enumerate(text.splitlines(), start=1):
            match = re.search(pattern, line)
            if match:
                findings.append(
                    Finding("error", index, f"占位残留「{match.group(0)}」：{line.strip()[:60]}")
                )

    # ---- 图片引用 ----
    referenced: list[tuple[str, int]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        for alt, target in MD_IMAGE.findall(line):
            referenced.append((target, index))
            if not alt.strip():
                findings.append(Finding("error", index, f"图片缺替代文本：{target}"))
        for tag in HTML_IMG.findall(line):
            attrs = {k.lower(): (v1 or v2) for k, v1, v2 in HTML_ATTR.findall(tag)}
            src = attrs.get("src")
            if src:
                referenced.append((src, index))
            if "alt" not in attrs:
                findings.append(Finding("review", index, f"HTML img 缺 alt：{src or tag[:40]}"))

    order: list[str] = []
    for target, index in referenced:
        if is_external(target):
            continue
        if is_absolute(target):
            findings.append(Finding("error", index, f"图片用了绝对路径（应为相对路径）：{target}"))
            continue
        stats["images"] += 1
        resolved = (path.parent / unquote(target)).resolve()
        if not resolved.exists():
            findings.append(Finding("error", index, f"图片文件不存在：{target}"))
        else:
            order.append(unquote(target))

    # ---- 编号连续性（文件名形如 01-xxx.png）----
    numbers: list[tuple[int, str]] = []
    for target in order:
        match = LEADING_NUM.match(Path(target).name)
        if match:
            numbers.append((int(match.group(1)), target))
    if len(numbers) >= 2:
        seq = [n for n, _ in numbers]
        if seq != list(range(seq[0], seq[0] + len(seq))):
            findings.append(
                Finding("review", None, f"图片编号不连续或与出现顺序不一致：{seq}")
            )

    # ---- 同目录未被引用的图片 ----
    # 一个目录里的图片常被同目录多份文档共用，所以先扣掉兄弟文档引用过的文件名。
    # 注意「引用」包含两种写法：图片语法 ![](...)，以及截图索引表里的普通链接 []（图很常见）
    def html_srcs(doc_text: str) -> list[str]:
        srcs: list[str] = []
        for tag in HTML_IMG.findall(doc_text):
            for key, double_quoted, single_quoted in HTML_ATTR.findall(tag):
                if key.lower() == "src":
                    value = double_quoted or single_quoted
                    if value:
                        srcs.append(value)
        return srcs

    def image_names_in(doc: Path) -> set[str]:
        names: set[str] = set()
        try:
            doc_text = doc.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return names
        targets = [target for _, target in MD_IMAGE.findall(doc_text)]
        targets += html_srcs(doc_text)
        # 截图索引表里常用普通链接指向图片，同样算被引用
        for raw in MD_LINK.findall(doc_text):
            target = raw.strip().strip("<>").split("#", 1)[0]
            if Path(target).suffix.lower() in IMAGE_SUFFIXES:
                targets.append(target)
        for target in targets:
            if not is_external(target):
                names.add(Path(unquote(target.strip().strip("<>"))).name)
        return names

    sibling_used: set[str] = set()
    for sibling in path.parent.glob("*.md"):
        if sibling != path:
            sibling_used |= image_names_in(sibling)

    dirs = {Path(unquote(t)).parent for t in order}
    used_names = {Path(unquote(t)).name for t in order} | sibling_used | image_names_in(path)
    for rel_dir in sorted(dirs):
        folder = (path.parent / rel_dir).resolve()
        if not folder.is_dir():
            continue
        stray = sorted(
            p.name for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES and p.name not in used_names
        )
        if stray:
            findings.append(
                Finding(
                    "review",
                    None,
                    f"{rel_dir or '.'}/ 下有目录内任何文档都未引用的图片："
                    + "、".join(stray[:8])
                    + ("…" if len(stray) > 8 else ""),
                )
            )

    # ---- 非图片链接可达性 ----
    for index, line in enumerate(text.splitlines(), start=1):
        for raw in MD_LINK.findall(line):
            target = raw.strip().strip("<>")
            if is_external(target):
                continue
            stats["links"] += 1
            if is_absolute(target):
                findings.append(Finding("error", index, f"链接用了绝对路径：{target}"))
                continue
            resolved = (path.parent / unquote(target.split("#", 1)[0])).resolve()
            if not resolved.exists():
                findings.append(Finding("error", index, f"相对链接失效：{target}"))

    return findings, stats


def collect(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in targets:
        path = Path(raw).expanduser()
        if path.is_dir():
            files += sorted(p for p in path.rglob("*.md") if ".git" not in p.parts)
        elif path.is_file():
            files.append(path)
        else:
            print(f"跳过（不存在）：{raw}")
    return files


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv[1:]
    files = collect(args)
    if not files:
        print("未找到可扫描的 Markdown 文件。用法：python3 scripts/scan_prd.py <PRD 文件或目录>")
        return 2

    total_error = 0
    total_review = 0
    print(f"扫描 {len(files)} 个文件\n")

    for path in files:
        findings, stats = scan_file(path)
        errors = [f for f in findings if f.level == "error"]
        reviews = [f for f in findings if f.level == "review"]
        total_error += len(errors)
        total_review += len(reviews)

        print(f"{path}（图片 {stats['images']} 张、链接 {stats['links']} 条）")
        if not findings:
            print("  ✅ 未发现问题")
        for finding in errors + reviews:
            mark = "❌" if finding.level == "error" else "⚠️"
            where = f"第 {finding.line} 行 " if finding.line else ""
            print(f"  {mark} {where}{finding.message}")
        print()

    print(f"汇总：{total_error} 个错误、{total_review} 项待人工确认")
    if total_error or (strict and total_review):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
