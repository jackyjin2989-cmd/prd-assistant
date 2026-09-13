#!/usr/bin/env python3
"""离线 stdlib 文件完整性校验；不证明模型行为、浏览器质量或发布者身份。

仅支持明示的 YAML/Markdown 子集。没有网络、安装、Git 或 home 目录探测。
路径防护针对静态文件树；并发换链不是本脚本能提供的操作系统沙箱保证。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import re
import stat
import sys
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.dont_write_bytecode = True
from prd_syntax import is_reparse, links, local_target, prose_lines, safe_resolve

ROOT = Path(__file__).absolute().parents[1]
SKILL_NAME = "prd-assistant"
MANIFEST = "package-manifest.json"
BASELINE_COMMIT = "e5ab216fd1caab7d3b76a9ffe6229e5771e5b4c7"
# 基础资产不由 manifest 自报：删掉脚本再改 manifest 不能绕过此清单。
REQUIRED = frozenset({
    ".gitattributes", ".github/workflows/validate.yml", ".gitignore",
    "CONTRIBUTING.md", "LICENSE", "README.md", "SKILL.md",
    "scripts/scan_prd.py", "scripts/test_scan_prd.py", "scripts/validate_skill.py",
    "references/input-intake.md", "references/写法指南.md", "references/边界扫描清单.md",
    "references/示例.md", "references/review-checklist.md", "references/图片嵌入与截图指南.md",
    "references/语言表述规范.md", "references/prototype/generation.md",
    "references/prototype/responsive-guide.md", "references/prototype/visual-validation.md",
    "references/prototype/screenshot-tooling.md", "scripts/prd_syntax.py",
    "scripts/test_prd_syntax.py", "scripts/test_validate_skill.py", "scripts/package_skill.py",
    "tests/behavior-cases.json", "references/behavior-evaluation.md",
})
# 排除项明确固定，不采用 .gitignore 或用户环境；先检查目录入口不是链接再跳过。
EXCLUDED_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", "artifacts", "screenshots",
                           "diffs", "test-results", "playwright-report", "dist", "build"})
COMPILED_SUFFIXES = {".pyc", ".pyo"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".html", ".htm", ".js", ".css", ".json", ".yml", ".yaml"}
SCOPE = ("仅验证本地文件集合、SHA256、明示语法子集和基础敏感硬编码；"
         "不保证模型行为、PRD/原型/浏览器质量、完整凭据审计或发布者身份；外链不联网。")


class Invalid(ValueError):
    """文件内容、结构或安全边界不符合契约（退出 1）。"""


@dataclass
class Report:
    root: str
    mode: str = "repository"
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    io_failure: bool = False
    version: str | None = None
    files_checked: int = 0
    manifest: dict | None = field(default=None, repr=False)

    def error(self, code: str, message: str, path: str = "", line: int | None = None) -> None:
        self.errors.append({"code": code, "path": path, "line": line, "message": message})

    def warning(self, code: str, message: str, path: str = "", line: int | None = None) -> None:
        self.warnings.append({"code": code, "path": path, "line": line, "message": message})

    @property
    def exit_code(self) -> int:
        return 2 if self.io_failure else 1 if self.errors else 0

    def as_dict(self) -> dict:
        return {"root": self.root, "mode": self.mode, "version": self.version,
                "status": "通过本地校验" if not self.errors else "校验失败",
                "exit_code": self.exit_code, "files_checked": self.files_checked,
                "errors": self.errors, "warnings": self.warnings, "scope": SCOPE,
                "installed_checked": self.mode == "installed" and not self.errors}


def checked_root(path: Path) -> Path:
    """不展开 ~；逐级 lstat 拒绝祖先中的 symlink/junction，再解析根。"""
    root = Path(os.path.abspath(path))
    for component in (*reversed(root.parents), root):
        if is_reparse(component):
            raise Invalid("授权根或其祖先是 symlink/junction")
    if not root.is_dir():
        raise OSError("授权根不是目录")
    real = root.resolve(strict=True)
    if root != real:
        raise Invalid("授权根的词法路径与真实路径不一致")
    return root


def guarded_path(path: Path, root: Path) -> Path:
    """先词法包含，再逐级拒绝链接，最后真实包含；不读取根外目标。"""
    root = checked_root(root)
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        parts = candidate.relative_to(root).parts
    except ValueError as exc:
        raise Invalid("路径超出授权根") from exc
    current = root
    for part in parts:
        current /= part
        try:
            if is_reparse(current):
                raise Invalid("拒绝 symlink/junction")
        except FileNotFoundError:
            break
    try:
        return safe_resolve(candidate, root)
    except ValueError as exc:
        raise Invalid(str(exc)) from exc


def safe_bytes(path: Path, root: Path) -> bytes:
    candidate = guarded_path(path, root)
    before = candidate.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise Invalid("目标不是普通文件")
    with candidate.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise Invalid("文件在打开时发生变化")
        data = stream.read()
        after = os.fstat(stream.fileno())
    guarded_path(candidate, root)
    final = candidate.lstat()
    stamp = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    # Windows 的 lstat/fstat 对 ctime 的含义可能不同；只在同一 API 内比较 ctime。
    if (stamp(before) != stamp(opened) or stamp(opened) != stamp(after) or stamp(after) != stamp(final)
            or before.st_ctime_ns != final.st_ctime_ns or opened.st_ctime_ns != after.st_ctime_ns):
        raise Invalid("文件在读取时发生变化")
    return data


def safe_text(path: Path, root: Path) -> str:
    return safe_bytes(path, root).decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def valid_relative(name: str) -> None:
    if not isinstance(name, str) or not name or name != unicodedata.normalize("NFC", name):
        raise Invalid("清单路径必须是非空 NFC 相对 POSIX 路径")
    parts = name.split("/")
    for part in parts:
        if (part in {"", ".", ".."} or part.endswith((" ", "."))
                or any(ord(c) < 32 or ord(c) == 127 or c in '\\<>:"|?*' for c in part)
                or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part)):
            raise Invalid("清单路径有越界、绝对路径或跨平台歧义")
    if any(p.casefold() in EXCLUDED_DIRS for p in parts) or Path(name).suffix.lower() in COMPILED_SUFFIXES:
        raise Invalid("清单不允许包含排除目录或编译产物")


def sensitive_filename(name: str) -> bool:
    parts = [part.casefold() for part in name.split("/")]
    return (any(part in {".ssh", ".aws", ".venv", "venv", "node_modules"} for part in parts)
            or parts[-1].startswith(".env")
            or parts[-1] in {"cookies.json", "storage-state.json", "credentials", "id_rsa", "id_ed25519"}
            or Path(name).suffix.lower() in {".pem", ".key", ".p12", ".pfx"})


def inventory(root: Path) -> dict[str, Path]:
    root = checked_root(root)
    files: dict[str, Path] = {}
    seen: dict[str, str] = {}

    def visit(directory: Path) -> None:
        directory = guarded_path(directory, root)
        with os.scandir(directory) as entries:
            paths = sorted((Path(item.path) for item in entries), key=lambda p: p.name)
        for path in paths:
            relative = path.relative_to(root).as_posix()
            # 必须先看入口，连指向排除目录的链接也拒绝。
            guarded_path(path, root)
            info = path.lstat()
            is_dir = stat.S_ISDIR(info.st_mode)
            if (is_dir and path.name.casefold() in EXCLUDED_DIRS
                    or stat.S_ISREG(info.st_mode) and path.suffix.lower() in COMPILED_SUFFIXES):
                continue
            valid_relative(relative)
            folded = relative.casefold()
            if folded in seen:
                raise Invalid(f"路径大小写碰撞：{seen[folded]} / {relative}")
            seen[folded] = relative
            if sensitive_filename(relative):
                raise Invalid(f"拒绝秘密、依赖或本地缓存路径：{relative}")
            if path.name.casefold() == "skill.md" and relative != "SKILL.md":
                raise Invalid(f"只能有根 SKILL.md，拒绝嵌套或大小写变体：{relative}")
            if is_dir:
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                files[relative] = path
            else:
                raise Invalid(f"拒绝非普通文件：{relative}")
    visit(root)
    return files


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise Invalid(f"JSON 重复键：{key}")
        result[key] = value
    return result


def valid_version(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                         r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
                         r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?", value, re.ASCII)
    return bool(match and all(not (s.isdigit() and len(s) > 1 and s.startswith("0"))
                              for s in (match[4] or "").split(".")))


def parse_manifest(text: str) -> dict:
    try:
        manifest = json.loads(text, object_pairs_hook=unique_object)
    except (ValueError, RecursionError) as exc:
        raise Invalid(f"manifest JSON 无效：{exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "skill", "version", "baseline_commit", "files"}:
        raise Invalid("manifest 顶层字段不符合 schema 1")
    if type(manifest["schema"]) is not int or manifest["schema"] != 1 or manifest["skill"] != SKILL_NAME:
        raise Invalid("manifest schema 或 skill 无效")
    if not valid_version(manifest["version"]):
        raise Invalid("manifest version 必须是合法 SemVer（唯一版本来源）")
    baseline = manifest["baseline_commit"]
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline) or baseline == "0" * 40:
        raise Invalid("manifest baseline_commit 必须是非零完整提交标识；不联网核验其真实性")
    files = manifest["files"]
    if not isinstance(files, dict):
        raise Invalid("manifest files 必须是路径到 SHA256 的映射")
    seen: dict[str, str] = {}
    for name, digest in files.items():
        valid_relative(name)
        if name.casefold() == MANIFEST or sensitive_filename(name):
            raise Invalid("manifest 不能列自身或敏感缓存文件")
        # 同时检查祖先目录大小写，防止 a/x 和 A/y 在不同系统折叠。
        parts = name.split("/")
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            previous = seen.setdefault(prefix.casefold(), prefix)
            if prefix != previous:
                raise Invalid("manifest 存在路径大小写碰撞")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Invalid(f"SHA256 格式错误：{name}")
    missing = REQUIRED - files.keys()
    if missing:
        raise Invalid("manifest 缺少强制基础资产：" + ", ".join(sorted(missing)))
    return manifest


def yaml_scalar(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise Invalid("YAML 标量不能为空")
    if raw.startswith('"'):
        try:
            value, end = json.JSONDecoder().raw_decode(raw)
        except ValueError as exc:
            raise Invalid("双引号标量只支持 JSON 兼容转义") from exc
        if not isinstance(value, str) or raw[end:].strip() and not raw[end:].lstrip().startswith("#"):
            raise Invalid("双引号标量结尾无效")
    elif raw.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:\s+#.*)?", raw)
        if not match:
            raise Invalid("单引号标量无效")
        value = match[1].replace("''", "'")
    else:
        value = re.split(r"\s+#", raw, maxsplit=1)[0].rstrip()
        if (value.startswith(tuple("[{}]&*!|>@`%#\"'")) or value in {"-", "?", ":", "~"}
                or re.search(r":(?:\s|$)", value)
                or re.match(r"[-?]\s", value)
                or value.lower() in {"null", "true", "false"}):
            raise Invalid("不支持复杂 YAML、标签、锚点、集合或非字符串标量；请使用简单引号字符串")
    if not value.strip() or any(ord(c) < 32 for c in value):
        raise Invalid("YAML 标量为空或含控制字符")
    return value


def parse_metadata(text: str) -> tuple[dict, str]:
    """支持简单标量、description |/>、metadata.version；不声称完整 YAML。"""
    rows = text.removeprefix("\ufeff").replace("\r\n", "\n").splitlines(keepends=True)
    if not rows or rows[0].rstrip("\r\n") != "---":
        raise Invalid("SKILL.md 缺少起始 frontmatter ---")
    end = next((i for i in range(1, len(rows)) if rows[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise Invalid("SKILL.md frontmatter 未闭合")
    header = [row.rstrip("\r\n") for row in rows[1:end]]
    result: dict = {}
    i = 0
    while i < len(header):
        row = header[i]
        i += 1
        if not row.strip() or row.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):(?:[ ]+(.*))?", row)
        if not match:
            raise Invalid("frontmatter 仅支持顶层 key: 标量；拒绝伪 YAML/制表符/未知缩进")
        key, raw = match[1], match[2] or ""
        if key in result:
            raise Invalid(f"frontmatter 重复键：{key}")
        if key not in {"name", "description", "license", "compatibility", "metadata"}:
            raise Invalid(f"frontmatter 不支持字段：{key}")
        if key == "metadata":
            if raw.strip() and not raw.lstrip().startswith("#"):
                raise Invalid("metadata 仅支持两空格缩进的 version 映射")
            nested: dict = {}
            while i < len(header) and (not header[i].strip() or header[i].startswith(" ")):
                child = header[i]
                i += 1
                if not child.strip() or child.lstrip().startswith("#"):
                    continue
                child_match = re.fullmatch(r"  version: +(.+)", child)
                if not child_match or nested:
                    raise Invalid("metadata 仅允许唯一 version 简单标量")
                nested["version"] = yaml_scalar(child_match[1])
            if not nested:
                raise Invalid("metadata 映射不能为空")
            result[key] = nested
        elif key == "description" and re.fullmatch(r"[|>](?:\s+#.*)?", raw.strip()):
            style = raw.strip()[0]
            block: list[str] = []
            while i < len(header) and (not header[i].strip() or header[i].startswith(" ")):
                block.append(header[i])
                i += 1
            nonempty = [line for line in block if line.strip()]
            if not nonempty:
                raise Invalid("description block 不能为空")
            indent = len(nonempty[0]) - len(nonempty[0].lstrip(" "))
            if not indent or any(len(line) - len(line.lstrip(" ")) < indent for line in nonempty):
                raise Invalid("description block 缩进不一致")
            content = [line[indent:] if line.strip() else "" for line in block]
            while content and not content[-1]:
                content.pop()
            if style == "|":
                value = "\n".join(content) + "\n"
            else:
                positions = [n for n, line in enumerate(content) if line]
                value = "\n" * positions[0]
                for index, position in enumerate(positions):
                    line = content[position]
                    value += line
                    if index + 1 < len(positions):
                        following = positions[index + 1]
                        blanks = following - position - 1
                        if line.startswith(" ") or content[following].startswith(" "):
                            value += "\n" * (blanks + 1)
                        else:
                            value += "\n" * blanks if blanks else " "
                value += "\n"
            result[key] = value
        else:
            result[key] = yaml_scalar(raw)
    if result.get("name") != SKILL_NAME:
        raise Invalid(f"frontmatter name 必须等于 {SKILL_NAME}")
    description = result.get("description", "")
    if not description.strip() or len(description) > 1024:
        raise Invalid("description 必须非空且按解析值不超过 1024 字符（含 block 换行）")
    if "compatibility" in result and len(result["compatibility"]) > 500:
        raise Invalid("compatibility 不得超过 500 字符")
    # 用空行替换 frontmatter，保持正文链接的原始行号。
    return result, "\n" * (end + 1) + "".join(rows[end + 1:])


class IdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.ids.update(value for key, value in attrs if key == "id" and value is not None)


def anchors(text: str) -> set[str]:
    result: set[str] = set()
    used: set[str] = set()
    source = text.splitlines()
    visible = prose_lines(text)
    parser = IdParser()
    parser.feed("\n".join(line for _, line in visible))
    result.update(parser.ids)
    for number, line in visible:
        if not re.match(r" {0,3}#{1,6}(?:\s|$)", line):
            continue
        title = re.sub(r"^ {0,3}#{1,6}(?:[ \t]+|$)", "", source[number - 1])
        title = re.sub(r"\s+#+\s*$", "", title).strip()
        title = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", title)
        title = html.unescape(re.sub(r"<[^>]*>", "", title)).lower()
        title = title.replace("`", "")
        slug = "".join(c for c in title if c in "-_ " or c.isalnum())
        slug = slug.replace(" ", "-")
        base, suffix = slug, 0
        while slug in used:
            suffix += 1
            slug = f"{base}-{suffix}"
        used.add(slug)
        result.add(slug)
    return result


def check_links(relative: str, text: str, root: Path, report: Report, texts: dict[str, str],
                *, prospective_targets: frozenset[str] = frozenset()) -> None:
    path = root / relative
    for link in links(text):
        if not link.target.strip():
            report.error("link.empty", "链接目标为空或引用未定义", relative, link.line)
            continue
        try:
            local, fragment = local_target(link.target)
            if local is None:
                if urlsplit(link.target).scheme.lower() not in {"http", "https", "mailto"}:
                    report.warning("link.scheme", "外链协议未验证且不访问", relative, link.line)
                continue
            target = guarded_path(path.parent / local if local else path, root)
            if not target.exists():
                # 只供显式维护在首次生成清单前验证自引用；普通校验没有该豁免。
                if target.relative_to(root).as_posix() in prospective_targets and not fragment:
                    continue
                report.error("link.missing", f"本地链接目标不存在：{link.target}", relative, link.line)
                continue
            if fragment:
                target_name = target.relative_to(root).as_posix()
                value = unquote(urlsplit(link.target).fragment, encoding="utf-8", errors="strict")
                target_text = text if target == path else texts.get(target_name)
                if target.suffix.lower() == ".md" and target_text is not None and value in anchors(target_text):
                    continue
                report.warning("link.fragment_unverified", f"锚点未验证（支持 ATX slug/HTML id 子集）：{link.target}", relative, link.line)
        except (ValueError, UnicodeError) as exc:
            report.error("link.unsafe", str(exc), relative, link.line)
        except OSError as exc:
            report.io_failure = True
            report.error("io.link", str(exc), relative, link.line)


def secret_key(name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", name.casefold())
    return compact in {"password", "passwd", "token", "apitoken", "accesstoken", "authtoken",
                       "refreshtoken", "apikey", "secret", "clientsecret", "privatekey", "cookie",
                       "authorization", "awssecretaccesskey"}


def suspicious_value(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    # 只豁免明确占位语法，不把 fake/test 前缀或测试文件整体视为安全。
    return not (value in {"...", "<redacted>", "<placeholder>", "YOUR_TOKEN", "YOUR_API_KEY"}
                or re.fullmatch(r"\$\{[A-Z_][A-Z_0-9]*\}", value))


def python_secrets(tree: ast.AST) -> list[int]:
    findings: set[int] = set()

    def literal(node: ast.AST | None) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literal(node.left), literal(node.right)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        return None

    def names(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            return [node.attr]
        if isinstance(node, ast.Subscript) and isinstance(literal(node.slice), str):
            return [literal(node.slice)]
        return []

    def assignment(target: ast.AST, value: ast.AST | None, line: int) -> None:
        if isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (ast.Tuple, ast.List)):
            for left, right in zip(target.elts, value.elts):
                assignment(left, right, line)
        elif any(secret_key(name) for name in names(target)) and suspicious_value(literal(value)):
            findings.add(line)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                assignment(target, node.value, node.lineno)
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            assignment(node.target, node.value, node.lineno)
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                name = literal(key)
                if isinstance(name, str) and secret_key(name) and suspicious_value(literal(value)):
                    findings.add(value.lineno)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg and secret_key(keyword.arg) and suspicious_value(literal(keyword.value)):
                    findings.add(keyword.value.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg, default in zip((args.posonlyargs + args.args)[-len(args.defaults):], args.defaults):
                if secret_key(arg.arg) and suspicious_value(literal(default)):
                    findings.add(default.lineno)
            for arg, default in zip(args.kwonlyargs, args.kw_defaults):
                if secret_key(arg.arg) and suspicious_value(literal(default)):
                    findings.add(default.lineno)
    return sorted(findings)


def check_text(relative: str, text: str, report: Report) -> None:
    if any(c == "\ufffd" or ord(c) < 32 and c not in "\n\r\t" or ord(c) == 127 for c in text):
        report.error("text.character", "文本含替换字符或非法控制字符", relative)
    if Path(relative).suffix.lower() == ".py":
        try:
            tree = ast.parse(text, filename=relative)
        except (SyntaxError, ValueError, RecursionError) as exc:
            report.error("python.syntax", str(exc), relative, getattr(exc, "lineno", None))
            return
        for line in python_secrets(tree):
            report.error("secret.literal", "敏感字段含硬编码字符串（不回显值）", relative, line)
        # Python 字符串里的测试源码/正则不会再被作为可执行赋值扫描。
    else:
        pattern = re.compile(r'''(?im)^\s*["']?([a-z_][a-z_0-9-]*)["']?\s*[:=]\s*(.+?)\s*$''')
        for match in pattern.finditer(text):
            value = match[2].strip().rstrip(",").strip("\"'")
            if secret_key(match[1]) and suspicious_value(value):
                report.error("secret.literal", "敏感字段含硬编码值（不回显值）", relative, text.count("\n", 0, match.start()) + 1)


def validate(root: Path = ROOT, installed: Path | None = None) -> Report:
    report = Report(str(root), "installed" if installed is not None else "repository")
    try:
        root = checked_root(root)
        report.root = str(root)
        files = inventory(root)
        actual = set(files) - {MANIFEST}
        for name in sorted(REQUIRED - actual):
            report.error("files.required", "缺少强制基础资产", name)
        manifest = None
        if MANIFEST not in files:
            report.error("manifest.missing", "缺少 package-manifest.json；不能证明文件完整性", MANIFEST)
        else:
            try:
                manifest = parse_manifest(safe_text(files[MANIFEST], root))
                report.manifest = manifest
                report.version = manifest["version"]
            except (Invalid, UnicodeError) as exc:
                report.error("manifest.invalid", str(exc), MANIFEST)
        if manifest is not None:
            expected = set(manifest["files"])
            for name in sorted(expected - actual):
                report.error("files.missing", "manifest 中的文件不存在", name)
            for name in sorted(actual - expected):
                report.error("files.extra", "文件未列入 manifest", name)
        texts: dict[str, str] = {}
        for name, path in files.items():
            if name == MANIFEST:
                continue
            data = safe_bytes(path, root)
            report.files_checked += 1
            if manifest and name in manifest["files"] and hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                report.error("files.hash", "SHA256 与 manifest 不一致", name)
            if path.suffix.lower() in TEXT_SUFFIXES or name in {"LICENSE", ".gitignore", ".gitattributes"}:
                try:
                    text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
                except UnicodeError:
                    report.error("text.encoding", "文本不是有效 UTF-8/BOM 编码", name)
                    continue
                check_text(name, text, report)
                texts[name] = text
        if "SKILL.md" in texts:
            try:
                metadata, texts["SKILL.md"] = parse_metadata(texts["SKILL.md"])
                declared = metadata.get("metadata", {}).get("version")
                if declared is not None and manifest and declared != manifest["version"]:
                    report.error("metadata.version", "metadata.version 必须与 manifest 唯一版本来源一致", "SKILL.md")
            except Invalid as exc:
                report.error("metadata.invalid", str(exc), "SKILL.md")
        for name, text in texts.items():
            if Path(name).suffix.lower() in {".md", ".html", ".htm"}:
                check_links(name, text, root, report, texts)
        if installed is not None:
            compare_installed(installed, manifest, root, report)
    except Invalid as exc:
        report.error("tree.unsafe", str(exc))
    except (OSError, ValueError, RuntimeError) as exc:
        report.io_failure = True
        report.error("io.root", str(exc))
    return report


def compare_installed(installed: Path, manifest: dict | None, root: Path, report: Report) -> None:
    try:
        target = checked_root(installed)
    except FileNotFoundError:
        report.error("installed.missing", "显式指定的安装目标不存在", str(installed))
        return
    if manifest is None:
        report.error("installed.unverified", "仓库 manifest 无效，不能核对安装版", str(installed))
        return
    files = inventory(target)
    expected = set(manifest["files"]) | {MANIFEST}
    for name in sorted(expected - files.keys()):
        report.error("installed.missing", "安装版缺少文件", name)
    for name in sorted(files.keys() - expected):
        report.error("installed.extra", "安装版存在额外文件", name)
    if MANIFEST in files and safe_bytes(files[MANIFEST], target) != safe_bytes(root / MANIFEST, root):
        report.error("installed.manifest", "安装版 manifest 与仓库不一致", MANIFEST)
    for name in sorted(set(manifest["files"]) & files.keys()):
        if hashlib.sha256(safe_bytes(files[name], target)).hexdigest() != manifest["files"][name]:
            report.error("installed.hash", "安装版 SHA256 与仓库 manifest 不一致", name)


def emit(report: Report, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return
    print("通过本地校验" if not report.errors else "校验失败")
    for level, items in (("error", report.errors), ("warning", report.warnings)):
        for item in items:
            location = item["path"] + (f":{item['line']}" if item["line"] else "")
            print(f"{level} [{item['code']}] {location} {item['message']}")
    print("已请求显式安装核对。" if report.mode == "installed" else "仓库模式：未扫描任何 home/安装目录。")
    print(SCOPE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="单 Skill 根；默认当前脚本的仓库根")
    parser.add_argument("--installed", type=Path, help="显式安装版 Skill 根；不存在即失败，不自动搜索")
    parser.add_argument("--json", action="store_true", help="输出结构化校验结果")
    args = parser.parse_args(argv)
    report = validate(args.root, args.installed)
    emit(report, args.json)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
