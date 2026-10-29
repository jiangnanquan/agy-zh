#!/usr/bin/env python3
"""Prepare a fail-closed AGY localization manifest for the latest release.

The script reuses translations only when the old literal is still surrounded by
an unchanged, unique binary context. It never patches by occurrence rank or by
global replacement. New/changed built-in Skills and unresolved binary literals
are reduced to a small review report so a human can decide whether AI is needed.
"""

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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import patch_binary


MANIFEST = ROOT / "i18n" / "binary-translations.json"
SKILL_MANIFEST = ROOT / "i18n" / "skill-translations.json"
OUTPUT_ROOT = ROOT / ".upgrade"
RELEASE_MANIFEST_URL = (
    "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/"
    "manifests/darwin_arm64.json"
)
SKILL_ROOT = Path.home() / ".gemini" / "antigravity-cli" / "builtin"
SIGNING_AUTHORITY = "Authority=Developer ID Application: Google LLC (EQHXZ8M8AV)"
CONTEXT_WIDTHS = (128, 96, 64, 48, 32, 24, 16)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_release() -> dict[str, str]:
    result = run(
        "curl",
        "-fsSL",
        "--proto",
        "=https",
        "--tlsv1.2",
        RELEASE_MANIFEST_URL,
    )
    release = json.loads(result.stdout)
    for field in ("version", "url", "sha512"):
        if not isinstance(release.get(field), str) or not release[field]:
            raise RuntimeError(f"官方发布清单缺少 {field}")
    if not release["url"].startswith("https://"):
        raise RuntimeError("官方发布包地址必须使用 HTTPS")
    return release


def validate_google_binary(path: Path, version: str) -> None:
    actual_platform = f"{sys.platform}-{platform.machine()}"
    if actual_platform != "darwin-arm64":
        raise RuntimeError(f"平台不匹配：检测到 {actual_platform}，仅支持 darwin-arm64")
    actual_version = run(str(path), "--version").stdout.strip()
    if actual_version != version:
        raise RuntimeError(f"版本不匹配：检测到 {actual_version!r}，期望 {version!r}")
    run("codesign", "--verify", "--deep", "--strict", str(path))
    if SIGNING_AUTHORITY not in patch_binary.signature_details(path):
        raise RuntimeError(f"{path} 不是 Google Developer ID 原签名文件")


def download_release(release: dict[str, str], work_dir: Path) -> Path:
    archive = work_dir / "agy.tar.gz"
    run(
        "curl",
        "-fsSL",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--output",
        str(archive),
        release["url"],
    )
    actual_sha512 = digest(archive, "sha512")
    if actual_sha512 != release["sha512"]:
        raise RuntimeError(
            f"官方归档 SHA-512 不匹配：读取到 {actual_sha512}，期望 {release['sha512']}"
        )

    source = work_dir / "agy.official"
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.getmember("antigravity")
            if not member.isfile():
                raise RuntimeError("官方归档中的 antigravity 不是普通文件")
            extracted = bundle.extractfile(member)
            if extracted is None:
                raise RuntimeError("无法读取官方归档中的 antigravity")
            with extracted, source.open("wb") as output:
                shutil.copyfileobj(extracted, output)
    except (KeyError, OSError, tarfile.TarError) as error:
        raise RuntimeError(f"解包官方 AGY 失败：{error}") from error
    source.chmod(0o755)
    validate_google_binary(source, release["version"])
    return source


def unique_offset(data: bytes, pattern: bytes) -> int | None:
    first = data.find(pattern)
    if first < 0:
        return None
    if data.find(pattern, first + 1) >= 0:
        return None
    return first


