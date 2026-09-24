#!/usr/bin/env python3
"""PRD 静态扫描（stdlib，Python 3.10+ 语法目标）。

scan_file 默认仅读取选中文档，根默认为文件父目录；目录 target 的根为该目录。
--root 限定同一授权交付根；不推导多个 target 的公共祖先、不 expanduser。
--assets-dir 仅检查明确资源目录；CLI 要求同时给 --root，允许读根内安全兄弟 MD。
未指定资源目录不做孤儿图检查。外链不联网，本地 fragment 只生成待确认项。
--ack FILE 是人工填写的 version=1 JSON；只确认 review，不消除 error。
退出码：0 通过，1 存在 error/strict 下未确认 review，2 配置或输入异常。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from prd_syntax import is_absolute, is_reparse, links, local_target, prose_lines, read_text, safe_resolve

SCOPE_WORDS = [
    r"本期不做", r"本期不含", r"本期不涉及", r"不在本期", r"范围排除",
    r"暂不(?:做|支持|考虑)", r"非[^，。；]{0,6}版", r"不再(?:展示|支持|提供)",
]
TRACE_WORDS = [
    r'原[「『"]', r"（原", r"已改为", r"已调整", r"已删除", r"已清理",
    r"曾考虑", r"之前(?:的|是)", r"(?<!不)占位(?!符|文案)", r"草稿", r"待补",
]
PLACEHOLDER_WORDS = [r"截图占位", r"待补图", r"图片占位", r"\bTODO\b", r"\bFIXME\b", r"\bTBD\b"]
ARTIFACT_WORDS = [r"本文截图取自", r"截图取自该原型", r"中台返回的文件\s*URL"]
OPTIONAL_HEADINGS = {"验收标准", "测试用例", "成功判定", "里程碑", "风险评估", "FAQ", "版本记录", "名词解释", "非功能要求"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
SKIP_DIRS = {"node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
INPUT_CODES = {"INPUT_READ", "INPUT_ENCODING", "INPUT_TYPE", "ASSET_INPUT"}


@dataclass
class Finding:
    level: str
    line: int | None
    message: str
    code: str = "UNCLASSIFIED"
    fingerprint: str = ""
    acknowledged: bool = False
    acknowledgement_reason: str | None = None


def is_external(target: str) -> bool:
    try:
        return local_target(target)[0] is None
    except (ValueError, UnicodeError):
        return False


def _pipe_positions(line: str) -> list[int]:
    positions: list[int] = []
    escapes = 0
    for i, char in enumerate(line):
        if char == "|" and escapes % 2 == 0:
            positions.append(i)
        escapes = escapes + 1 if char == "\\" else 0
    return positions


def count_unescaped_pipes(line: str) -> int:
    return len(_pipe_positions(line))


def _cells(line: str, original: str | None = None) -> list[str] | None:
    row = line.strip()
    original = line if original is None else original
    positions = _pipe_positions(row)
    if not positions:
        return None
    pieces: list[str] = []
    start = 0
    for pos in positions:
        pieces.append(row[start:pos].strip())
        start = pos + 1
    pieces.append(row[start:].strip())
    # 被屏蔽的代码单元格仍占一列；外侧竖线身份必须按原始行判断。
    if positions[0] == 0 and original.lstrip().startswith("|"):
        pieces.pop(0)
    if positions[-1] == len(row) - 1 and original.rstrip().endswith("|"):
        pieces.pop()
    return pieces


def scan_structure(text: str) -> list[Finding]:
    """列数是交付一致性检查；忽略代码跨度内管道，不声称完整 GFM 兼容。"""
    findings: list[Finding] = []
    rows = prose_lines(text)
    original_rows = text.removeprefix("\ufeff").splitlines()
    previous_level = 0
    table_columns: int | None = None
    for index, (line_no, row) in enumerate(rows):
        heading = re.match(r"^ {0,3}(#{1,6})\s+(\S.*?)\s*#*\s*$", row)
        if heading:
            level = len(heading[1])
            if previous_level and level > previous_level + 1:
                findings.append(Finding("review", line_no,
                                        f"标题层级跳级：从 {'#' * previous_level} 跳到 {'#' * level}（{row.strip()[:30]}）", "HEADING_JUMP"))
            previous_level = level
            title = re.sub(r"^\d+(?:\.\d+)*(?:[.、．])?\s+", "", heading[2])
            if title in OPTIONAL_HEADINGS:
                findings.append(Finding("review", line_no, f"可选章节需人工确认是否明确要求：{title}", "OPTIONAL_SECTION"))
        cells = _cells(row, original_rows[index])
        if table_columns is not None:
            if cells is None or not row.strip() or heading:
                table_columns = None
            else:
                if len(cells) != table_columns:
                    findings.append(Finding("error", line_no,
                                            f"表格列数不一致（应为 {table_columns} 列，本行 {len(cells)} 列）：{row.strip()[:50]}", "TABLE_COLUMNS"))
                continue
        if cells and all(re.fullmatch(r":?-+:?", cell) for cell in cells) and index:
            header = _cells(rows[index - 1][1], original_rows[index - 1])
            if header and len(header) == len(cells):
                table_columns = len(cells)
    return findings


def scan_words(text: str, patterns: list[str], level: str, label: str, code: str = "WORD_REVIEW") -> list[Finding]:
    findings: list[Finding] = []
    compiled = [re.compile(pattern) for pattern in patterns]
    for index, row in prose_lines(text):
        for pattern in compiled:
            match = pattern.search(row)
            if match:
                findings.append(Finding(level, index, f"{label}「{match[0]}」：{row.strip()[:60]}", code))
    return findings


def _fingerprint(findings: list[Finding], path: Path, content_hash: str) -> None:
    for finding in findings:
        payload = [str(path), content_hash, finding.code, finding.line, finding.message]
        finding.fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _ack_entries(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"version", "entries"} or type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("ack 必须为 version=1、entries 数组的 JSON 对象")
    if not isinstance(value["entries"], list):
        raise ValueError("ack entries 必须是数组")
    entries: dict[str, str] = {}
    for item in value["entries"]:
        if not isinstance(item, dict) or set(item) != {"fingerprint", "reason"}:
            raise ValueError("ack 条目必须且只能包含 fingerprint 和 reason")
        fingerprint, reason = item["fingerprint"], item["reason"]
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("ack fingerprint 必须是 64 位小写 SHA-256")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("ack reason 不得为空")
        if fingerprint in entries:
            raise ValueError("ack fingerprint 重复")
        entries[fingerprint] = reason.strip()
    return entries


def apply_acknowledgements(findings: list[Finding], acknowledgements: object) -> None:
    entries = _ack_entries(acknowledgements)
    known = {finding.fingerprint for finding in findings}
    if set(entries) - known:
        raise ValueError("ack 已过期或不属于本次扫描；请重新核对文档与发现指纹")
    for finding in findings:
        finding.acknowledged = finding.level == "review" and finding.fingerprint in entries
        finding.acknowledgement_reason = entries[finding.fingerprint] if finding.acknowledged else None


def _walk(folder: Path, root: Path) -> list[Path]:
    """静态安全遍历；不跟随任何目录/文件 reparse，路径解析失败的条目不进入队列。"""
    folder = safe_resolve(folder, root)
    result: list[Path] = []
    for raw in sorted(folder.iterdir()):
        try:
            path = safe_resolve(raw, root)
        except ValueError:
            continue
        if is_reparse(raw):
            continue
        if raw.name.startswith(".") or raw.name in SKIP_DIRS:
            continue
        if path.is_dir():
            result.extend(_walk(path, root))
        elif path.is_file():
            result.append(path)
    return result


def _asset_findings(path: Path, root: Path, text: str, assets_dirs: list[Path], include_siblings: bool) -> list[Finding]:
    used: set[Path] = set()
    docs = [(path, text)]
    if include_siblings:
        for raw in sorted(safe_resolve(path.parent, root).iterdir()):
            if raw.suffix.lower() != ".md":
                continue
            try:
                sibling = safe_resolve(raw, root)
            except ValueError:
                continue
            if sibling == path or is_reparse(raw) or not sibling.is_file():
                continue
            docs.append((sibling, read_text(sibling, root)))
    for doc, body in docs:
        for link in links(body):
            try:
                target, _ = local_target(link.target)
                if target:
                    used.add(safe_resolve(doc.parent / target, root))
            except (ValueError, UnicodeError):
                continue
    findings: list[Finding] = []
    folders: set[Path] = set()
    for raw in assets_dirs:
        raw = Path(raw)
        raw = raw if raw.is_absolute() else root / raw
        folder = safe_resolve(raw, root)
        if is_reparse(raw) or not folder.is_dir():
            raise ValueError("资源目录必须是授权根内的普通目录，不接受 symlink/junction")
        folders.add(folder)
    orphaned: set[Path] = set()
    for folder in sorted(folders):
        orphaned.update(item for item in _walk(folder, root) if item.suffix.lower() in IMAGE_SUFFIXES and item not in used)
    for orphan in sorted(orphaned):
        findings.append(Finding("review", None, f"明确资源目录内未引用的图片（当前及已授权同目录文档）：{orphan.relative_to(root).as_posix()}", "IMAGE_UNUSED"))
    return findings


def scan_file(path: Path, *, root: Path | None = None, acknowledgements: dict[str, object] | None = None,
              assets_dirs: list[Path] | None = None) -> tuple[list[Finding], dict[str, int]]:
    """返回 findings/stats；输入文件异常为 error，ack 配置异常抛 ValueError。

    assets_dirs 是可选的新增关键字；未传时绝不枚举兄弟文档/资源目录。
    显式 root + assets_dirs 才允许读取同目录安全兄弟 Markdown 以扣除共享引用。
    """
    findings: list[Finding] = []
    stats = {"images": 0, "links": 0, "external_unchecked": 0, "assets_dirs_checked": 0}
    original = Path(path).absolute()
    include_siblings = root is not None
    boundary = Path(root) if root is not None else original.parent
    digest = "unread"
    try:
        path = safe_resolve(original, boundary)
        boundary = safe_resolve(boundary, boundary)
        if path.suffix.lower() != ".md":
            findings.append(Finding("error", None, "输入文件必须为 Markdown（.md，大小写均可）", "INPUT_TYPE"))
            text = ""
        else:
            if not path.is_file():
                raise OSError("输入不是普通文件")
            data = safe_resolve(path, boundary).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            text = data.decode("utf-8-sig")
    except UnicodeError:
        findings.append(Finding("error", None, "非 UTF-8 编码，无法读取", "INPUT_ENCODING"))
        text = ""
    except ValueError as exc:
        findings.append(Finding("error", None, str(exc), "PATH_BOUNDARY"))
        text = ""
    except OSError:
        findings.append(Finding("error", None, "文件缺失、不是普通文件或无法读取", "INPUT_READ"))
        text = ""
    if findings:
        _fingerprint(findings, original, digest)
        if acknowledgements is not None:
            apply_acknowledgements(findings, acknowledgements)
        return findings, stats
    if "\ufffd" in text:
        findings.append(Finding("error", None, "含无效编码字符 (U+FFFD)，文本已损坏", "INPUT_ENCODING"))
    findings += scan_words(text, SCOPE_WORDS, "review", "疑似范围排除", "SCOPE_WORD")
    findings += scan_words(text, TRACE_WORDS, "review", "疑似迭代痕迹", "TRACE_WORD")
    findings += scan_words(text, ARTIFACT_WORDS, "review", "疑似交付物/实现细节", "ARTIFACT_WORD")
    findings += scan_words(text, PLACEHOLDER_WORDS, "error", "占位残留", "PLACEHOLDER")
    findings += scan_structure(text)
    order: dict[Path, list[int]] = {}
    seen_images: set[Path] = set()
    for link in links(text):
        if link.kind == "unresolved":
            findings.append(Finding("review", link.line, f"引用定义未找到：{link.reference}", "REFERENCE_UNDEFINED"))
            continue
        if link.image and not link.alt.strip():
            findings.append(Finding("error", link.line, f"图片缺替代文本：{link.target}", "IMAGE_ALT"))
        if not link.target:
            if link.image:
                findings.append(Finding("error", link.line, "图片缺少 src 或目标为空", "IMAGE_SOURCE"))
            else:
                findings.append(Finding("review", link.line, "链接目标为空，需人工确认是否有意指向本文", "LINK_EMPTY"))
            continue
        try:
            target, fragment = local_target(link.target)
            if target is None:
                stats["external_unchecked"] += 1
                continue
            stats["images" if link.image else "links"] += 1
            resolved = safe_resolve(path.parent / target if target else path, boundary)
            if not resolved.exists() or (link.image and not resolved.is_file()):
                message = "图片文件不存在" if link.image else "相对链接失效"
                findings.append(Finding("error", link.line, f"{message}：{link.target}", "IMAGE_MISSING" if link.image else "LINK_MISSING"))
            elif link.image and resolved not in seen_images:
                seen_images.add(resolved)
                number = re.match(r"^(\d+)", resolved.name)
                if number:
                    order.setdefault(resolved.parent, []).append(int(number[1]))
            if fragment:
                findings.append(Finding("review", link.line, f"fragment/锚点尚未验证：{link.target}", "FRAGMENT_UNCHECKED"))
        except (ValueError, UnicodeError) as exc:
            findings.append(Finding("error", link.line, f"不安全链接：{link.target}（{exc}）", "PATH_UNSAFE"))
        except OSError:
            findings.append(Finding("error", link.line, f"本地目标无法检查：{link.target}", "LINK_IO"))
    for folder, numbers in order.items():
        if len(numbers) >= 2 and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            findings.append(Finding("review", None,
                                    f"图片编号不连续或与出现顺序不一致：{folder.relative_to(boundary).as_posix()} {numbers}", "IMAGE_NUMBERING"))
    if assets_dirs:
        try:
            findings += _asset_findings(path, boundary, text, assets_dirs, include_siblings)
            stats["assets_dirs_checked"] = len(assets_dirs)
        except (ValueError, OSError, UnicodeError) as exc:
            findings.append(Finding("error", None, f"资源目录/共享文档检查失败：{type(exc).__name__}", "ASSET_INPUT"))
    _fingerprint(findings, path, digest)
    if acknowledgements is not None:
        apply_acknowledgements(findings, acknowledgements)
    return findings, stats


def _collect_context(targets: list[str], root: Path | None = None) -> dict[Path, Path]:
    files: dict[Path, Path] = {}
    if root is not None:
        root = Path(root).absolute()
        root = safe_resolve(root, root)
        if not root.is_dir():
            raise ValueError("--root 必须是存在的目录")
    for target in targets:
        raw = Path(target).absolute()
        boundary = root if root is not None else raw.parent
        path = safe_resolve(raw, boundary)
        if path.is_dir():
            if is_reparse(raw):
                raise ValueError("目录 target 不允许 symlink/junction")
            boundary = root if root is not None else path
            selected = [item for item in _walk(path, boundary) if item.suffix.lower() == ".md"]
        elif path.is_file():
            if raw.suffix.lower() != ".md" or path.suffix.lower() != ".md":
                raise ValueError("输入文件扩展名必须为 .md")
            selected = [path]
        else:
            raise ValueError("target 不存在或不是普通文件/目录")
        for item in selected:
            # 重复 target 的授权取较窄根，不因参数先后意外扩大授权。
            if item not in files or boundary.is_relative_to(files[item]):
                files[item] = boundary
    return files


def collect(targets: list[str], *, root: Path | None = None) -> list[Path]:
    """顺序稳定的真实路径去重；非法 target 抛 ValueError/OSError，不输出旁路文本。"""
    return list(_collect_context(targets, root))


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = _Parser(description=__doc__)
    parser.add_argument("targets", nargs="+")
    parser.add_argument("--strict", action="store_true", help="未确认 review 也失败")
    parser.add_argument("--root", type=Path, help="明确授权交付根")
    parser.add_argument("--assets-dir", type=Path, action="append", default=[], help="根内资源目录，可重复；须同时给 --root")
    parser.add_argument("--ack", type=Path, help="人工确认 JSON，不自动生成")
    parser.add_argument("--json", action="store_true", help="向标准输出打印 JSON")
    records: list[dict[str, object]] = []
    try:
        args = parser.parse_args(argv)
        if args.assets_dir and args.root is None:
            raise ValueError("--assets-dir 须同时指定 --root，避免扩大或混淆授权根")
        contexts = _collect_context(args.targets, args.root)
        if not contexts:
            raise ValueError("未找到可扫描的 Markdown 文件")
        ack: object | None = None
        if args.ack is not None:
            raw = args.ack.absolute()
            boundary = None
            for allowed in set(contexts.values()):
                try:
                    safe_resolve(raw, allowed)
                    boundary = allowed
                    break
                except ValueError:
                    continue
            if boundary is None:
                raise ValueError("ack 必须位于本次已授权的扫描根内；不会扩大到确认文件的父目录")
            ack = json.loads(read_text(raw, boundary))
            _ack_entries(ack)
        all_findings: list[Finding] = []
        for path, boundary in contexts.items():
            findings, stats = scan_file(path, root=boundary, assets_dirs=args.assets_dir)
            records.append({"path": str(path), "root": str(boundary), "findings": findings, "stats": stats})
            all_findings.extend(findings)
        if ack is not None:
            apply_acknowledgements(all_findings, ack)
        errors = sum(item.level == "error" for item in all_findings)
        pending = sum(item.level == "review" and not item.acknowledged for item in all_findings)
        acknowledged = sum(item.acknowledged for item in all_findings)
        exit_code = 2 if any(item.code in INPUT_CODES for item in all_findings) else int(bool(errors or (args.strict and pending)))
        for record in records:
            record["findings"] = [asdict(item) for item in record["findings"]]
        result = {"version": 1, "files": records, "errors": errors, "pending_review": pending,
                  "acknowledged": acknowledged, "exit_code": exit_code,
                  "scope": {"external_urls": "未联网验证", "fragments": "仅提示人工确认", "orphan_images": "仅明确资源目录" if args.assets_dir else "未检查"}}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for record in records:
                print(record["path"])
                for item in record["findings"]:
                    state = "已确认" if item["acknowledged"] else item["level"]
                    print(f"  {state} [{item['code']}] 行 {item['line'] or '-'} {item['message']} ({item['fingerprint']})")
                    if item["acknowledgement_reason"]:
                        print(f"    确认理由：{item['acknowledgement_reason']}")
            print(f"汇总：{errors} 个错误，{pending} 项未确认，{acknowledged} 项已确认；外链未联网验证，锚点未验证。")
            if not args.assets_dir:
                print("未指定资源目录：未检查孤儿图片。静态扫描不替代完整产品审校。")
        return exit_code
    except (ValueError, OSError, UnicodeError) as exc:
        message = f"配置/输入错误：{exc}"
        if "--json" in argv:
            print(json.dumps({"version": 1, "files": [], "configuration_error": message, "exit_code": 2}, ensure_ascii=False))
        else:
            print(message)
        return 2


if __name__ == "__main__":
    sys.exit(main())
