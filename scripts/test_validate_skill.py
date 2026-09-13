#!/usr/bin/env python3
"""人工文件树回归，不访问安装版或真实用户材料；PRD_TEST_TMP 指定隔离临时父目录。"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
import package_skill as packager
import validate_skill as validator


GOOD_SKILL = "---\nname: prd-assistant\ndescription: 人工离线校验夹具\n---\n# 示例\n"


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = Path(os.environ.get("PRD_TEST_TMP", tempfile.gettempdir())).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="validator-", dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "prd-assistant"
        self.root.mkdir()
        for name in sorted(validator.REQUIRED):
            self.write(name, "# 人工测试文件\n" if name.endswith(".py") else "人工测试文件\n")
        self.write("SKILL.md", GOOD_SKILL)
        self.seal()

    def write(self, name: str, text: str | bytes) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))

    def seal(self) -> dict:
        files = validator.inventory(self.root)
        document = {"schema": 1, "skill": "prd-assistant", "version": "0.0.0-dev",
                    "baseline_commit": validator.BASELINE_COMMIT,
                    "files": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for name, path in files.items() if name != validator.MANIFEST}}
        self.save_manifest(document)
        return document

    def save_manifest(self, document: dict) -> None:
        self.write(validator.MANIFEST, json.dumps(document, ensure_ascii=False, indent=2) + "\n")

    def assert_code(self, code: str, report: validator.Report | None = None, exit_code: int = 1) -> validator.Report:
        report = report or validator.validate(self.root)
        self.assertEqual(report.exit_code, exit_code, report.as_dict())
        self.assertIn(code, {item["code"] for item in report.errors}, report.as_dict())
        return report

    def cli(self, *args: str, package: bool = False, env: dict | None = None) -> subprocess.CompletedProcess:
        script = Path(packager.__file__ if package else validator.__file__)
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        environment.update(env or {})
        return subprocess.run([sys.executable, "-B", "-X", "utf8", str(script), "--root", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8", env=environment, check=False)

    def output(self, name: str = "output") -> Path:
        directory = self.base / name
        directory.mkdir()
        return directory

    def test_bootstrap_manifest_with_documentation_self_link(self) -> None:
        self.write("README.md", "# Readme\n[清单](package-manifest.json)\n")
        (self.root / validator.MANIFEST).unlink()
        self.assert_code("manifest.missing")
        packager.refresh_manifest(self.root)
        self.assertEqual(validator.validate(self.root).exit_code, 0)

    def test_bootstrap_never_excuses_unrelated_missing_link(self) -> None:
        self.write("README.md", "[清单](package-manifest.json)\n[缺失](absent.md)\n")
        (self.root / validator.MANIFEST).unlink()
        with self.assertRaises(packager.PackageError):
            packager.refresh_manifest(self.root)
        self.assertFalse((self.root / validator.MANIFEST).exists())

    def test_compatibility_length_bound(self) -> None:
        text = GOOD_SKILL.replace("description:", "compatibility: " + "a" * 501 + "\ndescription:")
        with self.assertRaises(validator.Invalid):
            validator.parse_metadata(text)
        validator.parse_metadata(text.replace("a" * 501, "a" * 500))

    def test_baseline_can_identify_later_review_without_code_change(self) -> None:
        document = self.seal()
        document["baseline_commit"] = "622c8aef39695d7100f5d0ef8b01dffcb69437ec"
        self.save_manifest(document)
        self.assertEqual(validator.validate(self.root).exit_code, 0)

    def test_clean_repository_and_no_home_discovery(self) -> None:
        with patch.object(Path, "home", side_effect=AssertionError("禁止 home 探测")):
            result = validator.validate(self.root)
        self.assertEqual(result.exit_code, 0, result.as_dict())
        self.assertFalse(result.as_dict()["installed_checked"])
        result = self.cli("--json", env={"SKILLS_DIR": str(self.base / "不存在的安装")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "repository")

    def test_missing_script_even_when_removed_from_manifest(self) -> None:
        document = self.seal()
        name = "scripts/scan_prd.py"
        (self.root / name).unlink()
        del document["files"][name]
        self.save_manifest(document)
        self.assert_code("files.required")
        self.assert_code("manifest.invalid")

    def test_every_required_asset_is_mandatory(self) -> None:
        original = self.seal()
        for name in sorted(validator.REQUIRED):
            with self.subTest(name=name):
                document = {**original, "files": dict(original["files"])}
                del document["files"][name]
                self.save_manifest(document)
                self.assert_code("manifest.invalid")

    def test_missing_manifest(self) -> None:
        (self.root / validator.MANIFEST).unlink()
        self.assert_code("manifest.missing")

    def test_hash_difference_in_script(self) -> None:
        self.write("scripts/scan_prd.py", "changed = True\n")
        self.assert_code("files.hash")

    def test_missing_file_and_extra_file(self) -> None:
        (self.root / "README.md").unlink()
        self.write("extra.md", "额外文件")
        report = self.assert_code("files.missing")
        self.assert_code("files.extra", report)

    def test_manifest_omission(self) -> None:
        self.write("extra.md", "额外文件")
        self.assert_code("files.extra")

    def test_manifest_unsafe_paths_and_duplicate_keys(self) -> None:
        original = self.seal()
        for name in ("../outside", "/outside", "C:/outside", "a\\b", "a/../b", "a//b", "a:stream",
                     "CON.txt", "trailing.", "a/\x00b", ".git/config", "__pycache__/x.pyc", validator.MANIFEST):
            with self.subTest(name=name):
                document = {**original, "files": {**original["files"], name: "0" * 64}}
                self.save_manifest(document)
                self.assert_code("manifest.invalid")
        self.write(validator.MANIFEST, '{"schema":1,"schema":1}')
        self.assert_code("manifest.invalid")

    def test_manifest_case_collisions(self) -> None:
        document = self.seal()
        document["files"].update({"Foo/a.md": "0" * 64, "foo/b.md": "0" * 64})
        self.save_manifest(document)
        self.assert_code("manifest.invalid")

    def test_actual_case_collision_or_case_variant(self) -> None:
        self.write("Case.md", "一")
        self.write("case.md", "二")
        if len(list(self.root.glob("[Cc]ase.md"))) == 2:
            self.assert_code("tree.unsafe")
        else:
            document = self.seal()
            document["files"]["case.md" if "Case.md" in document["files"] else "Case.md"] = "0" * 64
            self.save_manifest(document)
            self.assert_code("manifest.invalid")

    def test_nested_skill(self) -> None:
        self.write("nested/SKILL.md", GOOD_SKILL)
        self.assert_code("tree.unsafe")

    def test_temp_root_name_not_required_by_validator(self) -> None:
        destination = self.base / "random-fixture-name"
        self.root.rename(destination)
        self.root = destination
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        with self.assertRaises(packager.PackageError):
            packager.package(self.root, self.output())

    def test_bom_crlf_and_description_block(self) -> None:
        for style in ("|", ">"):
            with self.subTest(style=style):
                text = f"---\nname: prd-assistant\ndescription: {style}\n  " + "字" * 600 + "\n  第二行\n---\n# 示例\n"
                self.write("SKILL.md", b"\xef\xbb\xbf" + text.replace("\n", "\r\n").encode("utf-8"))
                self.seal()
                self.assertEqual(validator.validate(self.root).exit_code, 0)
        metadata, _ = validator.parse_metadata("---\nname: prd-assistant\ndescription: >\n  一\n  二\n\n  三\n---\n")
        self.assertEqual(metadata["description"], "一 二\n三\n")
        metadata, _ = validator.parse_metadata("---\nname: prd-assistant\ndescription: >\n  一\n\n    保留缩进\n  三\n---\n")
        self.assertEqual(metadata["description"], "一\n\n  保留缩进\n三\n")

    def test_description_1024_boundary(self) -> None:
        for style, length, expected in (("|", 1023, 0), ("|", 1024, 1), (">", 1023, 0), (">", 1024, 1)):
            with self.subTest(style=style, length=length):
                self.write("SKILL.md", f"---\nname: prd-assistant\ndescription: {style}\n  " + "字" * length + "\n---\n")
                self.seal()
                self.assertEqual(validator.validate(self.root).exit_code, expected)
        self.write("SKILL.md", "---\nname: prd-assistant\ndescription: " + "字" * 1024 + "\n---\n")
        self.seal()
        self.assertEqual(validator.validate(self.root).exit_code, 0)

    def test_invalid_yaml_variants(self) -> None:
        for body in ("name: prd-assistant\ndescription:", "name: prd-assistant\ndescription: ''",
                     "name: prd-assistant\ndescription: |", "name: wrong\ndescription: 测试",
                     "name: prd-assistant\nname: prd-assistant\ndescription: 测试",
                     "name:prd-assistant\ndescription: 测试", "name: prd-assistant\ndescription: [a, b]",
                     "name: prd-assistant\ndescription: &anchor value", "name: prd-assistant\ndescription: key: value",
                     "name: prd-assistant\ndescription: 测试\nmetadata:",
                     "name: prd-assistant\ndescription: 测试\nmetadata:\n  version: 0.0.0-dev\n  version: 0.0.0-dev",
                     "name: prd-assistant\ndescription: 测试\nother: value",
                     "name: prd-assistant\ndescription: |-\n  暂不支持 chomp 指示符"):
            with self.subTest(body=body):
                self.write("SKILL.md", f"---\n{body}\n---\n")
                self.seal()
                self.assert_code("metadata.invalid")

    def test_supported_scalars_and_metadata_version(self) -> None:
        text = "---\nname: 'prd-assistant'\ndescription: \"测试 # 文本\" # 注释\nlicense: MIT\ncompatibility: Python 3.10+\nmetadata:\n  version: 0.0.0-dev\n---\n"
        self.write("SKILL.md", text)
        self.seal()
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        self.write("SKILL.md", text.replace("version: 0.0.0-dev", "version: 1.0.0"))
        self.seal()
        self.assert_code("metadata.version")

    def test_bad_encoding_replacement_and_control_characters(self) -> None:
        for data, code in ((b"\xff", "text.encoding"), (GOOD_SKILL + "\ufffd", "text.character"),
                           (GOOD_SKILL + "\x00", "text.character")):
            with self.subTest(code=code):
                self.write("SKILL.md", data)
                self.seal()
                self.assert_code(code)
                result = self.cli("--json")
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("Traceback", result.stderr)

    def test_empty_link_friendly_error(self) -> None:
        for text in ("[空]()", "![空]( )", '<img alt="无目标">', "[文][未定义]"):
            with self.subTest(text=text):
                self.write("README.md", text)
                self.seal()
                self.assert_code("link.empty")

    def test_visible_images_checked_but_code_examples_ignored(self) -> None:
        for text in ("![图](missing.png)", '<img src="missing.png" alt="图">'):
            self.write("README.md", text)
            self.seal()
            self.assert_code("link.missing")
        self.write("README.md", "```md\n![图](placeholder.png)\n<img src='missing.png'>\n```\n"
                   "`[例](missing.md)`\n\n    ![缩进](missing.png)\n<!-- ![注释](missing.png) -->\n")
        self.seal()
        self.assertEqual(validator.validate(self.root).exit_code, 0)

    def test_query_fragment_slug_html_id_and_external(self) -> None:
        self.write("README.md", "# 中文标题\n# 标题 `code`\n# 中文标题\n<a id='explicit'></a>\n"
                   "[一](README.md?q=test#中文标题)\n[二](#标题-code)\n[三](#中文标题-1)\n"
                   "[四](#explicit)\n[外](https://example.invalid/no-network)\n")
        self.seal()
        result = validator.validate(self.root)
        self.assertEqual(result.exit_code, 0, result.as_dict())
        self.assertEqual(result.warnings, [])
        self.write("README.md", "[未知扩展锚点](SKILL.md#合法但无法确认)\n")
        self.seal()
        result = validator.validate(self.root)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("link.fragment_unverified", {i["code"] for i in result.warnings})

    def test_link_outside_never_read(self) -> None:
        outside = self.base / "outside.md"
        outside.write_text("不允许读取", encoding="utf-8")
        self.write("README.md", "[越界](../outside.md)\n[转义](%2e%2e/outside.md)\n")
        self.seal()
        original = Path.open

        def guarded_open(path: Path, *args, **kwargs):
            self.assertNotEqual(path, outside, "尝试读取根外内容")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded_open):
            self.assert_code("link.unsafe")

    def test_python_ast_and_secret_semantics(self) -> None:
        for source in ('API_TOKEN = "invented-fixture-value"\n',
                       'config = {"password": "invented-fixture-value"}\n',
                       'client(api_key="invented-fixture-value")\n',
                       'def function(token="invented-fixture-value"): pass\n',
                       'x.password = "invented-" + "fixture-value"\n'):
            with self.subTest(source=source):
                self.write("scripts/validate_skill.py", source)
                self.seal()
                self.assert_code("secret.literal")
        self.write("scripts/validate_skill.py", 'fixture = \'token = "invented-fixture-value"\'\npattern = r"token\\s*=\\s*value"\n')
        self.seal()
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        self.write("scripts/test_scan_prd.py", 'token = "actual-assignment-in-test"\n')
        self.seal()
        self.assert_code("secret.literal")
        self.write("scripts/test_scan_prd.py", "def broken(:\n")
        self.seal()
        self.assert_code("python.syntax")

    def test_plaintext_secret_and_sensitive_file_rejected(self) -> None:
        self.write("README.md", 'token = invented-fixture-value\n')
        self.seal()
        self.assert_code("secret.literal")
        self.write(".env", "人工夹具，不是真实秘密")
        self.assert_code("tree.unsafe")

    def test_symlink_and_junction_rejected_without_target_reads(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("不允许读取", encoding="utf-8")
        link = self.root / "linked"
        kind = "symlink"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
            kind = "junction"
        original = Path.open

        def guarded_open(path: Path, *args, **kwargs):
            self.assertFalse(path.is_relative_to(outside), "尝试读取链接指向的根外文件")
            return original(path, *args, **kwargs)
        try:
            with patch.object(Path, "open", guarded_open):
                self.assert_code("tree.unsafe")
                linked_root = validator.validate(link)
                self.assertEqual(linked_root.exit_code, 1)
        finally:
            if kind == "junction":
                link.rmdir()
            else:
                link.unlink()

    def test_mock_file_symlink_rejected_before_read(self) -> None:
        original = validator.is_reparse
        target = self.root / "README.md"
        with patch.object(validator, "is_reparse", side_effect=lambda p: p == target or original(p)):
            self.assert_code("tree.unsafe")

    def test_installed_missing_script_difference_readme_license_and_extra(self) -> None:
        installed = self.base / "installed"
        shutil.copytree(self.root, installed)
        report = validator.validate(self.root, installed)
        self.assertEqual(report.exit_code, 0)
        self.assertTrue(report.as_dict()["installed_checked"])
        for name in ("scripts/scan_prd.py", "scripts/test_validate_skill.py", "README.md", "LICENSE"):
            with self.subTest(name=name):
                original = (installed / name).read_bytes()
                (installed / name).write_bytes(b"changed\n")
                self.assert_code("installed.hash", validator.validate(self.root, installed))
                (installed / name).unlink()
                self.assert_code("installed.missing", validator.validate(self.root, installed))
                (installed / name).write_bytes(original)
        (installed / "extra.md").write_text("额外", encoding="utf-8")
        self.assert_code("installed.extra", validator.validate(self.root, installed))
        self.assert_code("installed.missing", validator.validate(self.root, self.base / "not-installed"))

    def test_io_and_cli_return_codes(self) -> None:
        self.assertEqual(validator.validate(self.base / "missing-root").exit_code, 2)
        with patch.object(validator, "safe_bytes", side_effect=PermissionError("人工权限异常")):
            self.assert_code("io.root", exit_code=2)
        result = self.cli("--installed", str(self.base / "missing"), "--json")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["installed_checked"])
        result = self.cli("--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_manifest_version_contract(self) -> None:
        original = self.seal()
        for version in ("0.0.0-dev", "1.2.3", "1.2.3-rc.1+build.2"):
            with self.subTest(version=version):
                self.save_manifest({**original, "version": version})
                self.assertEqual(validator.validate(self.root).exit_code, 0)
        for version in ("", "v1.2.3", "01.2.3", "1.2", "1.2.3-01", "1.2.3/escape", 3):
            with self.subTest(version=version):
                self.save_manifest({**original, "version": version})
                self.assert_code("manifest.invalid")
        self.save_manifest({**original, "baseline_commit": "0" * 40})
        self.assert_code("manifest.invalid")

    def test_no_hard_marker_semantic_certification(self) -> None:
        self.write("SKILL.md", GOOD_SKILL + "正文无需校验器指定固定句子。\n")
        self.seal()
        report = validator.validate(self.root)
        self.assertEqual(report.exit_code, 0)
        self.assertIn("不保证模型行为", report.as_dict()["scope"])

    def test_generated_and_compiled_excluded(self) -> None:
        self.write("__pycache__/test.pyc", b"\x00\xff")
        self.write("dist/generated.zip", b"\x00\xff")
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        document = packager.generate_manifest(self.root)
        self.assertEqual(set(document["files"]), validator.REQUIRED)

    def test_refresh_is_explicit_preserves_version_and_whitelist(self) -> None:
        original = self.seal()
        self.save_manifest({**original, "version": "1.0.0-rc.1"})
        before = (self.root / validator.MANIFEST).read_bytes()
        generated = packager.generate_manifest(self.root)
        self.assertEqual(generated["version"], "1.0.0-rc.1")
        self.assertEqual(before, (self.root / validator.MANIFEST).read_bytes())
        self.write("README.md", "明确维护的人工修改\n")
        result = self.cli("--refresh-manifest", package=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        self.write("scripts/unapproved.py", "# 未进入维护白名单\n")
        with self.assertRaises(packager.PackageError):
            packager.generate_manifest(self.root)

    def test_refresh_initial_manifest_and_missing_script_rejected(self) -> None:
        (self.root / validator.MANIFEST).unlink()
        packager.refresh_manifest(self.root)
        self.assertEqual(validator.validate(self.root).exit_code, 0)
        (self.root / "scripts/scan_prd.py").unlink()
        before = (self.root / validator.MANIFEST).read_bytes()
        with self.assertRaises(packager.PackageError):
            packager.refresh_manifest(self.root)
        self.assertEqual(before, (self.root / validator.MANIFEST).read_bytes())

    def test_successful_zip_paths_hashes_and_reproducibility(self) -> None:
        first, sums = packager.package(self.root, self.output("one"))
        second, _ = packager.package(self.root, self.output("two"))
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(sums.read_text(encoding="utf-8"), f"{hashlib.sha256(first.read_bytes()).hexdigest()}  {first.name}\n")
        with zipfile.ZipFile(first) as archive:
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            self.assertEqual(set(archive.namelist()), {"prd-assistant/" + name for name in validator.REQUIRED | {validator.MANIFEST}})
            self.assertIsNone(archive.testzip())
            self.assertTrue(all(name.startswith("prd-assistant/") and ".." not in name for name in archive.namelist()))

    def test_package_cli_and_conflicting_output(self) -> None:
        output = self.output()
        result = self.cli("--output", str(output), package=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        original = {path.name: path.read_bytes() for path in output.iterdir()}
        result = self.cli("--output", str(output), package=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(original, {path.name: path.read_bytes() for path in output.iterdir()})
        result = self.cli(package=True)
        self.assertEqual(result.returncode, 2)

    def test_only_checksum_conflict_preserves_existing_file(self) -> None:
        output = self.output()
        sums = output / "SHA256SUMS-candidate.txt"
        sums.write_text("已有人工产物", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            packager.package(self.root, output)
        self.assertEqual(list(output.iterdir()), [sums])
        self.assertEqual(sums.read_text(encoding="utf-8"), "已有人工产物")

    def test_installed_manifest_difference(self) -> None:
        installed = self.base / "installed"
        shutil.copytree(self.root, installed)
        manifest = installed / validator.MANIFEST
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        self.assert_code("installed.manifest", validator.validate(self.root, installed))

    def test_package_missing_manifest_never_refreshes_implicitly(self) -> None:
        (self.root / validator.MANIFEST).unlink()
        output = self.output()
        with self.assertRaises(packager.PackageError):
            packager.package(self.root, output)
        self.assertFalse((self.root / validator.MANIFEST).exists())
        self.assertEqual(list(output.iterdir()), [])

    def test_package_bad_output_and_label(self) -> None:
        output = self.output()
        for arguments in ((self.root, output, "../bad"), (self.root, self.root, "candidate")):
            with self.assertRaises(packager.PackageError):
                packager.package(*arguments)
        with self.assertRaises(OSError):
            packager.package(self.root, self.base / "missing-output")
        self.write("README.md", "变化未更新哈希\n")
        with self.assertRaises(packager.PackageError):
            packager.package(self.root, output)
        self.assertEqual(list(output.iterdir()), [])

    def test_package_rehash_detects_change_and_cleans_own_outputs(self) -> None:
        output = self.output()
        original = validator.safe_bytes
        reads = 0

        def changed(path: Path, root: Path) -> bytes:
            nonlocal reads
            data = original(path, root)
            if path == self.root / "README.md":
                reads += 1
                if reads == 3:
                    return data + b"changed"
            return data
        with patch.object(validator, "safe_bytes", side_effect=changed):
            with self.assertRaises(packager.PackageError):
                packager.package(self.root, output)
        self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
