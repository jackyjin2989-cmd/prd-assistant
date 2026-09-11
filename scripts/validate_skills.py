from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
# 单技能仓库：仓库根就是技能根，SKILL.md 与 references/ 直接放在仓库根下。
SKILL_NAME = "prd-assistant"
REQUIRED = [
    "references/input-intake.md",
    "references/写法指南.md",
    "references/边界扫描清单.md",
    "references/示例.md",
    "references/review-checklist.md",
    "references/图片嵌入与截图指南.md",
    "references/语言表述规范.md",
    "references/prototype/generation.md",
    "references/prototype/responsive-guide.md",
    "references/prototype/visual-validation.md",
    "references/prototype/screenshot-tooling.md",
]
# browser/ 目录已移除：本 Skill 不访问网站，页面现状由用户提供截图。
FORBIDDEN_DIRS = [
    "references/browser",
]
# final-output-hygiene.md 已并入 review-checklist.md（审校与交付清理）。
FORBIDDEN_FILES = [
    "references/final-output-hygiene.md",
]
FORBIDDEN = [
    r"TRAE\s+Design",
    r"(?i)(password|passwd|token|cookie)\s*[:=]\s*[^\s]+",
    r"(?i)https?://[^\s/]*\.(?:internal|corp)(?:/|\s|$)",
    r"(?i)[A-Z]:\\Users\\[^\\]+",
]
TEXT_SUFFIXES = {".md", ".txt", ".html", ".js", ".css", ".json", ".yml", ".yaml"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

PRD_POLICY_MARKERS = [
    "## 简单需求必须简单写（硬规则）",
    "篇幅与复杂度匹配",
    "默认不写以下章节",
    "验收标准、测试用例、本期不做/范围排除",
    "## 默认内容边界",
    "系统边界",
    "超时、重试、异步",
    "发布、灰度、监控、回滚",
    "运营后台操作手册",
    "本 Skill 不访问网站",
    "请用户提供截图",
    "## 原型分流",
    "默认不生成原型",
    "最小追问闭环",
    "## 冲突处理",
]
SKILL_FORBIDDEN_MARKERS = [
    "### 建议结构",
    "references/browser",
    "页面观察",
    "观察分流",
]
README_POLICY_MARKERS = [
    "聚焦核心产品功能与改动",
    "简单需求必须简单写",
    "不访问网站",
    "截图能力判定",
]
IMAGE_GUIDE_REQUIRED_MARKERS = [
    "## 图片选择",
    "## 命名",
    "## 脱敏",
    "## 相对路径与存在性",
    "## 图片排布",
    "## 多图横排",
    "每张截图必须紧跟对应描述或对应小标题",
    "禁止把各模块截图统一堆到章节末尾或文档末尾",
    "截图内容必须与正文口径一致",
    "插图时记录进入该状态的方式",
    "截图能力判定",
]
IMAGE_GUIDE_FORBIDDEN_MARKERS = [
    "Selenium",
    "## 远程同步",
    "同步到远程",
]
INTAKE_POLICY_MARKERS = [
    "本 Skill 不访问网站",
    "需要页面现状才能写清改动时请用户提供截图",
    "的\"冲突处理\"为唯一完整定义",
    "的\"原型分流\"为唯一完整定义",
]
INTAKE_FORBIDDEN_MARKERS = [
    "browser/",
    "观察页面 → 写 PRD",
]
PROTOTYPE_POLICY_MARKERS = [
    "的\"原型分流\"为唯一完整定义",
    "确定最小范围",
    "双端支持按需",
    "不得擅自把截图替换成更熟悉的通用后台",
    "截图能力判定",
]
PROTOTYPE_FORBIDDEN_MARKERS = [
    "site-reference.md",
    "观察记录",
]
RESPONSIVE_REQUIRED_MARKERS = [
    "以目标材料为准",
    "内容重排，不是缩放",
]
RESPONSIVE_FORBIDDEN_MARKERS = [
    "原型必须同时支持 PC 和 H5",
    "核心功能在两个端都可用",
]
VISUAL_REQUIRED_MARKERS = [
    "## 截图能力判定（先读这一节）",
    "禁止安装浏览器、驱动、npm/pip 包或任何依赖",
    "禁止编写、调试截图脚本",
    "禁止对同一失败重试超过 1 次",
    "判定只做一次",
    "不作为逐像素复制目标",
]
REVIEW_REQUIRED_MARKERS = [
    "研发读完对应章节即可动手实现",
    "截图驱动原型是否先识别界面身份",
    "通过 / 受限 / 未完成",
    "是否出现了用户未要求的验收标准、本期不做",
    "被否方案当作不存在",
    "兼容展示 / 一次性刷数 / 新老划断",
    "正文不含 REQ/RULE/AC 编号和追踪矩阵",
]
PRD_WRITING_REQUIRED_MARKERS = [
    "简单需求必须简单写",
    "| 验收标准 | 仅用户明确要求时 |",
    "硬性上限",
    "边界扫描清单.md",
    "示例.md",
    "Mermaid",
    "不输出角色权限矩阵",
    "兼容展示",
    "新老划断",
]
BOUNDARY_SCAN_REQUIRED_MARKERS = [
    "并发、系统异常、性能等技术问题不在产品扫描范围内",
    "## 状态与枚举类改动",
    "## 字段类改动",
    "## 流程类改动",
    "## 权限类改动",
    "不做角色矩阵",
    "不为覆盖清单而扩写",
]
EXAMPLES_REQUIRED_MARKERS = [
    "## A 类完整示例",
    "## A 类反例",
    "## B 类结构示例",
    "## AI 味对照",
]
SCREENSHOT_REQUIRED_MARKERS = [
    "## 与判定标准的分工",
    "--headless=old",
    "--dump-dom",
    "按文档所述状态取图",
]
# 「口径一致」这条规则只在 references/图片嵌入与截图指南.md 里定义一份，
# 截图执行手册引用它即可；出现即视为职责复制。
SCREENSHOT_FORBIDDEN_MARKERS = [
    "## 环境能不能截图的判定",
    "比对顺序",
    "通过 / 受限 / 未完成",
    "口径一致",
]
# 运行版技能目录候选：环境变量优先，其次各宿主约定目录。命中第一个存在的即用它。
RUNTIME_CANDIDATES = [
    *([Path(os.environ["SKILLS_DIR"]).expanduser()] if os.environ.get("SKILLS_DIR") else []),
    Path.home() / ".workbuddy" / "skills",
    Path.home() / ".trae" / "skills",
    ROOT.parent / ".trae" / "skills",
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


def check_skill() -> list[str]:
    errors: list[str] = []
    skill_file = ROOT / "SKILL.md"
    if not skill_file.is_file():
        return ["缺少 SKILL.md"]

    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        errors.append("SKILL.md: frontmatter 缺失或格式错误")
    else:
        frontmatter = match.group(1)
        name_value = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
        if not name_value or name_value.group(1).strip().strip('"').strip("'") != SKILL_NAME:
            errors.append(f"SKILL.md: name 与预期技能名 {SKILL_NAME} 不一致")
        description = re.search(r"^description:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
        if not description:
            errors.append("SKILL.md: description 缺失")
        elif len(description.group(1).strip().strip('"').strip("'")) > 200:
            errors.append("SKILL.md: description 超过 200 字符")

    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"缺少引用 {relative}")

    for forbidden_dir in FORBIDDEN_DIRS:
        if (ROOT / forbidden_dir).exists():
            errors.append(f"不应存在已移除目录 {forbidden_dir}")

    for forbidden_file in FORBIDDEN_FILES:
        if (ROOT / forbidden_file).exists():
            errors.append(f"不应存在已移除文件 {forbidden_file}")

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
    errors.extend(check_skill())

    skill_root = ROOT  # 单技能仓库：仓库根就是技能根
    errors.extend(check_markers(skill_root / "SKILL.md", PRD_POLICY_MARKERS))
    errors.extend(check_forbidden_markers(skill_root / "SKILL.md", SKILL_FORBIDDEN_MARKERS))
    errors.extend(check_markers(ROOT / "README.md", README_POLICY_MARKERS))
    image_guide = skill_root / "references" / "图片嵌入与截图指南.md"
    errors.extend(check_markers(image_guide, IMAGE_GUIDE_REQUIRED_MARKERS))
    errors.extend(check_forbidden_markers(image_guide, IMAGE_GUIDE_FORBIDDEN_MARKERS))
    intake = skill_root / "references" / "input-intake.md"
    errors.extend(check_markers(intake, INTAKE_POLICY_MARKERS))
    errors.extend(check_forbidden_markers(intake, INTAKE_FORBIDDEN_MARKERS))
    generation = skill_root / "references" / "prototype" / "generation.md"
    errors.extend(check_markers(generation, PROTOTYPE_POLICY_MARKERS))
    errors.extend(check_forbidden_markers(generation, PROTOTYPE_FORBIDDEN_MARKERS))

    responsive_guide = skill_root / "references" / "prototype" / "responsive-guide.md"
    errors.extend(check_forbidden_markers(responsive_guide, RESPONSIVE_FORBIDDEN_MARKERS))
    errors.extend(check_markers(responsive_guide, RESPONSIVE_REQUIRED_MARKERS))
    visual_validation = skill_root / "references" / "prototype" / "visual-validation.md"
    errors.extend(check_markers(visual_validation, VISUAL_REQUIRED_MARKERS))
    review_checklist = skill_root / "references" / "review-checklist.md"
    errors.extend(check_markers(review_checklist, REVIEW_REQUIRED_MARKERS))
    writing_guide = skill_root / "references" / "写法指南.md"
    errors.extend(check_markers(writing_guide, PRD_WRITING_REQUIRED_MARKERS))
    boundary_scan = skill_root / "references" / "边界扫描清单.md"
    errors.extend(check_markers(boundary_scan, BOUNDARY_SCAN_REQUIRED_MARKERS))
    examples = skill_root / "references" / "示例.md"
    errors.extend(check_markers(examples, EXAMPLES_REQUIRED_MARKERS))

    screenshot_tooling = skill_root / "references" / "prototype" / "screenshot-tooling.md"
    errors.extend(check_markers(screenshot_tooling, SCREENSHOT_REQUIRED_MARKERS))
    errors.extend(check_forbidden_markers(screenshot_tooling, SCREENSHOT_FORBIDDEN_MARKERS))

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.name == "validate_skills.py":
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "\ufffd" in text:
            errors.append(f"{path.relative_to(ROOT)} 含无效编码字符 (U+FFFD)")
        if path.suffix.lower() == ".md":
            errors.extend(check_markdown_links(path, text))
        for pattern in FORBIDDEN:
            if re.search(pattern, text):
                errors.append(f"{path.relative_to(ROOT)} 命中禁止模式: {pattern}")

    runtime_base = next((c for c in RUNTIME_CANDIDATES if c.is_dir()), None)
    if runtime_base is None:
        runtime_note = (
            "未找到运行版技能目录，已跳过运行版一致性核对（探测过："
            + "、".join(str(c) for c in RUNTIME_CANDIDATES)
            + "；可用 SKILLS_DIR 环境变量指定）。"
        )
    else:
        runtime_skill = runtime_base / SKILL_NAME
        if not runtime_skill.exists() and not runtime_skill.is_symlink():
            runtime_note = (
                f"已找到运行版目录 {runtime_base}，其中没有 {SKILL_NAME}，无法核对一致性。"
            )
        elif runtime_skill.is_symlink() and Path(os.path.realpath(runtime_skill)) == ROOT:
            # 运行版是指向本仓库的软链 -> 同一份文件，天然一致，不做逐字节比对
            runtime_note = (
                f"已核对运行版目录 {runtime_base}（{SKILL_NAME} 为指向本仓库的软链，直接判定一致）。"
            )
        else:
            # 运行版是独立拷贝：逐文件比对，确认没有被改过而忘记同步回仓库
            for relative in ["SKILL.md", *REQUIRED]:
                runtime_ref = runtime_skill / relative
                repo_ref = ROOT / relative
                if runtime_ref.is_file() and repo_ref.is_file():
                    if runtime_ref.read_bytes() != repo_ref.read_bytes():
                        errors.append(f"运行版 {SKILL_NAME}/{relative} 与仓库版不一致")
                elif repo_ref.is_file():
                    errors.append(f"运行版缺少 {SKILL_NAME}/{relative}")
            runtime_note = f"已核对运行版目录 {runtime_base}（{SKILL_NAME} 为独立拷贝，逐文件比对）。"

    if errors:
        print("验证失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"验证通过：单技能 {SKILL_NAME}；已检查仓库结构与 frontmatter、全部必需参考文件、"
        "非图片 Markdown 链接、编码完整性、基础敏感文本模式、简单需求简单写与默认内容边界、"
        "不访问网站与原型分流、截图能力判定与降级规则、"
        f"responsive-guide 目标材料优先、审校北极星与交付清理；{runtime_note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
