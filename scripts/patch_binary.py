#!/usr/bin/env python3
"""Apply a version-locked, exact-offset localization patch to AGY."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


TARGET = Path.home() / ".local" / "bin" / "agy"
LEGACY_BACKUP = TARGET.with_name(f"{TARGET.name}.zh-backup")
MANIFEST = Path(__file__).resolve().parent.parent / "i18n" / "binary-translations.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha512(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as handle:
        return json.load(handle)


def backup_path(manifest: dict) -> Path:
    version = manifest["_meta"]["agy_version"]
    return TARGET.with_name(f"{TARGET.name}.zh-backup-{version}")


def parse_version(path: Path) -> tuple[int, ...] | None:
    match = re.search(r"\.zh-backup-(\d+(?:\.\d+)*)", path.name)
    if not match:
        return None
    parts = []
    for chunk in match.group(1).split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def prune_old_backups(keep: int = 2) -> list[Path]:
    """Retain only the latest `keep` versioned backups and purge obsolete ones."""
    if not TARGET.parent.exists():
        return []
    versioned: list[tuple[tuple[int, ...], Path]] = []
    purged: list[Path] = []
    prefix = f"{TARGET.name}.zh-backup-"

    for candidate in TARGET.parent.iterdir():
        if candidate.name.startswith(prefix) and candidate.is_file():
            ver = parse_version(candidate)
            if ver is not None:
                versioned.append((ver, candidate))

    versioned.sort(key=lambda item: item[0])
    if len(versioned) > keep:
        to_delete = versioned[:-keep]
        for _, old_backup in to_delete:
            try:
                old_backup.unlink(missing_ok=True)
                purged.append(old_backup)
            except OSError:
                pass

    # Clean legacy non-versioned or broken backup artifacts
    legacy_patterns = [
        f"{TARGET.name}.zh-backup",
        f"{TARGET.name}.zh-1114-backup",
        f"{TARGET.name}.zh-broken-*",
    ]
    for pattern in legacy_patterns:
        for extra in TARGET.parent.glob(pattern):
            if extra.is_file():
                try:
                    extra.unlink(missing_ok=True)
                    purged.append(extra)
                except OSError:
                    pass

    return purged


def signature_details(path: Path) -> str:
    details = run("codesign", "-dv", "--verbose=4", str(path), check=False)
    return details.stdout + details.stderr


def validate_source(path: Path, manifest: dict) -> None:
    actual_platform = f"{sys.platform}-{platform.machine()}"
    if actual_platform != manifest["_meta"]["platform"]:
        raise RuntimeError(
            f"平台不匹配：检测到 {actual_platform}，仅支持 {manifest['_meta']['platform']}"
        )
    expected_hash = manifest["_meta"]["sha256"]
    actual_hash = sha256(path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"版本锁校验失败：{path} 的 SHA-256 为 {actual_hash}，期望 {expected_hash}"
        )
    version = run(str(path), "--version").stdout.strip()
    if version != manifest["_meta"]["agy_version"]:
        raise RuntimeError(f"版本不匹配：检测到 {version}，仅支持 {manifest['_meta']['agy_version']}")
    run("codesign", "--verify", "--deep", "--strict", str(path))
    expected_authority = manifest["_meta"]["upstream"]["signing_authority"]
    if expected_authority not in signature_details(path):
        raise RuntimeError(f"签名来源不匹配：{path} 不是清单声明的 Google 原签名文件")


def download_official_source(manifest: dict, work_dir: Path) -> Path:
    upstream = manifest["_meta"]["upstream"]
    url = upstream["url"]
    if not url.startswith("https://"):
        raise RuntimeError("官方发布地址必须使用 HTTPS")

    archive = work_dir / "agy.tar.gz"
    try:
        run(
            "curl",
            "-fsSL",
            "--proto",
            "=https",
            "--tlsv1.2",
            "--output",
            str(archive),
            url,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise RuntimeError(f"下载官方 AGY 失败：{detail}") from error

    actual_archive_hash = sha512(archive)
    expected_archive_hash = upstream["archive_sha512"]
    if actual_archive_hash != expected_archive_hash:
        raise RuntimeError(
            f"官方归档 SHA-512 校验失败：读取到 {actual_archive_hash}，期望 {expected_archive_hash}"
        )

    member_name = upstream["archive_member"]
    source = work_dir / "agy.official"
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            member = bundle.getmember(member_name)
            if not member.isfile():
                raise RuntimeError(f"官方归档成员不是普通文件：{member_name}")
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise RuntimeError(f"无法读取官方归档成员：{member_name}")
            with extracted, source.open("wb") as output:
                shutil.copyfileobj(extracted, output)
    except (KeyError, OSError, tarfile.TarError) as error:
        raise RuntimeError(f"解包官方 AGY 失败：{error}") from error

    source.chmod(0o755)
    validate_source(source, manifest)
    return source


def patch_bytes(source: Path, destination: Path, manifest: dict) -> None:
    data = bytearray(source.read_bytes())
    for item in manifest["patches"]:
        offset = int(item["offset"], 0)
        original = item["en"].encode("utf-8")
        translated = item["zh"].encode("utf-8")
        if len(translated) > len(original):
            raise RuntimeError(f"翻译过长：{item['context']} ({len(translated)} > {len(original)})")
        actual = bytes(data[offset : offset + len(original)])
        if actual != original:
            raise RuntimeError(
                f"偏移校验失败 {item['offset']} ({item['context']})："
                f"读取到 {actual!r}，期望 {original!r}"
            )
        data[offset : offset + len(original)] = translated.ljust(len(original), b" ")
    destination.write_bytes(data)
    destination.chmod(0o755)


def verify_patched(path: Path, manifest: dict) -> None:
    run("codesign", "--verify", "--deep", "--strict", str(path))
    version = run(str(path), "--version").stdout.strip()
    if version != manifest["_meta"]["agy_version"]:
        raise RuntimeError(f"补丁后版本冒烟失败：{version!r}")
    help_result = run(str(path), "--help")
    help_text = help_result.stdout + help_result.stderr
    if "可用子命令：" not in help_text:
        raise RuntimeError("补丁后帮助文本未出现中文标题")
    data = path.read_bytes()
    for item in manifest["patches"]:
        offset = int(item["offset"], 0)
        expected = item["zh"].encode("utf-8")
        if data[offset : offset + len(expected)] != expected:
            raise RuntimeError(f"补丁验收失败：{item['context']}")


def select_existing_source(manifest: dict) -> Path | None:
    """Choose a verified pristine source without overwriting any older backup."""
    expected_hash = manifest["_meta"]["sha256"]
    if TARGET.exists() and sha256(TARGET) == expected_hash:
        return TARGET

    if TARGET.exists():
        signature = run("codesign", "--verify", "--deep", "--strict", str(TARGET), check=False)
        if signature.returncode != 0:
            raise RuntimeError("当前 agy 签名无效；拒绝自动覆盖，请先显式运行 --restore")

        version = run(str(TARGET), "--version").stdout.strip()
        if version != manifest["_meta"]["agy_version"]:
            raise RuntimeError(
                f"检测到新的官方或未知 agy 版本 {version!r}；拒绝使用旧备份覆盖，请先更新偏移表"
            )
        if "Signature=adhoc" not in signature_details(TARGET):
            raise RuntimeError(
                "当前 agy 是同版本但 SHA-256 未识别的正式签名文件；拒绝使用旧备份覆盖"
            )

    current_backup = backup_path(manifest)
    for candidate in (current_backup, LEGACY_BACKUP):
        if candidate.exists() and sha256(candidate) == expected_hash:
            validate_source(candidate, manifest)
            return candidate
    return None


def apply_patch(dry_run: bool) -> None:
    manifest = load_manifest()
    with tempfile.TemporaryDirectory(prefix="agy-zh-") as temp_dir:
        work_dir = Path(temp_dir)
        source = select_existing_source(manifest)
        downloaded = source is None
        if downloaded:
            source = download_official_source(manifest, work_dir)
        else:
            validate_source(source, manifest)

        if dry_run:
            staged = work_dir / "agy.dry-run"
            patch_bytes(source, staged, manifest)
            origin = "（已校验官方下载原包）" if downloaded else ""
            print(f"DRY-RUN PASS：{len(manifest['patches'])} 条精确偏移全部匹配{origin}")
            return

        TARGET.parent.mkdir(parents=True, exist_ok=True)
        current_backup = backup_path(manifest)
        if not current_backup.exists():
            file_descriptor, backup_name = tempfile.mkstemp(
                prefix=f"{current_backup.name}.staged-", dir=TARGET.parent
            )
            os.close(file_descriptor)
            staged_backup = Path(backup_name)
            try:
                shutil.copy2(source, staged_backup)
                validate_source(staged_backup, manifest)
                os.replace(staged_backup, current_backup)
            finally:
                staged_backup.unlink(missing_ok=True)
        validate_source(current_backup, manifest)
        pruned = prune_old_backups(keep=2)
        if pruned:
            purged_names = ", ".join(p.name for p in pruned)
            print(f"CLEANUP PASS：已清理 {len(pruned)} 个旧备份以节省空间（仅保留最新 2 份）：{purged_names}")

        file_descriptor, staged_name = tempfile.mkstemp(prefix="agy.zh-staged-", dir=TARGET.parent)
        os.close(file_descriptor)
        staged = Path(staged_name)
        try:
            patch_bytes(current_backup, staged, manifest)
            run("codesign", "--force", "--sign", "-", "--options", "runtime", str(staged))
            verify_patched(staged, manifest)
            os.replace(staged, TARGET)
        finally:
            staged.unlink(missing_ok=True)
    print(f"PATCH PASS：已应用 {len(manifest['patches'])} 条精确汉化并完成 ad-hoc 签名")


def restore() -> None:
    manifest = load_manifest()
    current_backup = backup_path(manifest)
    validate_source(current_backup, manifest)
    file_descriptor, staged_name = tempfile.mkstemp(prefix="agy.zh-restore-", dir=TARGET.parent)
    os.close(file_descriptor)
    staged = Path(staged_name)
    try:
        shutil.copy2(current_backup, staged)
        os.replace(staged, TARGET)
    finally:
        staged.unlink(missing_ok=True)
    validate_source(TARGET, manifest)
    print("RESTORE PASS：已恢复 Google 原签名 agy")


def status() -> None:
    manifest = load_manifest()
    expected_hash = manifest["_meta"]["sha256"]
    if not TARGET.exists():
        raise RuntimeError(f"找不到 {TARGET}")
    current_hash = sha256(TARGET)
    if current_hash == expected_hash:
        validate_source(TARGET, manifest)
        print("状态：官方原版（Google 签名）")
        return
    verification = run("codesign", "--verify", "--deep", "--strict", str(TARGET), check=False)
    if verification.returncode != 0:
        print("状态：签名无效，agy 会被 macOS 杀死")
        sys.exit(1)
    try:
        verify_patched(TARGET, manifest)
    except RuntimeError as error:
        print(f"状态：未知的已签名二进制（{error}）")
        sys.exit(1)
    print("状态：精确偏移汉化版（ad-hoc hardened runtime 签名）")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--restore", action="store_true")
    group.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore()
    elif args.status:
        status()
    else:
        apply_patch(args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(1)