def relocate_patch(
    item: dict[str, str], old_data: bytes, new_data: bytes
) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    old_offset = int(item["offset"], 0)
    needle = item["en"].encode("utf-8")
    if old_data[old_offset : old_offset + len(needle)] != needle:
        return None, {
            "context": item["context"],
            "en": item["en"],
            "reason": "旧清单偏移与旧原件不匹配",
        }

    candidates: set[int] = set()
    methods: set[str] = set()
    for width in CONTEXT_WIDTHS:
        if old_offset < width:
            continue
        left = old_data[old_offset - width : old_offset]
        right_start = old_offset + len(needle)
        right = old_data[right_start : right_start + width]
        for method, pattern, adjustment in (
            (f"双侧上下文 {width}B", left + needle + right, width),
            (f"左侧上下文 {width}B", left + needle, width),
            (f"右侧上下文 {width}B", needle + right, 0),
        ):
            located = unique_offset(new_data, pattern)
            if located is not None:
                candidates.add(located + adjustment)
                methods.add(method)
        if len(candidates) == 1:
            break

    if len(candidates) != 1:
        count = 0
        cursor = 0
        while count <= 2:
            located = new_data.find(needle, cursor)
            if located < 0:
                break
            count += 1
            cursor = located + 1
        reason = "新原件中原文消失" if count == 0 else "无法用唯一上下文确认新偏移"
        return None, {
            "context": item["context"],
            "en": item["en"],
            "reason": reason,
            "occurrences": str(count) if count <= 2 else ">2",
        }

    new_offset = candidates.pop()
    if new_data[new_offset : new_offset + len(needle)] != needle:
        raise RuntimeError(f"内部错误：{item['context']} 的重定位结果未命中原文")
    relocated = dict(item)
    relocated["offset"] = f"0x{new_offset:08x}"
    return relocated, {
        "context": item["context"],
        "old_offset": item["offset"],
        "new_offset": relocated["offset"],
        "method": " / ".join(sorted(methods)),
    }


