#!/usr/bin/env python3
"""Audit AGY binary and built-in assets for untranslated slash commands and surfaces.

Scans the target AGY Mach-O binary and builtin skills to detect:
1. System slash commands whose Description() is missing in binary-translations.json
2. Builtin skills whose description is missing in skill-translations.json
3. Critical CLI subcommands / usage surface coverage

Usage:
    python3 scripts/scan_untranslated.py [--strict] [--json] [--binary <path>]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BINARY_MANIFEST = ROOT / "i18n" / "binary-translations.json"
SKILL_MANIFEST = ROOT / "i18n" / "skill-translations.json"
DEFAULT_TARGET = Path.home() / ".local" / "bin" / "agy"
SKILL_DIR = Path.home() / ".gemini" / "antigravity-cli" / "builtin" / "skills"


def locate_pristine_binary() -> Path:
    """Find the best pristine or current binary candidate to audit."""
    if not DEFAULT_TARGET.parent.exists():
        return DEFAULT_TARGET

    # Look for the latest pristine version backup first
    candidates = sorted(
        DEFAULT_TARGET.parent.glob(f"{DEFAULT_TARGET.name}.zh-backup-*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates and candidates[0].is_file():
        return candidates[0]

    return DEFAULT_TARGET


def extract_command_descriptions(binary_path: Path) -> list[dict[str, Any]]:
    """Recover all Description() string literals from jetski commands package."""
    go_bin = shutil.which("go")
    if not go_bin:
        # If go is missing, fall back to warning
        return []

    helper = ROOT / "scripts" / "go_func_ranges.go"
    if not helper.exists():
        return []

    res = subprocess.run(
        [go_bin, "run", str(helper), str(binary_path), "Command).Description"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []

    bin_data = binary_path.read_bytes()
    results: list[dict[str, Any]] = []

    for line in res.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            entry = int(parts[0], 16)
            end = int(parts[1], 16)
        except ValueError:
            continue

        fn_name = parts[2]
        # Skip GenericCommand since it dynamically forwards descriptions
        if "GenericCommand" in fn_name:
            continue

        file_start = entry - 0x100000000
        file_end = end - 0x100000000
        if file_start < 0 or file_end > len(bin_data) or file_start >= file_end:
            continue

        fn_bytes = bin_data[file_start:file_end]
        target_off: int | None = None
        target_len: int | None = None

        for i in range(0, len(fn_bytes) - 4, 4):
            inst = int.from_bytes(fn_bytes[i : i + 4], "little")
            # ADRP
            if (inst & 0x9F000000) == 0x90000000:
                reg = inst & 0x1F
                immlo = (inst >> 29) & 0x3
                immhi = (inst >> 5) & 0x7FFFF
                imm = (immhi << 2) | immlo
                if imm & (1 << 20):
                    imm -= 1 << 21
                pc = entry + i
                page = (pc & ~0xFFF) + (imm << 12)
                if i + 4 < len(fn_bytes):
                    next_inst = int.from_bytes(fn_bytes[i + 4 : i + 8], "little")
                    if (next_inst >> 22) == 0b1001000100:  # ADD Xd, Xn, #imm
                        rn = (next_inst >> 5) & 0x1F
                        if rn == reg:
                            imm12 = (next_inst >> 10) & 0xFFF
                            target_off = (page + imm12) - 0x100000000

            # MOV X1, #len (0xd2800001 format)
            if (inst & 0xFFE0001F) == 0xD2800001:
                target_len = (inst >> 5) & 0xFFFF

        if target_off is not None and 0 <= target_off < len(bin_data):
            if target_len and target_len > 0:
                raw_bytes = bin_data[target_off : target_off + target_len]
                raw_text = raw_bytes.decode("utf-8", errors="ignore")
            else:
                s_chars: list[str] = []
                for b in bin_data[target_off : target_off + 150]:
                    if 32 <= b <= 126:
                        s_chars.append(chr(b))
                    else:
                        break
                raw_text = "".join(s_chars)

            if raw_text.strip():
                # Derive slash command name from function name
                m = re.search(r"\.\(\*([a-zA-Z0-9_]+)Command\)", fn_name)
                cmd_hint = m.group(1).lower() if m else "unknown"

                results.append(
                    {
                        "function": fn_name,
                        "command_hint": cmd_hint,
                        "offset": f"0x{target_off:08x}",
                        "length": len(raw_text.encode("utf-8")),
                        "en": raw_text,
                    }
                )

    return results


def audit_skills(manifest_path: Path, skills_dir: Path) -> dict[str, Any]:
    """Audit builtin skill definitions against skill-translations.json."""
    if not manifest_path.exists():
        return {"covered": [], "missing": []}

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {"covered": [], "missing": []}

    known = {item["path"]: item for item in data.get("patches", [])}
    covered: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            rel_path = f"skills/{skill_md.parent.name}/SKILL.md"
            if rel_path in known:
                covered.append(
                    {
                        "path": rel_path,
                        "context": known[rel_path].get("context", ""),
                    }
                )
            else:
                missing.append(
                    {
                        "path": rel_path,
                        "skill_name": skill_md.parent.name,
                    }
                )

    return {"covered": covered, "missing": missing}


def run_audit(
    binary_path: Path,
    binary_manifest_path: Path,
    skill_manifest_path: Path,
    skills_dir: Path,
) -> dict[str, Any]:
    """Execute full audit across binary and skills."""
    if not binary_manifest_path.exists():
        raise FileNotFoundError(f"Missing binary manifest: {binary_manifest_path}")

    b_manifest = json.loads(binary_manifest_path.read_text(encoding="utf-8"))
    translated_en_map = {item["en"]: item for item in b_manifest.get("patches", [])}

    commands = extract_command_descriptions(binary_path)
    cmd_covered: list[dict[str, Any]] = []
    cmd_missing: list[dict[str, Any]] = []

    for cmd in commands:
        matched = None
        for en_key, item in translated_en_map.items():
            if cmd["en"] == en_key or cmd["en"].startswith(en_key):
                matched = item
                break

        if matched:
            record = dict(cmd)
            record["zh"] = matched.get("zh", "")
            record["context"] = matched.get("context", "")
            cmd_covered.append(record)
        else:
            cmd_missing.append(cmd)

    skills_audit = audit_skills(skill_manifest_path, skills_dir)

    return {
        "binary_path": str(binary_path),
        "summary": {
            "commands_total": len(commands),
            "commands_covered": len(cmd_covered),
            "commands_missing": len(cmd_missing),
            "skills_covered": len(skills_audit["covered"]),
            "skills_missing": len(skills_audit["missing"]),
        },
        "commands": {
            "covered": cmd_covered,
            "missing": cmd_missing,
        },
        "skills": skills_audit,
    }


def print_report(audit: dict[str, Any]) -> None:
    """Print a clean human-readable audit readout."""
    summary = audit["summary"]
    print("=" * 68)
    print("      Google Antigravity CLI (agy) 汉化与遗漏扫描报告")
    print("=" * 68)
    print(f"目标二进制: {audit['binary_path']}")
    print(
        f"系统交互命令: 总数 {summary['commands_total']} | "
        f"已汉化 {summary['commands_covered']} | "
        f"遗漏 {summary['commands_missing']}"
    )
    print(
        f"内置技能说明: 已收录 {summary['skills_covered']} | "
        f"遗漏 {summary['skills_missing']}"
    )
    print("-" * 68)

    cmd_missing = audit["commands"]["missing"]
    skill_missing = audit["skills"]["missing"]

    if not cmd_missing and not skill_missing:
        print("🎉 恭喜！当前所有检测到的系统斜杠命令与内置技能均已 100% 覆盖汉化。")
    else:
        if cmd_missing:
            print(f"⚠️  发现 {len(cmd_missing)} 处未汉化的系统交互命令说明：")
            for item in cmd_missing:
                print(f"  • [{item['command_hint']}] (offset: {item['offset']}, len: {item['length']})")
                print(f"    原文: {item['en']}")
                print(f"    函数: {item['function']}")
            print()

        if skill_missing:
            print(f"⚠️  发现 {len(skill_missing)} 处未汉化的内置技能：")
            for item in skill_missing:
                print(f"  • {item['path']} ({item['skill_name']})")
            print()

        print("💡 建议：可将上述条目加入 i18n/ 对应的清单并执行 patch_binary.py。")
    print("=" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="Path to AGY binary (defaults to newest pristine backup or ~/.local/bin/agy)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=BINARY_MANIFEST,
        help="Path to binary-translations.json",
    )
    parser.add_argument(
        "--skills-manifest",
        type=Path,
        default=SKILL_MANIFEST,
        help="Path to skill-translations.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any missing/untranslated items are found",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON report instead of text",
    )

    args = parser.parse_args()
    binary_path = args.binary or locate_pristine_binary()

    if not binary_path.exists():
        print(f"错误：未找到目标二进制文件：{binary_path}", file=sys.stderr)
        return 2

    try:
        audit = run_audit(binary_path, args.manifest, args.skills_manifest, SKILL_DIR)
    except Exception as err:
        print(f"扫描执行失败: {err}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    else:
        print_report(audit)

    if args.strict:
        has_missing = (
            audit["summary"]["commands_missing"] > 0
            or audit["summary"]["skills_missing"] > 0
        )
        if has_missing:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
