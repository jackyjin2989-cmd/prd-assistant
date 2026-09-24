#!/usr/bin/env python3
"""stdlib Markdown 明示子集与根内读取；不是 CommonMark/GFM 完整解析器。

支持顶层围栏、简单缩进代码、HTML 注释、行内代码、inline/reference 链接与 img。
引用定义须在单行；不解析列表/引用块容器、自动链接、HTML a、YAML 或 Markdown 扩展。
所有位置以原文 1 起始行号表示。URL 解码属于 local_target，不属于 links/safe_resolve。
路径边界是静态文件树检查，不是抵御并发换链的操作系统沙箱。
"""
from __future__ import annotations

import html
import os
import re
import stat
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class Link:
    target: str
    line: int
    image: bool
    alt: str
    kind: str = "inline"
    reference: str | None = None


def safe_resolve(path: Path, root: Path) -> Path:
    """相对 path 按 root 解释；越界/解析失败抛 ValueError，不读取文件内容。

    root 是调用方给定的授权根，不推导公共祖先、不 expanduser。先检查词法边界，
    再检查 resolve 后真实路径边界；返回值不存在也允许，由调用方随后验证类型。
    """
    try:
        root = Path(root).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        Path(os.path.abspath(candidate)).relative_to(root)
        resolved = candidate.resolve()
        resolved.relative_to(root)
        return resolved
    except (ValueError, OSError, RuntimeError) as exc:
        raise ValueError("路径不在授权根内或无法安全解析") from exc


def read_text(path: Path, root: Path) -> str:
    """根检查后读取 UTF-8/BOM 文本；I/O/解码异常由调用方结构化处理。"""
    resolved = safe_resolve(path, root)
    if not resolved.is_file():
        raise OSError("输入不是普通文件")
    return resolved.read_text(encoding="utf-8-sig")


def is_reparse(path: Path) -> bool:
    """仅在根检查后调用；lstat 不跟随链接，兼容 Python 3.10 的 Windows junction。"""
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _blank(text: str) -> str:
    return "".join(c if c in "\r\n" else " " for c in text)


def _masked(text: str) -> str:
    text = text.removeprefix("\ufeff")
    result = list(text)
    i = 0
    fence: tuple[str, int] | None = None
    while i < len(text):
        line_start = i == 0 or text[i - 1] == "\n"
        if line_start:
            end = text.find("\n", i)
            end = len(text) if end < 0 else end + 1
            row = text[i:end].rstrip("\r\n")
            if fence:
                if re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(fence[1]) + r",}[ \t]*", row):
                    fence = None
                result[i:end] = _blank(text[i:end])
                i = end
                continue
            opening = re.match(r" {0,3}(`{3,}|~{3,})(.*)$", row)
            if opening and not (opening[1][0] == "`" and "`" in opening[2]):
                fence = (opening[1][0], len(opening[1]))
                result[i:end] = _blank(text[i:end])
                i = end
                continue
            if row.startswith(("    ", "\t")):
                result[i:end] = _blank(text[i:end])
                i = end
                continue
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4)
            end = len(text) if end < 0 else end + 3
            result[i:end] = _blank(text[i:end])
            i = end
            continue
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == "`":
            run = re.match(r"`+", text[i:])[0]
            # 代码跨度不跨空段；相同长度的 delimiter 才能闭合。
            limit = re.search(r"\n[ \t\r]*\n", text[i + len(run):])
            end_limit = i + len(run) + limit.start() if limit else len(text)
            closing = re.search(r"(?<!`)" + run + r"(?!`)", text[i + len(run):end_limit])
            if closing:
                end = i + len(run) + closing.end()
                result[i:end] = _blank(text[i:end])
                i = end
                continue
            i += len(run)
            continue
        i += 1
    return "".join(result)


def prose_lines(text: str) -> list[tuple[int, str]]:
    """屏蔽区替换为空格并保留换行；返回包含空行的 (原行号, 正文) 列表。"""
    return list(enumerate(_masked(text).splitlines(), start=1))


