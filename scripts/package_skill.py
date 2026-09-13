#!/usr/bin/env python3
"""离线候选包工具；不读取 Git、账户、网络或安装目录。

常规命令只读根目录。--refresh-manifest 是必须明确请求的维护写入命令，
先读取原清单再更新；只接纳固定基础资产白名单，不自动执行、不收集秘密缓存。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
import validate_skill as validator


class PackageError(validator.Invalid):
    pass


def generate_manifest(root: Path) -> dict:
    """纯生成：检查固定路径白名单、内容和新鲜度，返回清单而不写盘。"""
    root = validator.checked_root(root)
    files = validator.inventory(root)
    actual = set(files) - {validator.MANIFEST}
    if actual != validator.REQUIRED:
        raise PackageError("维护白名单不匹配；缺少：" + ", ".join(sorted(validator.REQUIRED - actual))
                           + "；额外：" + ", ".join(sorted(actual - validator.REQUIRED)))
    if validator.MANIFEST in files:
        # 保留唯一版本来源，不从 Git、README、环境变量或目录名猜版本。
        try:
            document = json.loads(validator.safe_text(files[validator.MANIFEST], root),
                                  object_pairs_hook=validator.unique_object)
        except (ValueError, RecursionError) as exc:
            raise PackageError("现有 manifest 不是有效 JSON，拒绝覆盖") from exc
        if not isinstance(document, dict):
            raise PackageError("现有 manifest 必须是对象")
    else:
        document = {"schema": 1, "skill": validator.SKILL_NAME, "version": "0.0.0-dev",
                    "baseline_commit": validator.BASELINE_COMMIT, "files": {}}
    document["files"] = {name: hashlib.sha256(validator.safe_bytes(files[name], root)).hexdigest()
                         for name in sorted(actual)}
    validator.parse_manifest(json.dumps(document))
    report = validator.Report(str(root))
    texts: dict[str, str] = {}
    for name in sorted(actual):
        path = files[name]
        if path.suffix.lower() in validator.TEXT_SUFFIXES or name in {"LICENSE", ".gitignore", ".gitattributes"}:
            try:
                texts[name] = validator.safe_text(path, root)
            except UnicodeError as exc:
                raise PackageError(f"无效 UTF-8：{name}") from exc
            validator.check_text(name, texts[name], report)
    metadata, texts["SKILL.md"] = validator.parse_metadata(texts["SKILL.md"])
    version = metadata.get("metadata", {}).get("version")
    if version is not None and version != document["version"]:
        raise PackageError("metadata.version 与 manifest 不一致")
    for name, text in texts.items():
        if Path(name).suffix.lower() in {".md", ".html", ".htm"}:
            validator.check_links(name, text, root, report, texts,
                                  prospective_targets=frozenset({validator.MANIFEST}))
    if report.io_failure:
        raise OSError("维护检查遇到 I/O 错误")
    if report.errors:
        raise PackageError("维护检查失败：" + json.dumps(report.errors, ensure_ascii=False))
    ensure_fresh(root, document)
    return document


def ensure_fresh(root: Path, manifest: dict, manifest_bytes: bytes | None = None) -> None:
    files = validator.inventory(root)
    expected = set(manifest["files"])
    if set(files) - {validator.MANIFEST} != expected:
        raise PackageError("源文件集合在校验后发生变化")
    for name, digest in manifest["files"].items():
        if hashlib.sha256(validator.safe_bytes(files[name], root)).hexdigest() != digest:
            raise PackageError(f"源文件在校验后发生变化：{name}")
    if manifest_bytes is not None and validator.safe_bytes(root / validator.MANIFEST, root) != manifest_bytes:
        raise PackageError("源 manifest 在校验后发生变化")


def refresh_manifest(root: Path) -> Path:
    root = validator.checked_root(root)
    destination = validator.guarded_path(root / validator.MANIFEST, root)
    # 更新已有文件必须先读；也用于防止维护期间覆盖别人的改动。
    previous = validator.safe_bytes(destination, root) if destination.exists() else None
    manifest = generate_manifest(root)
    content = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = root / (validator.MANIFEST + ".refresh-tmp")
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        current = validator.safe_bytes(destination, root) if destination.exists() else None
        if current != previous:
            raise PackageError("manifest 在维护时发生变化，拒绝覆盖")
        # 临时文件只在本命令中短暂存在，不属于发行资产。
        for name, digest in manifest["files"].items():
            if hashlib.sha256(validator.safe_bytes(root / name, root)).hexdigest() != digest:
                raise PackageError(f"维护期间源文件发生变化：{name}")
        validator.guarded_path(destination, root)
        os.replace(temporary, destination)
        created = False
    finally:
        if created:
            temporary.unlink()
    return destination


def package(root: Path, output: Path, label: str = "candidate", *, release_root: str = validator.SKILL_NAME) -> tuple[Path, Path]:
    if release_root != validator.SKILL_NAME:
        raise PackageError("本单 Skill 的发行根必须为 prd-assistant")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", label) or label.endswith("."):
        raise PackageError("label 仅允许安全的字母、数字、点、下划线和短横线")
    root = validator.checked_root(root)
    output = validator.checked_root(output)
    if output.is_relative_to(root):
        raise PackageError("输出目录必须已存在且位于 Skill 根外")
    if root.name != release_root:
        raise PackageError("发行工作副本的根目录名必须为 prd-assistant；普通校验不限制临时根名")
    report = validator.validate(root)
    if report.io_failure:
        raise OSError("源目录校验遇到 I/O 错误")
    if report.errors:
        raise PackageError("源目录未通过本地校验：" + json.dumps(report.errors, ensure_ascii=False))
    manifest = report.manifest
    if manifest is None:
        raise PackageError("缺少有效 manifest")
    manifest_bytes = validator.safe_bytes(root / validator.MANIFEST, root)
    if validator.parse_manifest(manifest_bytes.decode("utf-8-sig")) != manifest:
        raise PackageError("manifest 在校验后发生变化")
    filename = f"{release_root}-{manifest['version']}-{label}.zip"
    archive_path = output / filename
    sums_path = output / f"SHA256SUMS-{label}.txt"
    for destination in (archive_path, sums_path):
        if os.path.lexists(destination):
            raise FileExistsError(f"拒绝覆盖已有产物：{destination.name}")
        validator.guarded_path(destination, output)
    created: list[Path] = []
    try:
        # 先独占占位两份产物；若其中一个发生冲突，仅清理本次确实创建的文件。
        with archive_path.open("xb") as archive_stream:
            created.append(archive_path)
            with sums_path.open("xb") as sums_stream:
                created.append(sums_path)
                ensure_fresh(root, manifest, manifest_bytes)
                with zipfile.ZipFile(archive_stream, "w", compression=zipfile.ZIP_STORED) as archive:
                    for name in sorted(set(manifest["files"]) | {validator.MANIFEST}):
                        data = validator.safe_bytes(root / name, root)
                        expected = (hashlib.sha256(manifest_bytes).hexdigest() if name == validator.MANIFEST
                                    else manifest["files"][name])
                        if hashlib.sha256(data).hexdigest() != expected:
                            raise PackageError(f"打包时源文件发生变化：{name}")
                        info = zipfile.ZipInfo(f"{release_root}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                        info.create_system = 3
                        info.external_attr = 0o100644 << 16
                        info.compress_type = zipfile.ZIP_STORED
                        archive.writestr(info, data)
                archive_stream.flush()
                os.fsync(archive_stream.fileno())
                ensure_fresh(root, manifest, manifest_bytes)
                # 不解压、不执行包内代码：验证有序文件集合、唯一根、CRC 和每个 SHA256。
                with zipfile.ZipFile(archive_path, "r") as archive:
                    expected_names = [f"{release_root}/{name}" for name in sorted(set(manifest["files"]) | {validator.MANIFEST})]
                    if archive.namelist() != expected_names or archive.testzip() is not None:
                        raise PackageError("ZIP 文件集合或 CRC 校验失败")
                    for entry in archive.infolist():
                        name = entry.filename.removeprefix(release_root + "/")
                        validator.valid_relative(name)
                        if name == validator.MANIFEST:
                            if archive.read(entry) != manifest_bytes:
                                raise PackageError("ZIP manifest 校验失败")
                        elif hashlib.sha256(archive.read(entry)).hexdigest() != manifest["files"][name]:
                            raise PackageError(f"ZIP 文件哈希校验失败：{name}")
                digest = hashlib.sha256(validator.safe_bytes(archive_path, output)).hexdigest()
                sums_stream.write(f"{digest}  {filename}\n".encode("utf-8"))
                sums_stream.flush()
                os.fsync(sums_stream.fileno())
        if validator.safe_text(sums_path, output) != f"{hashlib.sha256(validator.safe_bytes(archive_path, output)).hexdigest()}  {filename}\n":
            raise PackageError("SHA256SUMS 产物校验失败")
        ensure_fresh(root, manifest, manifest_bytes)
        return archive_path, sums_path
    except BaseException:
        for path in reversed(created):
            path.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=validator.ROOT, help="单 Skill 工作副本根")
    parser.add_argument("--output", type=Path, help="必须已存在的根外目录（打包模式必填）")
    parser.add_argument("--label", default="candidate", help="候选产物标签，默认 candidate")
    parser.add_argument("--refresh-manifest", action="store_true", help="明确维护命令：读取并更新工作副本清单，不打包")
    args = parser.parse_args(argv)
    if args.refresh_manifest and (args.output is not None or args.label != "candidate"):
        parser.error("维护模式不能同时指定 --output/--label")
    if not args.refresh_manifest and args.output is None:
        parser.error("打包模式需要 --output DIRECTORY")
    try:
        if args.refresh_manifest:
            print(f"已更新工作副本清单：{refresh_manifest(args.root)}")
        else:
            archive, sums = package(args.root, args.output, args.label)
            print(f"已生成并校验：{archive}\n{sums}\n{validator.SCOPE}")
    except (validator.Invalid, UnicodeError, zipfile.BadZipFile) as exc:
        print(f"打包/维护失败：{exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"配置或 I/O 失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
