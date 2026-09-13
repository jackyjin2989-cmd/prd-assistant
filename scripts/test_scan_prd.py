#!/usr/bin/env python3
"""scan_prd.py 的自动化测试（stdlib unittest，零依赖）。

跑法：
    python3 scripts/test_scan_prd.py
    python3 -m unittest discover -s scripts -p 'test_*.py'

维护约定：**新增或修改检查项时，必须同时加一条「应报」与一条「不应报」的用例**。
扫描类工具的第一杀手是误报 —— 规则写宽了就会被使用者弃用，而误报只有跑真实语料
才会暴露（历史教训：裸 XXX 占位模式误报 `XXXX.txt.enc.TEMP`；未扣除兄弟文档引用
导致把别人引用的图片报成未引用）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "scan_prd.py"
TMP_ROOT = pathlib.Path(tempfile.gettempdir()).resolve()
sys.path.insert(0, str(HERE))
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

spec = importlib.util.spec_from_file_location("scan_prd", SCRIPT)
scan_prd = importlib.util.module_from_spec(spec)
sys.modules["scan_prd"] = scan_prd
spec.loader.exec_module(scan_prd)

PY = sys.executable


class ScanPrdTest(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(prefix="scanner-", dir=TMP_ROOT)
        self.addCleanup(self._tmp.cleanup)
        self.dir = pathlib.Path(self._tmp.name)

    # ---------- 工具 ----------
    def write(self, name: str, text: str) -> pathlib.Path:
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def scan(self, name: str, text: str):
        findings, _ = scan_prd.scan_file(self.write(name, text))
        return findings

    @staticmethod
    def errors(findings) -> list[str]:
        return [f.message for f in findings if f.level == "error"]

    @staticmethod
    def reviews(findings) -> list[str]:
        return [f.message for f in findings if f.level == "review"]

    # ---------- 表格列数 ----------
    def test_table_column_mismatch_is_error(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n| A | B |\n|---|---|\n| 1 | 2 | 3 |\n")
        self.assertTrue(any("表格列数不一致" in m for m in self.errors(findings)))

    def test_consistent_table_passes(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(findings, [])

    def test_escaped_pipe_does_not_break_columns(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n| A | B |\n|---|---|\n| `a\\|b` | 2 |\n")
        self.assertFalse(any("表格列数不一致" in m for m in self.errors(findings)))

    def test_fenced_code_is_ignored(self) -> None:
        text = "# 标题\n\n```\n| A | B |\n|---|---|\n| 1 | 2 | 3 |\n### 跳级标题\n```\n"
        findings = self.scan("t.md", text)
        self.assertEqual(self.errors(findings), [])
        self.assertFalse(any("表格" in m or "层级" in m for m in self.reviews(findings)))

    # ---------- 标题层级 ----------
    def test_heading_level_jump_is_review(self) -> None:
        findings = self.scan("t.md", "# 一级\n\n### 直接三级\n")
        self.assertTrue(any("标题层级跳级" in m for m in self.reviews(findings)))

    def test_sequential_headings_pass(self) -> None:
        findings = self.scan("t.md", "# 一级\n\n## 二级\n\n### 三级\n")
        self.assertEqual(findings, [])

    # ---------- 图片 ----------
    def test_missing_image_and_empty_alt_are_errors(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n![](images/missing.png)\n")
        self.assertTrue(any("图片缺替代文本" in m for m in self.errors(findings)))
        self.assertTrue(any("图片文件不存在" in m for m in self.errors(findings)))

    def test_absolute_image_path_is_error(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n![图](/tmp/a.png)\n")
        self.assertTrue(any("绝对路径" in m for m in self.errors(findings)))

    def test_image_numbering_gap_is_review(self) -> None:
        self.write("images/01-a.png", "")
        self.write("images/03-c.png", "")
        text = "# 标题\n\n![a](images/01-a.png)\n\n![c](images/03-c.png)\n"
        findings = self.scan("t.md", text)
        self.assertTrue(any("编号不连续" in m for m in self.reviews(findings)))

    def test_unused_image_is_review(self) -> None:
        self.write("images/01-a.png", "")
        self.write("images/02-orphan.png", "")
        # 契约收窄：孤儿图只检查显式指定的资源目录，保留原应报断言。
        findings, _ = scan_prd.scan_file(self.write("t.md", "# 标题\n\n![a](images/01-a.png)\n"),
                                        assets_dirs=[pathlib.Path("images")])
        self.assertTrue(any("未引用" in m and "02-orphan" in m for m in self.reviews(findings)))

    def test_sibling_reference_suppresses_unused(self) -> None:
        """兄弟文档（哪怕用的是普通链接）引用过的图片，不该报未引用。"""
        self.write("images/01-a.png", "")
        self.write("images/02-b.png", "")
        self.write("other.md", "# 别的文档\n\n[02](images/02-b.png)\n")
        # 根与资源目录均显式授权后才可读兄弟文档，仍保留原不应报断言。
        findings, _ = scan_prd.scan_file(self.write("t.md", "# 标题\n\n![a](images/01-a.png)\n"),
                                        root=self.dir, assets_dirs=[pathlib.Path("images")])
        self.assertFalse(any("未引用" in m for m in self.reviews(findings)))

    # ---------- 占位与残留词 ----------
    def test_placeholder_is_error(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n待补图\n")
        self.assertTrue(any("待补图" in m for m in self.errors(findings)))

    def test_normal_placeholder_wording_is_allowed(self) -> None:
        text = "# 标题\n\n输入框占位符随币种变化。\n\n该模块整块不占位，其余内容前移。\n"
        findings = self.scan("t.md", text)
        self.assertEqual(findings, [])

    def test_scope_exclusion_word_is_review(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n本期不做优惠功能。\n")
        self.assertTrue(any("本期不做" in m for m in self.reviews(findings)))

    # ---------- 链接 ----------
    def test_broken_relative_link_is_error(self) -> None:
        findings = self.scan("t.md", "# 标题\n\n[文档](doc/missing.md)\n")
        self.assertTrue(any("相对链接失效" in m for m in self.errors(findings)))

    # ---------- 目录扫描与退出码 ----------
    def test_collect_skips_noise_dirs(self) -> None:
        self.write("keep.md", "# 保留\n")
        self.write(".git/hidden.md", "# 版本控制\n")
        self.write("node_modules/dep.md", "# 依赖\n")
        found = [p.name for p in scan_prd.collect([str(self.dir)])]
        self.assertEqual(found, ["keep.md"])

    def test_cli_exit_codes(self) -> None:
        bad = self.write("bad.md", "# 标题\n\n![](images/missing.png)\n")
        result = subprocess.run([PY, str(SCRIPT), str(bad)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout)

        good = self.write("good.md", "# 标题\n\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        result = subprocess.run([PY, str(SCRIPT), str(good)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ack_output_preserves_reason(self) -> None:
        path = self.write("ack-target.md", "# 标题\n## 验收标准\n保持已有行为。\n")
        findings, _ = scan_prd.scan_file(path)
        ack = {"version": 1, "entries": [{"fingerprint": f.fingerprint, "reason": "用户要求保留验收"}
                                        for f in findings if f.level == "review"]}
        ack_path = self.write("ack.json", json.dumps(ack))
        result = subprocess.run([PY, str(SCRIPT), str(path), "--ack", str(ack_path), "--json", "--strict"],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        found = json.loads(result.stdout)["files"][0]["findings"]
        self.assertTrue(found)
        self.assertEqual(found[0]["acknowledgement_reason"], "用户要求保留验收")

    def test_ack_does_not_expand_default_scan_root(self) -> None:
        path = self.write("delivery/prd.md", "# 标题\n正常正文。\n")
        ack_path = self.write("outside.json", '{"version": 1, "entries": []}')
        with patch.object(pathlib.Path, "read_text", side_effect=AssertionError("不应读取根外ack")):
            code = scan_prd.main([str(path), "--ack", str(ack_path), "--json"])
        self.assertEqual(code, 2)

    # ---------- G07/G08 回归：正文与结构 ----------
    def test_words_and_links_ignore_fences_comments_inline(self) -> None:
        text = '# 标题\n````md\n```\nTODO ![图](missing.png)\n~~~\n````\n<!-- TODO -->\n`TODO [文](missing.md)`\n'
        self.assertEqual(self.scan("t.md", text), [])

    def test_real_placeholder_preserves_original_line(self) -> None:
        findings = self.scan("t.md", "<!-- TODO\n隐藏 -->\n`TODO`\nTODO\n")
        self.assertEqual([(f.code, f.line) for f in findings], [("PLACEHOLDER", 4)])

    def test_indented_backticks_do_not_hide_heading(self) -> None:
        findings = self.scan("t.md", "# 一级\n\n    ```\n\n### 正文\n")
        self.assertIn("HEADING_JUMP", [f.code for f in findings])

    def test_optional_outer_table_pipes(self) -> None:
        findings = self.scan("t.md", "A | B\n:---|---:\n1 | 2 | 3\n")
        self.assertEqual([f.code for f in findings], ["TABLE_COLUMNS"])

    def test_invalid_table_separator_is_not_table(self) -> None:
        for separator in ("|---||", "|---|text|", "|:|---|", "|---|---|---|"):
            with self.subTest(separator=separator):
                self.assertEqual(self.scan("t.md", f"|A|B|\n{separator}\n|1|2|3|\n"), [])

    def test_inline_code_raw_pipe_ignored_by_declared_subset(self) -> None:
        self.assertEqual(self.scan("t.md", "A | B\n---|---\n`a|b` | 2\n"), [])

    def test_even_backslash_does_not_escape_pipe(self) -> None:
        self.assertEqual(scan_prd.count_unescaped_pipes(r"a\\|b"), 1)
        self.assertEqual(scan_prd.count_unescaped_pipes(r"a\|b"), 0)

    def test_bom_and_crlf_heading(self) -> None:
        for text in ("\ufeff# 一级\n### 三级", "# 一级\r\n### 三级"):
            with self.subTest(text=text):
                self.assertEqual([f.code for f in self.scan("t.md", text)], ["HEADING_JUMP"])

    def test_optional_section_is_review_not_semantic_proof(self) -> None:
        self.assertEqual([f.code for f in self.scan("t.md", "# 改动\n## 验收标准\n具体内容")], ["OPTIONAL_SECTION"])

    # ---------- 链接、图片与编码 ----------
    def test_angle_encoded_nested_and_titles_existing(self) -> None:
        self.write("with space.md", "# 说明")
        self.write("a(b).png", "")
        findings = self.scan("t.md", '[文](<with space.md> "标题")\n[文](with%20space.md)\n![图](a(b).png)')
        self.assertEqual(findings, [])

    def test_reference_missing_files_detected(self) -> None:
        findings = self.scan("t.md", "![图][i]\n[说明][]\n[i]: missing.png\n[说明]: missing.md")
        self.assertEqual([f.code for f in findings], ["IMAGE_MISSING", "LINK_MISSING"])

    def test_html_unquoted_missing_and_empty_alt(self) -> None:
        self.write("a.png", "")
        findings = self.scan("t.md", '<img src=missing.png alt=图>\n<img src="a.png" alt="">')
        self.assertEqual([f.code for f in findings], ["IMAGE_MISSING", "IMAGE_ALT"])

    def test_html_missing_alt_and_src(self) -> None:
        findings = self.scan("t.md", "<img>")
        self.assertEqual([f.code for f in findings], ["IMAGE_ALT", "IMAGE_SOURCE"])

    def test_local_query_uses_path_only_and_fragment_review(self) -> None:
        self.write("page.html", "<div></div>")
        self.write("image.svg", "<svg/>")
        findings = self.scan("t.md", "[文](page.html?state=empty#panel)\n![图](image.svg?v=1#view)")
        self.assertEqual([f.code for f in findings], ["FRAGMENT_UNCHECKED"] * 2)

    def test_fragment_only_does_not_read_sibling(self) -> None:
        self.assertEqual([f.code for f in self.scan("t.md", "[文](#missing)")], ["FRAGMENT_UNCHECKED"])

    def test_external_not_network_or_local_probe(self) -> None:
        file = self.write("t.md", "[文](https://example.invalid/a?q=1#part)\n![图](https://example.invalid/a.png)")
        with patch.object(pathlib.Path, "exists", side_effect=AssertionError("外链不得 exists")):
            findings, stats = scan_prd.scan_file(file)
        self.assertEqual(findings, [])
        self.assertEqual(stats["external_unchecked"], 2)

    def test_empty_target_and_undefined_reference_review(self) -> None:
        findings = self.scan("t.md", "[文](   )\n[说明][missing]")
        self.assertEqual([f.code for f in findings], ["LINK_EMPTY", "REFERENCE_UNDEFINED"])

    def test_missing_file_and_bad_encoding_structured(self) -> None:
        findings, _ = scan_prd.scan_file(self.dir / "missing.md")
        self.assertEqual(findings[0].code, "INPUT_READ")
        file = self.write("bad.md", "")
        file.write_bytes(b"# title\n\xff")
        self.assertEqual(scan_prd.scan_file(file)[0][0].code, "INPUT_ENCODING")
        self.assertEqual(self.scan("bad.md", "\ufffd")[0].code, "INPUT_ENCODING")

    def test_reused_image_deduplicated_after_path_normalization(self) -> None:
        self.write("images/01-a.png", "")
        text = "![图](images/01-a.png)\n![图](./images/%30%31-a.png)\n![图](images/../images/01-a.png)"
        self.assertEqual(self.scan("t.md", text), [])

    def test_number_sequences_separate_directories(self) -> None:
        self.write("a/01-a.png", "")
        self.write("b/01-b.png", "")
        self.assertEqual(self.scan("t.md", "![图](a/01-a.png)\n![图](b/01-b.png)"), [])

    def test_orphans_not_claimed_without_asset_directory(self) -> None:
        self.write("images/orphan.png", "")
        file = self.write("t.md", "# 标题")
        findings, stats = scan_prd.scan_file(file)
        self.assertEqual(findings, [])
        self.assertEqual(stats["assets_dirs_checked"], 0)

    def test_orphan_only_directory_found_when_explicit(self) -> None:
        self.write("images/orphan.png", "")
        findings, _ = scan_prd.scan_file(self.write("t.md", "# 标题"), assets_dirs=[pathlib.Path("images")])
        self.assertEqual([f.code for f in findings], ["IMAGE_UNUSED"])

    def test_same_basename_current_doc_not_confused(self) -> None:
        self.write("images/same.png", "")
        self.write("other/same.png", "")
        findings, _ = scan_prd.scan_file(self.write("t.md", "![图](other/same.png)"), assets_dirs=[pathlib.Path("images")])
        self.assertEqual([f.code for f in findings], ["IMAGE_UNUSED"])
        self.assertIn("images/same.png", findings[0].message)

    def test_same_basename_sibling_not_confused(self) -> None:
        self.write("images/same.png", "")
        self.write("other/same.png", "")
        self.write("other.md", "[图](other/same.png)")
        findings, _ = scan_prd.scan_file(self.write("t.md", "# 标题"), root=self.dir, assets_dirs=[pathlib.Path("images")])
        self.assertEqual([f.code for f in findings], ["IMAGE_UNUSED"])

    # ---------- 授权根与人工 canary ----------
    def test_parent_shared_allowed_only_with_explicit_root(self) -> None:
        self.write("shared/a.png", "")
        file = self.write("docs/t.md", "![图](../shared/a.png)")
        self.assertEqual(scan_prd.scan_file(file, root=self.dir)[0], [])
        self.assertEqual(scan_prd.scan_file(file)[0][0].code, "PATH_UNSAFE")

    def test_encoded_absolute_and_nested_escape_no_probe(self) -> None:
        targets = ("C%3A%2Foutside/a.png", "%5c%5cserver/share/a.png", "file%3A%2F%2Fa.png", "%252e%252e/outside.md")
        file = self.write("t.md", "\n".join(f"![图]({target})" for target in targets))
        with patch.object(pathlib.Path, "exists", side_effect=AssertionError("越界前不得 exists")), \
             patch.object(pathlib.Path, "iterdir", side_effect=AssertionError("越界前不得遍历")):
            findings, _ = scan_prd.scan_file(file)
        self.assertEqual([f.code for f in findings], ["PATH_UNSAFE"] * 4)

    def test_parent_escape_no_metadata_or_read_canary(self) -> None:
        self.write("outside/canary.md", "人工 CANARY")
        file = self.write("root/t.md", "[文](../outside/canary.md)")
        real_open = pathlib.Path.open
        opened = []
        def guarded(path, *args, **kwargs):
            opened.append(path)
            self.assertEqual(path, file)
            return real_open(path, *args, **kwargs)
        with patch.object(pathlib.Path, "open", guarded), \
             patch.object(pathlib.Path, "exists", side_effect=AssertionError("越界不 stat")), \
             patch.object(pathlib.Path, "iterdir", side_effect=AssertionError("越界不枚举")):
            findings, _ = scan_prd.scan_file(file)
        self.assertEqual([f.code for f in findings], ["PATH_UNSAFE"])
        self.assertEqual(opened, [file])

    def test_single_file_never_reads_unselected_sibling(self) -> None:
        file = self.write("t.md", "# 正文")
        self.write("sibling.md", "人工 CANARY")
        real_open = pathlib.Path.open
        opened = []
        def guarded(path, *args, **kwargs):
            opened.append(path)
            self.assertEqual(path, file)
            return real_open(path, *args, **kwargs)
        with patch.object(pathlib.Path, "open", guarded):
            self.assertEqual(scan_prd.scan_file(file, root=self.dir)[0], [])
        self.assertEqual(opened, [file])

    def test_actual_symlink_main_and_sibling_canary(self) -> None:
        outside = self.write("outside/canary.md", "人工 CANARY")
        file = self.write("root/t.md", "# 正文")
        self.write("root/images/orphan.png", "")
        link = file.parent / "linked.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"无法创建真实 symlink：{exc}")
        real_open = pathlib.Path.open
        opened = []
        def guarded(path, *args, **kwargs):
            opened.append(path)
            self.assertNotEqual(path.resolve(), outside)
            return real_open(path, *args, **kwargs)
        with patch.object(pathlib.Path, "open", guarded):
            findings, _ = scan_prd.scan_file(link)
            self.assertEqual(findings[0].code, "PATH_BOUNDARY")
            findings, _ = scan_prd.scan_file(file, root=file.parent, assets_dirs=[pathlib.Path("images")])
            self.assertEqual([f.code for f in findings], ["IMAGE_UNUSED"])
            self.assertEqual(scan_prd.collect([str(file.parent)]), [file])
        self.assertEqual(opened, [file])

    def test_actual_directory_symlink_not_followed_inside_root(self) -> None:
        self.write("source/canary.md", "人工 CANARY")
        file = self.write("docs/t.md", "# 标题")
        link = file.parent / "linked"
        try:
            link.symlink_to(self.dir / "source", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"无法创建真实目录 symlink：{exc}")
        self.assertEqual(scan_prd.collect([str(file.parent)], root=self.dir), [file])
        with self.assertRaises(ValueError):
            scan_prd.collect([str(link)], root=self.dir)

    def test_actual_junction_not_traversed(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction 专项")
        import _winapi
        self.write("outside/canary.md", "人工 CANARY")
        file = self.write("root/t.md", "# 标题")
        _winapi.CreateJunction(str(self.dir / "outside"), str(file.parent / "junction"))
        self.assertEqual(scan_prd.collect([str(file.parent)]), [file])

    def test_asset_directory_escape_configuration_error(self) -> None:
        self.write("outside/a.png", "")
        file = self.write("root/t.md", "# 标题")
        findings, _ = scan_prd.scan_file(file, assets_dirs=[pathlib.Path("../outside")])
        self.assertEqual([f.code for f in findings], ["ASSET_INPUT"])

    def test_collect_deduplicates_case_extension_and_rejects_non_md(self) -> None:
        file = self.write("doc.MD", "# 标题")
        self.assertEqual(scan_prd.collect([str(self.dir), str(file), str(file)]), [file])
        with self.assertRaises(ValueError):
            scan_prd.collect([str(self.write("bad.txt", "# 标题"))])

    def test_multiple_targets_do_not_get_common_parent_root(self) -> None:
        left = self.write("left/a.md", "[文](../right/b.md)")
        right = self.write("right/b.md", "# 标题")
        contexts = scan_prd._collect_context([str(left), str(right)])
        self.assertEqual(contexts, {left: left.parent, right: right.parent})
        self.assertEqual(scan_prd.scan_file(left, root=contexts[left])[0][0].code, "PATH_UNSAFE")

    def test_directory_target_root_allows_shared_subdirectories(self) -> None:
        self.write("shared/a.md", "# 标题")
        file = self.write("docs/t.md", "[文](../shared/a.md)")
        contexts = scan_prd._collect_context([str(self.dir)])
        self.assertEqual(contexts[file], self.dir)
        self.assertEqual(scan_prd.scan_file(file, root=contexts[file])[0], [])

    # ---------- CLI、JSON、ack ----------
    def cli(self, *args: object):
        result = subprocess.run([PY, "-B", "-X", "utf8", str(SCRIPT), "--json", *(str(arg) for arg in args)],
                                capture_output=True, text=True, encoding="utf-8", cwd=self.dir)
        self.assertNotIn("Traceback", result.stderr)
        return result.returncode, json.loads(result.stdout)

    def ack_for(self, file: pathlib.Path, *, reason: str = "用户已确认保留") -> pathlib.Path:
        findings, _ = scan_prd.scan_file(file)
        return self.write("ack.json", json.dumps({"version": 1, "entries": [
            {"fingerprint": f.fingerprint, "reason": reason} for f in findings
        ]}, ensure_ascii=False))

    def test_cli_strict_pending_and_acknowledged_review(self) -> None:
        file = self.write("t.md", "# 标题\n本期不做批量操作")
        self.assertEqual(self.cli(file)[0], 0)
        self.assertEqual(self.cli("--strict", file)[0], 1)
        ack = self.ack_for(file)
        code, result = self.cli("--strict", "--ack", ack, file)
        self.assertEqual(code, 0)
        self.assertTrue(result["files"][0]["findings"][0]["acknowledged"])
        self.assertEqual(result["pending_review"], 0)

    def test_ack_never_suppresses_security_error(self) -> None:
        file = self.write("t.md", "![图](../outside/a.png)")
        ack = self.ack_for(file)
        code, result = self.cli("--strict", "--ack", ack, file)
        self.assertEqual(code, 1)
        self.assertFalse(result["files"][0]["findings"][0]["acknowledged"])

    def test_ack_stale_after_any_document_change(self) -> None:
        file = self.write("t.md", "本期不做批量操作")
        ack = self.ack_for(file)
        file.write_text("本期不做批量操作\n新增说明", encoding="utf-8")
        code, result = self.cli("--strict", "--ack", ack, file)
        self.assertEqual(code, 2)
        self.assertIn("过期", result["configuration_error"])

    def test_ack_empty_reason_invalid(self) -> None:
        file = self.write("t.md", "本期不做批量操作")
        self.assertEqual(self.cli("--ack", self.ack_for(file, reason="  "), file)[0], 2)

    def test_ack_malformed_schema_json_and_duplicates(self) -> None:
        file = self.write("t.md", "本期不做批量操作")
        fingerprint = scan_prd.scan_file(file)[0][0].fingerprint
        entry = {"fingerprint": fingerprint, "reason": "已确认"}
        values = ["not json", "[]", json.dumps({"version": True, "entries": []}),
                  json.dumps({"version": 1, "entries": [entry, entry]}),
                  json.dumps({"version": 2, "entries": []})]
        for body in values:
            with self.subTest(body=body):
                self.assertEqual(self.cli("--ack", self.write("ack.json", body), file)[0], 2)

    def test_ack_explicit_root_refuses_outside_before_read(self) -> None:
        file = self.write("root/t.md", "# 标题")
        ack = self.write("outside/ack.json", '{"version": 1, "entries": []}')
        self.assertEqual(self.cli("--root", file.parent, "--ack", ack, file)[0], 2)

    def test_ack_outside_requires_explicit_shared_root(self) -> None:
        file = self.write("root/t.md", "# 标题")
        ack = self.write("outside/ack.json", '{"version": 1, "entries": []}')
        # 与README统一：--ack只选文件，不隐式扩展已授权根；显式共享根才可读取。
        self.assertEqual(self.cli("--ack", ack, file)[0], 2)
        self.assertEqual(self.cli("--root", self.dir, "--ack", ack, file)[0], 0)

    def test_ack_public_api_and_stale_validation(self) -> None:
        file = self.write("t.md", "本期不做批量操作")
        value = json.loads(self.ack_for(file).read_text(encoding="utf-8"))
        self.assertTrue(scan_prd.scan_file(file, acknowledgements=value)[0][0].acknowledged)
        value["entries"][0]["fingerprint"] = "0" * 64
        with self.assertRaises(ValueError):
            scan_prd.scan_file(file, acknowledgements=value)

    def test_fingerprint_stable_and_bound_to_document_identity(self) -> None:
        file = self.write("one.md", "本期不做批量操作")
        other = self.write("two.md", "本期不做批量操作")
        first = scan_prd.scan_file(file)[0][0].fingerprint
        self.assertEqual(first, scan_prd.scan_file(file)[0][0].fingerprint)
        self.assertNotEqual(first, scan_prd.scan_file(other)[0][0].fingerprint)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    def test_cli_input_errors_exit_two_and_json(self) -> None:
        for args in ((), (self.dir / "missing.md",), (self.write("bad.txt", "x"),), ("--unknown",)):
            with self.subTest(args=args):
                self.assertEqual(self.cli(*args)[0], 2)
        invalid = self.write("bad.md", "")
        invalid.write_bytes(b"\xff")
        self.assertEqual(self.cli(invalid)[0], 2)

    def test_cli_assets_require_root_and_show_coverage(self) -> None:
        file = self.write("t.md", "# 标题")
        self.write("images/orphan.png", "")
        self.assertEqual(self.cli("--assets-dir", "images", file)[0], 2)
        code, result = self.cli("--root", self.dir, "--assets-dir", "images", "--strict", file)
        self.assertEqual(code, 1)
        self.assertEqual(result["files"][0]["findings"][0]["code"], "IMAGE_UNUSED")
        self.assertEqual(self.cli(file)[1]["scope"]["orphan_images"], "未检查")

    def test_cli_relative_explicit_root(self) -> None:
        file = self.write("root/t.md", "# 标题")
        self.assertEqual(self.cli("--root", "root", file)[0], 0)

    def test_cli_multi_document_ack_is_validated_globally(self) -> None:
        one = self.write("one.md", "本期不做批量操作")
        two = self.write("two.md", "本期不做批量操作")
        findings = scan_prd.scan_file(one)[0] + scan_prd.scan_file(two)[0]
        ack = self.write("ack.json", json.dumps({"version": 1, "entries": [
            {"fingerprint": f.fingerprint, "reason": "明确确认"} for f in findings
        ]}))
        code, result = self.cli("--strict", "--ack", ack, one, two, one)
        self.assertEqual(code, 0)
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(result["acknowledged"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
