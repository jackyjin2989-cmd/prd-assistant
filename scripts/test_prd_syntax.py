#!/usr/bin/env python3
"""共享 Markdown 子集与安全根回归；所有人工文件只写 revision/tmp。"""
from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from prd_syntax import Link, links, local_target, prose_lines, read_text, safe_resolve

TMP_ROOT = pathlib.Path(tempfile.gettempdir()).resolve()


class SyntaxTest(unittest.TestCase):
    def test_link_contract(self) -> None:
        item = links("\n![文字](picture.png)")[0]
        self.assertIsInstance(item, Link)
        self.assertEqual((item.target, item.line, item.image, item.alt), ("picture.png", 2, True, "文字"))

    def test_angle_spaces_and_title(self) -> None:
        self.assertEqual(links('[说明](<with space.md> "标题")')[0].target, "with space.md")

    def test_balanced_parentheses(self) -> None:
        self.assertEqual(links("[说明](docs/a(b(c)).md)")[0].target, "docs/a(b(c)).md")

    def test_escaped_parentheses(self) -> None:
        self.assertEqual(links(r"[说明](docs/a\(b\).md)")[0].target, "docs/a(b).md")

    def test_title_variants(self) -> None:
        for title in ('"标题"', "'标题'", "(标题)"):
            with self.subTest(title=title):
                self.assertEqual(links(f"![图](a.png {title})")[0].target, "a.png")

    def test_reference_forward_full_collapsed_shortcut(self) -> None:
        result = links('[文字][a]\n![a][]\n[a]\n\n[a]: <a b.png> "标题"\n')
        self.assertEqual([item.target for item in result], ["a b.png"] * 3)
        self.assertEqual([item.line for item in result], [1, 2, 3])
        self.assertEqual([item.image for item in result], [False, True, False])

    def test_reference_normalization_first_definition(self) -> None:
        self.assertEqual(links("[x][A  B]\n[a b]: first.md\n[A B]: second.md")[0].target, "first.md")

    def test_unused_definition_not_active_link(self) -> None:
        self.assertEqual(links("[unused]: unused.md\n普通正文"), [])

    def test_unknown_shortcut_is_prose(self) -> None:
        self.assertEqual(links("[普通文字]"), [])

    def test_undefined_full_reference_is_explicit(self) -> None:
        self.assertEqual(links("[文字][missing]")[0].kind, "unresolved")

    def test_image_shortcut(self) -> None:
        self.assertEqual(links("![图]\n[图]: a.png")[0].target, "a.png")

    def test_fences_need_same_marker_and_sufficient_length(self) -> None:
        body = "# 标题\n````md\n~~~\n```\n![图](missing.png)\n`````\n[后文](ok.md)"
        self.assertEqual([(item.target, item.line) for item in links(body)], [("ok.md", 7)])

    def test_fence_trailing_text_not_closer(self) -> None:
        self.assertEqual(links("~~~\n~~~不是关闭\n![图](missing.png)\n~~~"), [])

    def test_unclosed_fence_masks_rest(self) -> None:
        self.assertEqual(links("```\n[文字](missing.md)"), [])

    def test_three_space_fence(self) -> None:
        self.assertEqual(links("   ```\n[文字](missing.md)\n   ```"), [])

    def test_four_space_fence_does_not_hide_following_prose(self) -> None:
        self.assertEqual(links("    ```\n\n[文字](ok.md)")[0].line, 3)

    def test_comment_mask_preserves_line(self) -> None:
        self.assertEqual(links("<!--\n[隐藏](x.md)\n-->\n[正文](y.md)")[0].line, 4)

    def test_inline_code_mask_and_comment_inside_code(self) -> None:
        text = "`<!--` [保留](x.md)\n`` [隐藏](y.md) ` `` [后文](z.md)"
        self.assertEqual([item.target for item in links(text)], ["x.md", "z.md"])

    def test_multiline_inline_code(self) -> None:
        self.assertEqual(links("`示例\n[隐藏](x.md)`\n[正文](y.md)")[0].line, 3)

    def test_escaped_markdown_not_links(self) -> None:
        self.assertEqual(links(r"\[x](missing.md) \!\[x](missing.png)"), [])
        # 只转义感叹号不会转义后面的普通链接，保留首轮输入作为反向对照。
        result = links(r"\[x](missing.md) \![x](missing.png)")
        self.assertEqual([(item.target, item.image) for item in result], [("missing.png", False)])

    def test_nested_image_in_link(self) -> None:
        self.assertEqual([item.target for item in links("[![缩略图](a.png)](b.md)")], ["b.md", "a.png"])

    def test_html_quoted_unquoted_empty_alt(self) -> None:
        result = links("<IMG SRC=a.png ALT=图>\n<img src='b.png' alt=''>\n<img src=\"c.png\">")
        self.assertEqual([(item.target, item.alt) for item in result], [("a.png", "图"), ("b.png", ""), ("c.png", "")])

    def test_html_entities_and_gt_in_attr(self) -> None:
        item = links('<img alt="a > b" src="a.png?v=1&amp;b=2">')[0]
        self.assertEqual((item.alt, item.target), ("a > b", "a.png?v=1&b=2"))

    def test_html_missing_src_still_returned(self) -> None:
        self.assertEqual(links('<img alt="图">')[0].target, "")

    def test_empty_destination_does_not_crash(self) -> None:
        self.assertEqual(links("[说明](   )")[0].target, "")

    def test_prose_lines_keep_line_numbers(self) -> None:
        rows = prose_lines("\ufeff# 标题\n<!-- TODO -->\n正文 `TODO`\n")
        self.assertEqual([line for line, _ in rows], [1, 2, 3])
        self.assertEqual(rows[0], (1, "# 标题"))
        self.assertNotIn("TODO", "".join(row for _, row in rows))

    def test_local_query_fragment_split_before_decode(self) -> None:
        self.assertEqual(local_target("a%23b.png?q=1#view"), ("a#b.png", True))
        self.assertEqual(local_target("a%3Fb.png?q=1"), ("a?b.png", False))

    def test_external_query_is_not_local(self) -> None:
        self.assertEqual(local_target("https://example.invalid/a?q=%252e#part"), (None, True))
        self.assertEqual(local_target("mailto:user@example.invalid"), (None, False))

    def test_encoded_absolute_variants_rejected(self) -> None:
        for target in ("%2Ftmp/a.png", "C%3A%2Fa.png", "C%3Aa.png", "%5C%5Cserver%5Cshare%5Ca.png", "file%3A%2F%2Fa.png", "//server/a.png", "file:///a.png"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                local_target(target)

    def test_nested_encoding_rejected(self) -> None:
        for target in ("%252e%252e/out.md", "C%253A%252Fa.png", "%255c%255cserver/a", "a%2520b.png"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                local_target(target)

    def test_device_names_ads_control_and_trailing_alias_rejected(self) -> None:
        for target in ("CON.png", "a/nul", "com1.txt", "a.png%3Astream", "a%00.png", "a.png.", "a.png%20"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                local_target(target)

    def test_fragment_only(self) -> None:
        self.assertEqual(local_target("#标题"), ("", True))


class SafeReadTest(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="syntax-", dir=TMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.root = self.base / "root"
        self.root.mkdir()
        self.inside = self.root / "doc.md"
        self.inside.write_text("\ufeff# 文档", encoding="utf-8")
        self.canary = self.base / "outside.md"
        self.canary.write_text("仅人工 CANARY，不得读取", encoding="utf-8")

    def test_read_bom_inside_root(self) -> None:
        self.assertEqual(read_text(self.inside, self.root), "# 文档")

    def test_relative_path_is_relative_to_root(self) -> None:
        self.assertEqual(safe_resolve(pathlib.Path("doc.md"), self.root), self.inside)

    def test_missing_path_can_resolve_without_read(self) -> None:
        self.assertEqual(safe_resolve(self.root / "missing.md", self.root), self.root / "missing.md")

    def test_outside_before_open_exists_or_enumeration(self) -> None:
        with patch.object(pathlib.Path, "open", side_effect=AssertionError("不允许读取")), \
             patch.object(pathlib.Path, "exists", side_effect=AssertionError("不允许 exists")), \
             patch.object(pathlib.Path, "iterdir", side_effect=AssertionError("不允许枚举")):
            with self.assertRaises(ValueError):
                read_text(self.canary, self.root)

    def test_parent_reference_inside_authorized_root(self) -> None:
        child = self.root / "child"
        child.mkdir()
        self.assertEqual(safe_resolve(child / "../doc.md", self.root), self.inside)

    def test_similar_prefix_not_containment(self) -> None:
        with self.assertRaises(ValueError):
            safe_resolve(self.base / "root-other/doc.md", self.root)

    def test_actual_file_symlink_canary_not_read(self) -> None:
        link = self.root / "linked.md"
        try:
            link.symlink_to(self.canary)
        except OSError as exc:
            self.skipTest(f"无法创建真实 symlink：{exc}")
        with patch.object(pathlib.Path, "open", side_effect=AssertionError("不得读取 canary")):
            with self.assertRaises(ValueError):
                read_text(link, self.root)

    def test_actual_junction_canary_not_read(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction 专项")
        import _winapi
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "canary.md").write_text("人工 CANARY", encoding="utf-8")
        junction = self.root / "junction"
        _winapi.CreateJunction(str(outside), str(junction))
        with patch.object(pathlib.Path, "open", side_effect=AssertionError("不得读取 canary")):
            with self.assertRaises(ValueError):
                read_text(junction / "canary.md", self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