def _unescape(text: str) -> str:
    # 仅去 Markdown 标点转义，不能把 Windows 路径的普通反斜线删掉。
    return html.unescape(re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", text))


def _label(text: str) -> str:
    return " ".join(_unescape(text).split()).casefold()


def _bracket_end(text: str, start: int) -> int | None:
    depth = 1
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _destination(text: str, start: int) -> tuple[str, int] | None:
    i = start
    if i < len(text) and text[i] == "<":
        i += 1
        begin = i
        while i < len(text):
            if text[i] == "\\":
                i += 2
                continue
            if text[i] in "\r\n<":
                return None
            if text[i] == ">":
                return _unescape(text[begin:i]), i + 1
            i += 1
        return None
    begin = i
    depth = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            i += 2
            continue
        if char.isspace():
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        i += 1
    if depth:
        return None
    return _unescape(text[begin:i]), i


def _title_end(text: str, start: int) -> int | None:
    if start >= len(text) or text[start] not in "\"'(":
        return None
    close = ")" if text[start] == "(" else text[start]
    i = start + 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
        elif text[i] == close:
            return i + 1
        else:
            i += 1
    return None


class _ImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attrs: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.attrs = dict(attrs)


_IMG = re.compile(r'''<img\b(?:[^>"']|"[^"]*"|'[^']*')*>''', re.I)


def links(text: str) -> list[Link]:
    """解析可识别的链接；target 保留百分号编码/query/fragment，不访问磁盘或网络。

    未使用的引用定义不作为链接返回；未定义的全/折叠引用返回 kind=unresolved、
    target=''，普通无定义 [文字] 仍是正文。HTML 缺 src 返回空 target。
    """
    source = text.removeprefix("\ufeff")
    masked = _masked(source)
    definitions: dict[str, str] = {}
    rows = masked.splitlines(keepends=True)
    for index, row in enumerate(rows):
        match = re.match(r" {0,3}\[([^\]\n]+)\]:[ \t]*", row)
        if not match:
            continue
        parsed = _destination(row.rstrip("\r\n"), match.end())
        if parsed is None:
            continue
        target, end = parsed
        tail = row[end:].strip()
        if tail and _title_end(tail, 0) != len(tail):
            continue
        definitions.setdefault(_label(match[1]), target)
        rows[index] = _blank(row)
    masked = "".join(rows)
    found: list[tuple[int, Link]] = []
    chars = list(masked)
    for match in _IMG.finditer(masked):
        parser = _ImageParser()
        parser.feed(source[match.start():match.end()])
        attrs = parser.attrs
        found.append((match.start(), Link(attrs.get("src") or "", source.count("\n", 0, match.start()) + 1,
                                         True, attrs.get("alt") or "", "html")))
        chars[match.start():match.end()] = _blank(match[0])
    masked = "".join(chars)

    def parse_segment(start: int, limit: int) -> None:
        i = start
        while i < limit:
            if masked[i] == "\\":
                i += 2
                continue
            image = masked.startswith("![", i)
            bracket = i + 1 if image else i
            if masked[bracket:bracket + 1] != "[":
                i += 1
                continue
            close = _bracket_end(masked, bracket)
            if close is None or close >= limit:
                i += 1
                continue
            label = source[bracket + 1:close]
            end = close + 1
            kind = "reference"
            ref: str | None = None
            target: str | None = None
            if masked[end:end + 1] == "(":
                begin = end + 1
                while begin < limit and masked[begin].isspace():
                    begin += 1
                parsed = _destination(masked, begin)
                if parsed:
                    value, pos = parsed
                    skipped = pos
                    while pos < limit and masked[pos].isspace():
                        pos += 1
                    if pos > skipped and masked[pos:pos + 1] in ("\"", "'", "("):
                        pos = _title_end(masked, pos) or limit
                        while pos < limit and masked[pos].isspace():
                            pos += 1
                    if pos < limit and masked[pos] == ")":
                        target, end, kind = value, pos + 1, "inline"
            elif masked[end:end + 1] == "[":
                ref_end = _bracket_end(masked, end)
                if ref_end is not None and ref_end < limit:
                    ref = _label(source[end + 1:ref_end] or label)
                    target = definitions.get(ref, "")
                    end = ref_end + 1
                    kind = "reference" if ref in definitions else "unresolved"
            elif _label(label) in definitions:
                target = definitions[_label(label)]
            if target is not None:
                found.append((i, Link(target, source.count("\n", 0, i) + 1, image,
                                      _unescape(label) if image else "", kind, ref)))
                if not image:
                    parse_segment(bracket + 1, close)
                i = end
            else:
                i = close + 1

    parse_segment(0, len(masked))
    return [item for _, item in sorted(found, key=lambda pair: pair[0])]


def is_absolute(target: str) -> bool:
    return target.startswith(("/", "\\")) or bool(re.match(r"^[A-Za-z]:", target)) or target.lower().startswith("file:")


def local_target(target: str) -> tuple[str | None, bool]:
    """返回 (单次解码的本地 path 或外链 None, 是否有 fragment)。

    先分离原始 URL 的 query/fragment，再解码 path；拒绝编码绝对路径、嵌套编码、
    控制字符、Windows ADS/设备名。外链只分类不访问；未知 scheme 由调用方 review。
    """
    if any(ord(char) < 32 or ord(char) == 127 for char in target):
        raise ValueError("链接含控制字符")
    if is_absolute(target):
        raise ValueError("链接用了绝对路径（含 Windows/UNC/file 路径）")
    parts = urlsplit(target)
    if parts.scheme:
        return None, bool(parts.fragment)
    decoded = unquote(parts.path, encoding="utf-8", errors="strict")
    if is_absolute(decoded):
        raise ValueError("解码后的链接用了绝对路径（含 Windows/UNC/file 路径）")
    if re.search(r"%[0-9A-Fa-f]{2}", decoded):
        raise ValueError("拒绝嵌套 URL 转义，不能再次解释剩余路径")
    if any(ord(char) < 32 or ord(char) == 127 for char in decoded) or ":" in decoded:
        raise ValueError("本地路径含控制字符或冒号")
    decoded = decoded.replace("\\", "/")
    for part in decoded.split("/"):
        if part in ("", ".", ".."):
            continue
        if part.endswith((" ", ".")) or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part):
            raise ValueError("拒绝含 Windows 设备名或歧义尾缀的路径")
    return decoded, "#" in target
