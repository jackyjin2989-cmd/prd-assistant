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
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "scan_prd.py"

spec = importlib.util.spec_from_file_location("scan_prd", SCRIPT)
scan_prd = importlib.util.module_from_spec(spec)
sys.modules["scan_prd"] = scan_prd
spec.loader.exec_module(scan_prd)

PY = sys.executable


class ScanPrdTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
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
        findings = self.scan("t.md", "# 标题\n\n![a](images/01-a.png)\n")
        self.assertTrue(any("未引用" in m and "02-orphan" in m for m in self.reviews(findings)))

    def test_sibling_reference_suppresses_unused(self) -> None:
        """兄弟文档（哪怕用的是普通链接）引用过的图片，不该报未引用。"""
        self.write("images/01-a.png", "")
        self.write("images/02-b.png", "")
        self.write("other.md", "# 别的文档\n\n[02](images/02-b.png)\n")
        findings = self.scan("t.md", "# 标题\n\n![a](images/01-a.png)\n")
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
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