def frontmatter_description(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    frontmatter = text[4:end]
    lines = frontmatter.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("description:"):
            continue
        captured = [line]
        if re.fullmatch(r"description:\s*[>|][+-]?\s*", line):
            for continuation in lines[index + 1 :]:
                if continuation.startswith((" ", "\t")) or not continuation.strip():
                    captured.append(continuation)
                else:
                    break
        return "\n".join(captured)
    return None


def discover_skill_review(
    skill_root: Path, skill_manifest: dict[str, Any]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    known = {item["path"]: item for item in skill_manifest["patches"]}
    new_items: list[dict[str, str]] = []
    changed_items: list[dict[str, str]] = []
    skills_dir = skill_root / "skills"
    if not skills_dir.is_dir():
        return new_items, changed_items

    for path in sorted(skills_dir.glob("*/SKILL.md")):
        relative = path.relative_to(skill_root).as_posix()
        description = frontmatter_description(path)
        if description is None:
            continue
        if relative not in known:
            new_items.append(
                {
                    "path": relative,
                    "en": description,
                    "context": f"/{path.parent.name} 右侧说明",
                }
            )
            continue
        item = known[relative]
        text = path.read_text(encoding="utf-8", errors="replace")
        if item["en"] not in text and item["zh"] not in text:
            changed_items.append(
                {
                    "path": relative,
                    "previous_en": item["en"],
                    "current": description,
                    "context": item["context"],
                }
            )
    return new_items, changed_items


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        temp_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def write_ai_packet(path: Path, report: dict[str, Any]) -> None:
    review = {
        "target_version": report["target_version"],
        "unresolved_binary": report["unresolved_binary"],
        "new_skills": report["new_skills"],
        "changed_skills": report["changed_skills"],
    }
    path.write_text(
        "# AGY 汉化最小 AI 接入包\n\n"
        "只处理下列差异；先读仓库 AGENTS.md 和 AI_TRANSLATION_GUIDE.md。"
        "不得复用旧偏移、全局替换或跳过真实 TUI 验收。\n\n"
        "```json\n"
        + json.dumps(review, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )


def build_proposal(
    old_manifest: dict[str, Any], old_source: Path, new_source: Path, release: dict[str, str]
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    old_data = old_source.read_bytes()
    new_data = new_source.read_bytes()
    inherited: list[dict[str, str]] = []
    evidence: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for item in old_manifest["patches"]:
        relocated, detail = relocate_patch(item, old_data, new_data)
        if relocated is None:
            assert detail is not None
            unresolved.append(detail)
        else:
            inherited.append(relocated)
            assert detail is not None
            evidence.append(detail)

    offsets = [int(item["offset"], 0) for item in inherited]
    if len(offsets) != len(set(offsets)):
        raise RuntimeError("重定位后出现重复偏移；拒绝生成清单")

    proposal = {
        "_meta": {
            "description": f"agy {release['version']} macOS arm64 精确偏移汉化表",
            "agy_version": release["version"],
            "platform": "darwin-arm64",
            "sha256": digest(new_source, "sha256"),
            "signing": old_manifest["_meta"]["signing"],
            "upstream": {
                "url": release["url"],
                "archive_sha512": release["sha512"],
                "archive_member": "antigravity",
                "signing_authority": SIGNING_AUTHORITY,
            },
        },
        "patches": inherited,
    }
    return proposal, evidence, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-binary", type=Path, help="已验证来源的 Google 原签名新版本")
    parser.add_argument("--apply", action="store_true", help="零待审项时更新正式清单")
    parser.add_argument("--ai-packet", action="store_true", help="为待审项生成最小 AI 接入包")
    parser.add_argument("--non-interactive", action="store_true", help="不询问；适合静默检查")
    args = parser.parse_args()

    old_manifest = load_json(MANIFEST)
    old_version = old_manifest["_meta"]["agy_version"]
    release = fetch_release()
    is_upgrade = release["version"] != old_version
    if is_upgrade:
        old_source = patch_binary.backup_path(old_manifest)
        patch_binary.validate_source(old_source, old_manifest)
        with tempfile.TemporaryDirectory(prefix="agy-zh-upgrade-") as temp_dir:
            if args.new_binary is not None:
                new_source = args.new_binary.expanduser().resolve()
                validate_google_binary(new_source, release["version"])
            else:
                try:
                    validate_google_binary(patch_binary.TARGET, release["version"])
                    new_source = patch_binary.TARGET
                except (OSError, RuntimeError, subprocess.CalledProcessError):
                    new_source = download_release(release, Path(temp_dir))
            # AGY unpacks bundled Skills during normal startup. --help exercises
            # that initialization without opening an interactive conversation.
            run(str(new_source), "--help")
            proposal, evidence, unresolved = build_proposal(
                old_manifest, old_source, new_source, release
            )
    else:
        proposal = old_manifest
        evidence = []
        unresolved = []

    skill_manifest = load_json(SKILL_MANIFEST)
    new_skills, changed_skills = discover_skill_review(SKILL_ROOT, skill_manifest)
    version_dir = OUTPUT_ROOT / release["version"]
    proposal_path = version_dir / "binary-translations.json"
    report_path = version_dir / "report.json"
    packet_path = version_dir / "AI_REVIEW.md"
    atomic_json(proposal_path, proposal)
    report = {
        "from_version": old_version,
        "target_version": release["version"],
        "inherited_binary_count": len(proposal["patches"]) if is_upgrade else 0,
        "inherited_evidence": evidence,
        "unresolved_binary": unresolved,
        "new_skills": new_skills,
        "changed_skills": changed_skills,
        "proposal": str(proposal_path.relative_to(ROOT)),
        "requires_real_tui_review": True,
    }
    atomic_json(report_path, report)
    review_count = len(unresolved) + len(new_skills) + len(changed_skills)

    if review_count:
        print(
            f"发现 {review_count} 个待审项：二进制 {len(unresolved)}、"
            f"新增 Skill {len(new_skills)}、变更 Skill {len(changed_skills)}。"
        )
        print(f"短报告：{report_path}")
        make_packet = args.ai_packet
        if not args.non_interactive and not make_packet:
            answer = input("是否生成最小 AI 接入包？[y/N] ").strip().lower()
            make_packet = answer in {"y", "yes"}
        if make_packet:
            write_ai_packet(packet_path, report)
            print(f"AI 接入包：{packet_path}")
        if args.apply:
            print("仍有待审项：拒绝自动更新正式清单", file=sys.stderr)
        return 2

    if not is_upgrade:
        print(f"无需升级：清单已是官方最新版 {old_version}，内置 Skill 也无待审项")
        return 0

    if args.apply:
        atomic_json(MANIFEST, proposal)
        print(
            f"APPLY PASS：{len(proposal['patches'])} 条旧译文已安全继承到 "
            f"{release['version']}；仍需真实 TUI 验收"
        )
        return 0

    print(
        f"PREPARE PASS：{len(proposal['patches'])} 条旧译文可零 AI 继承到 "
        f"{release['version']}；提案位于 {proposal_path}"
    )
    if not args.non_interactive:
        answer = input("是否更新正式二进制清单？[y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            atomic_json(MANIFEST, proposal)
            print("APPLY PASS：正式清单已更新；仍需运行完整测试和真实 TUI 验收")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1)
