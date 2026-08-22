from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT
REQUIRED = {
    "browser-observer": [
        "references/tool-adapter.md",
        "references/snapshot-and-interaction.md",
        "references/auth-and-sessions.md",
        "references/evidence-and-diagnostics.md",
        "references/observation-record.md",
    ],
    "prd-assistant": [
        "references/input-intake.md",
        "references/写法指南.md",
        "references/review-checklist.md",
        "references/图片嵌入与截图指南.md",
        "references/语言表述规范.md",
        "references/final-output-hygiene.md",
    ],
    "html-prototype": [
        "references/site-reference.md",
        "references/responsive-guide.md",
        "references/visual-validation.md",
    ],
}
FORBIDDEN = [
    r"TRAE\s+Design",
    r"(?i)(password|passwd|token|cookie)\s*[:=]\s*[^\s]+",
    r"(?i)https?://[^\s/]*\.(?:internal|corp)(?:/|\s|$)",
    r"(?i)[A-Z]:\\Users\\[^\\]+",
]
TEXT_SUFFIXES = {".md", ".txt", ".html", ".js", ".css", ".json", ".yml", ".yaml"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

PRD_POLICY_MARKERS = [
    "## 默认内容边界",
    "系统边界",
    "超时、重试、异步",
    "发布、灰度、监控、回滚",
    "算法、模型和内部策略",
    "缺陷修复过程",
    "功能下线",
    "运营后台操作手册",
    "### 默认不调用 `browser-observer`",
    "### 默认不调用 `html-prototype`",
    "最终文档不用删除线",
]
README_POLICY_MARKERS = [
    "聚焦核心产品功能与改动",
    "观察和原型均不是 PRD 的默认步骤",
]


def parse_target(raw: str) -> str | None:
    target = raw.strip().split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    return unquote(target.split("#", 1)[0])


def check_markdown_links(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    for raw in MARKDOWN_LINK.findall(text):
        target = parse_target(raw)
        if target is None:
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)}: 链接超出仓库 -> {target}")
            continue
        if not resolved.exists():
            errors.append(f"{path.relative_to(ROOT)}: Markdown 链接无效 -> {target}")
    return errors


def check_skill(name: str, references: list[str]) -> list[str]:
    errors: list[str] = []
    folder = SKILLS / name
    skill_file = folder / "SKILL.md"
    if not skill_file.is_file():
        return [f"缺少 {skill_file.relative_to(ROOT)}"]

    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        errors.append(f"{name}: frontmatter 缺失或格式错误")
    else:
        frontmatter = match.group(1)
        name_value = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
        if not name_value or name_value.group(1).strip().strip('"').strip("'") != name:
            errors.append(f"{name}: name 与目录名不一致")
        description = re.search(r"^description:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
        if not description:
            errors.append(f"{name}: description 缺失")
        elif len(description.group(1).strip().strip('"').strip("'")) > 200:
            errors.append(f"{name}: description 超过 200 字符")

    for relative in references:
        if not (folder / relative).is_file():
            errors.append(f"{name}: 缺少引用 {relative}")

    return errors


def check_markers(path: Path, markers: list[str]) -> list[str]:
    if not path.is_file():
        return [f"缺少策略文件 {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    return [
        f"{path.relative_to(ROOT)}: 缺少策略标记 -> {marker}"
        for marker in markers
        if marker not in text
    ]


def main() -> int:
    errors: list[str] = []
    for name, references in REQUIRED.items():
        errors.extend(check_skill(name, references))

    errors.extend(check_markers(ROOT / "prd-assistant" / "SKILL.md", PRD_POLICY_MARKERS))
    errors.extend(check_markers(ROOT / "README.md", README_POLICY_MARKERS))

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name == "validate_skills.py":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.lower() == ".md":
            errors.extend(check_markdown_links(path, text))
        for pattern in FORBIDDEN:
            if re.search(pattern, text):
                errors.append(f"{path.relative_to(ROOT)} 命中禁止模式: {pattern}")

    if errors:
        print("验证失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"验证通过：{len(REQUIRED)} 个技能，结构、Markdown 链接、敏感模式、"
        "PRD 内容边界与低成本分流规则均通过。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
