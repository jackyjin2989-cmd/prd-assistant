from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".trae" / "skills"
REQUIRED = {
    "prd-assistant": [
        "review-checklist.md",
        "写法指南.md",
        "图片嵌入与截图指南.md",
        "语言表述规范.md",
    ],
    "html-prototype": [
        "references/site-reference.md",
        "references/visual-validation.md",
    ],
}
FORBIDDEN = [
    r"TRAE\s+Design",
    r"(?i)(password|passwd|token|cookie)\s*[:=]\s*[^\s]+",
    r"(?i)https?://[^\s/]*\.(?:internal|corp)(?:/|\s|$)",
    r"(?i)[A-Z]:\\Users\\[^\\]+",
]


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
        if not description or len(description.group(1).strip().strip('"').strip("'")) > 200:
            errors.append(f"{name}: description 缺失或超过 200 字符")

    for relative in references:
        if not (folder / relative).is_file():
            errors.append(f"{name}: 缺少引用 {relative}")
    return errors


def main() -> int:
    errors: list[str] = []
    for name, references in REQUIRED.items():
        errors.extend(check_skill(name, references))

    text_suffixes = {".md", ".txt", ".html", ".js", ".css", ".json", ".yml", ".yaml"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name == "validate_skills.py":
            continue
        if path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN:
            if re.search(pattern, text):
                errors.append(f"{path.relative_to(ROOT)} 命中禁止模式: {pattern}")

    if errors:
        print("验证失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"验证通过：{len(REQUIRED)} 个技能，结构、引用与敏感模式检查均通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
