#!/usr/bin/env python3
"""Patch only the descriptions of AGY's extracted built-in skills."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile


ROOT = Path.home() / ".gemini" / "antigravity-cli" / "builtin"
MANIFEST = Path(__file__).resolve().parent.parent / "i18n" / "skill-translations.json"
BACKUP_SUFFIX = ".agy-zh.orig"
LEGACY_BACKUP_SUFFIX = ".antigravity-zh.orig"


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write(path: Path, content: str) -> None:
    descriptor, staged_name = tempfile.mkstemp(prefix=f"{path.name}.zh-", dir=path.parent)
    staged = Path(staged_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        staged.chmod(path.stat().st_mode)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def is_already_applied(source: str, item: dict) -> bool:
    if source.count(item["zh"]) == 1 and item["en"] not in source:
        return True
    norm_source = "\n".join(line.rstrip() for line in source.splitlines())
    norm_zh = "\n".join(line.rstrip() for line in item["zh"].splitlines())
    return norm_zh in norm_source and item["en"] not in source


def apply() -> None:
    changed = 0
    for item in load_manifest()["patches"]:
        target = ROOT / item["path"]
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        source = target.read_text(encoding="utf-8")
        if is_already_applied(source, item):
            if source.count(item["zh"]) != 1:
                norm_zh = "\n".join(line.rstrip() for line in item["zh"].splitlines())
                norm_source = "\n".join(line.rstrip() for line in source.splitlines())
                if norm_zh in norm_source:
                    new_source = norm_source.replace(norm_zh, item["zh"], 1)
                    atomic_write(target, new_source + "\n" if not new_source.endswith("\n") else new_source)
                    changed += 1
            continue
        if source.count(item["en"]) != 1:
            raise RuntimeError(f"{item['context']}：英文原文不是唯一匹配")
        # AGY upgrades may refresh the full Skill body while keeping the same
        # description. In that case refresh the backup before applying this
        # version's patch, so --restore never writes an older Skill body back.
        if not backup.exists() or backup.read_text(encoding="utf-8") != source:
            backup.write_text(source, encoding="utf-8", newline="")
            backup.chmod(target.stat().st_mode)
        atomic_write(target, source.replace(item["en"], item["zh"], 1))
        changed += 1
    check()
    print(f"PATCH PASS：已汉化 {changed} 个内置 Skill 说明")


def check() -> None:
    for item in load_manifest()["patches"]:
        source = (ROOT / item["path"]).read_text(encoding="utf-8")
        if not is_already_applied(source, item):
            raise RuntimeError(f"{item['context']}：汉化未完整应用")
    print("状态：内置 Skill 说明已汉化")


def restore() -> None:
    for item in load_manifest()["patches"]:
        target = ROOT / item["path"]
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        if not backup.exists():
            backup = target.with_name(target.name + LEGACY_BACKUP_SUFFIX)
        if not backup.exists():
            raise RuntimeError(f"找不到备份：{backup}")
        atomic_write(target, backup.read_text(encoding="utf-8"))
    print("RESTORE PASS：已恢复内置 Skill 原始说明")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    elif args.restore:
        restore()
    else:
        apply()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, json.JSONDecodeError) as error:
        print(f"错误：{error}", file=os.sys.stderr)
        raise SystemExit(1)
