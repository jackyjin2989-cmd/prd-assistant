from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT
REQUIRED = {
    "prd-assistant": [
        "references/input-intake.md",
        "references/写法指南.md",
        "references/review-checklist.md",
        "references/图片嵌入与截图指南.md",
        "references/语言表述规范.md",
        "references/final-output-hygiene.md",
        "references/browser/observation.md",
        "references/browser/tool-adapter.md",
        "references/browser/snapshot-and-interaction.md",
        "references/browser/auth-and-sessions.md",
        "references/browser/evidence-and-diagnostics.md",
        "references/browser/observation-record.md",
        "references/prototype/generation.md",
        "references/prototype/responsive-guide.md",
        "references/prototype/site-reference.md",
        "references/prototype/visual-validation.md",
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
    "### 默认不执行页面观察",
    "### 默认不生成原型",
    "最终文档不用删除线",
    "核心分歧集中提出最少问题并暂停定稿",
    "待确认内容不得进入确定性验收",
    "XX问题已判断",
]
README_POLICY_MARKERS = [
    "聚焦核心产品功能与改动",
    "观察和原型均不是 PRD 的默认步骤",
    "图片指南的职责边界与关键规则",
    "截图模糊、PC/H5 等不单独触发",
    "核心分歧集中追问并暂停定稿",
]
IMAGE_GUIDE_REQUIRED_MARKERS = [
    "## 图片选择",
    "## 命名",
    "## 脱敏",
    "## 相对路径与存在性",
    "## 图片排布",
    "每张截图必须紧跟对应描述或对应小标题",
    "禁止把各模块截图统一堆到章节末尾或文档末尾",
    "需要制作或验证 HTML 原型时按 [prototype/generation.md](prototype/generation.md) 执行",
]
IMAGE_GUIDE_FORBIDDEN_MARKERS = [
    "Selenium",
    "截图脚本",
    "## 远程同步",
    "同步到远程",
    "截图索引",
]
BROWSER_POLICY_MARKERS = [
    "的“原型与观察分流”为唯一完整定义",
    "URL、截图模糊或裁切、缺少普通交互状态、PC/H5 差异等均不单独触发观察",
]

INTAKE_POLICY_MARKERS = [
    "的“冲突处理”为唯一完整定义",
]
SKILL_FORBIDDEN_MARKERS = [
    "### 建议结构",
]
PROTOTYPE_POLICY_MARKERS = [
    "的“原型与观察分流”为唯一完整定义",
    "信息架构转译、页面实现、交互状态、响应式适配和视觉验证",
    "不交付或长期维护独立 Selenium 截图脚本 SOP",
    "确定最小范围",
    "双端支持按需",
    "完整状态矩阵不作为默认完成条件",
]
RESPONSIVE_FORBIDDEN_MARKERS = [
    "原型必须同时支持 PC 和 H5",
    "核心功能在两个端都可用",
    "PC 和 H5 两端必须保持",
]
VISUAL_FORBIDDEN_MARKERS = [
    "建议矩阵",
    "最小状态",
]
RUNTIME_BASE = ROOT.parent / ".trae" / "skills"
PRD_WRITING_REQUIRED_MARKERS = [
    "成功判定（按需）",
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


def check_forbidden_markers(path: Path, markers: list[str]) -> list[str]:
    if not path.is_file():
        return [f"缺少策略文件 {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    return [
        f"{path.relative_to(ROOT)}: 不应包含旧职责或 SOP -> {marker}"
        for marker in markers
        if marker in text
    ]


def main() -> int:
    errors: list[str] = []
    for name, references in REQUIRED.items():
        errors.extend(check_skill(name, references))

    prd_root = ROOT / "prd-assistant"
    errors.extend(check_markers(prd_root / "SKILL.md", PRD_POLICY_MARKERS))
    errors.extend(check_forbidden_markers(prd_root / "SKILL.md", SKILL_FORBIDDEN_MARKERS))
    errors.extend(check_markers(ROOT / "README.md", README_POLICY_MARKERS))
    image_guide = prd_root / "references" / "图片嵌入与截图指南.md"
    errors.extend(check_markers(image_guide, IMAGE_GUIDE_REQUIRED_MARKERS))
    errors.extend(check_forbidden_markers(image_guide, IMAGE_GUIDE_FORBIDDEN_MARKERS))
    errors.extend(check_markers(prd_root / "references" / "browser" / "observation.md", BROWSER_POLICY_MARKERS))
    errors.extend(check_markers(prd_root / "references" / "prototype" / "generation.md", PROTOTYPE_POLICY_MARKERS))
    errors.extend(check_markers(prd_root / "references" / "input-intake.md", INTAKE_POLICY_MARKERS))

    responsive_guide = prd_root / "references" / "prototype" / "responsive-guide.md"
    errors.extend(check_forbidden_markers(responsive_guide, RESPONSIVE_FORBIDDEN_MARKERS))
    visual_validation = prd_root / "references" / "prototype" / "visual-validation.md"
    errors.extend(check_forbidden_markers(visual_validation, VISUAL_FORBIDDEN_MARKERS))
    writing_guide = prd_root / "references" / "写法指南.md"
    errors.extend(check_markers(writing_guide, PRD_WRITING_REQUIRED_MARKERS))

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

    runtime_checked = RUNTIME_BASE.is_dir()
    if runtime_checked:
        for skill_name, refs in REQUIRED.items():
            runtime_skill = RUNTIME_BASE / skill_name
            if not runtime_skill.is_dir():
                continue
            runtime_skill_file = runtime_skill / "SKILL.md"
            repo_skill_file = ROOT / skill_name / "SKILL.md"
            if runtime_skill_file.is_file() and repo_skill_file.is_file():
                if (runtime_skill_file.read_bytes()) != (repo_skill_file.read_bytes()):
                    errors.append(f"运行版 {skill_name}/SKILL.md 与仓库版不一致")
            elif not runtime_skill_file.is_file() and repo_skill_file.is_file():
                errors.append(f"运行版缺少 {skill_name}/SKILL.md")
            for ref in refs:
                runtime_ref = runtime_skill / ref
                repo_ref = ROOT / skill_name / ref
                if runtime_ref.is_file() and repo_ref.is_file():
                    if runtime_ref.read_bytes() != repo_ref.read_bytes():
                        errors.append(f"运行版 {skill_name}/{ref} 与仓库版不一致")
                elif not runtime_ref.is_file() and repo_ref.is_file():
                    errors.append(f"运行版缺少 {skill_name}/{ref}")

    if errors:
        print("验证失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    runtime_note = "并核对了运行版文件一致性。" if runtime_checked else "未找到运行版目录，已跳过运行版一致性核对。"
    print(
        f"验证通过：{len(REQUIRED)} 个技能；已检查目录与 frontmatter、全部必需参考文件（含 browser/ 和 prototype/ 子目录）、"
        "非图片 Markdown 链接（图片目标未检查）、基础敏感文本模式、PRD 内容边界与观察/原型分流，"
        "图片指南职责边界、最小追问闭环、页面观察收窄触发、原型最小范围与按需验证，"
        f"responsive-guide 与 visual-validation 无强制双端残留，写法指南含成功判定规则；{runtime_note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
