---
name: q汉化agy
description: Google Antigravity CLI (agy) 界面汉化（简体中文）。精确偏移安全打补丁 → ad-hoc 代码重签 → 内置技能说明汉化 → 完整冒烟验收。支持官方更新后低 token 自动增量重定位升级与一键回滚。适用场景：「汉化 agy」「汉化 antigravity」「更新 agy 汉化」「agy 汉化失效」「检查 agy 汉化状态」「还原 agy 官方英文」。只汉化 UI 展示文本，不碰命令名、模型名与执行逻辑。
---

# Antigravity CLI 汉化（q汉化agy）

为 Google Antigravity CLI（`agy`，Mach-O arm64）提供终端 TUI 界面简体中文汉化。
**核心原则：只做 UI 说明文本汉化，不碰功能逻辑、命令名与配置键值。**

---

## 快速开始（一键命令）

```bash
cd /Users/jnq/Dev/Private/Antigravity-zh

# 1. 首次安装 / 完整重建汉化
bash scripts/install.sh

# 2. 官方升级后低 token 自动增量重定位升级
bash scripts/auto_update.sh
```

- `scripts/install.sh` 自动按序执行：确认 HUD 原版状态 → 预检版本与精确偏移 → 应用二进制补丁并重签 → 应用内置 Skill 说明汉化 → 8 步完整冒烟测试。
- `scripts/auto_update.sh` 从官方在线清单检查新版本，通过唯一上下文自动继承历史译文并重定位偏移；若存在歧义或新增项，会退出码 `2` 暂停并生成最小差异报告包。

---

## 状态检查与冒烟验收

```bash
cd /Users/jnq/Dev/Private/Antigravity-zh

# 全量 8 项自动化冒烟检查（签名、版本、备份、帮助文本、HUD等）
bash scripts/smoke_test.sh

# 查看当前二进制打补丁与签名状态
bash scripts/patch_binary.sh --status

# 查看内置 Skill 说明汉化状态
bash scripts/patch_skill_descriptions.sh --check

# 确认 HUD 保持原版（状态栏）
bash scripts/patch_hud.sh --check-original
```

---

## 手动分步流程（排查与调试）

在需要逐步定位问题时，可按以下步骤手动执行：

### 1. 确认 HUD 保持原版
```bash
bash scripts/patch_hud.sh --check-original
```

### 2. 二进制安全预检（Dry-Run）
```bash
bash scripts/patch_binary.sh --dry-run
```
> 必须确保全部偏移与原文匹配。如报错版本不一致或哈希不符，必须停止，严禁强制跳过。

### 3. 应用二进制汉化
```bash
bash scripts/patch_binary.sh
```
从官方原包或备份核验 SHA-256，写入精确偏移补丁，并执行 macOS ad-hoc hardened runtime 代码重签名。备份自动留存于 `~/.local/bin/agy.zh-backup-<version>`。

### 4. 应用内置 Skill 说明汉化
```bash
bash scripts/patch_skill_descriptions.sh
```
仅替换解包至 `~/.gemini/antigravity-cli/builtin/skills/*/SKILL.md` 的 YAML `description`。

### 5. 验收
```bash
bash scripts/smoke_test.sh
agy --version
```
在终端实际启动 `agy`，输入 `/` 验证菜单首屏、末屏及底部快捷键。

---

## 官方升级后增量重定位流程

当 Google 官方发布新版 `agy` 时：

1. **自动升级尝试**：
   ```bash
   bash scripts/auto_update.sh
   ```
2. **处理审核暂停（退出码 2）**：
   - 查看 `.upgrade/<新版本>/report.json` 了解新增、消失或歧义项。
   - 查阅同目录下的 `AI_REVIEW.md`（仅包含几十行差异文本）。
   - 编辑 `i18n/binary-translations.json` 或 `i18n/skill-translations.json` 补充或校准文案。
3. **重新执行升级**：
   再次运行 `bash scripts/auto_update.sh`，通过测试后自动重新安装。

---

## 一键回滚（恢复官方英文原版）

```bash
cd /Users/jnq/Dev/Private/Antigravity-zh

# 二进制层恢复官方 Google 原签名原件
bash scripts/patch_binary.sh --restore

# 内置 Skill 说明恢复官方英文原件
bash scripts/patch_skill_descriptions.sh --restore

# HUD 恢复原版（仅当曾主动实验汉化）
bash scripts/patch_hud.sh --restore
```

---

## 红线清单（违反即坏，违反即返工）

| 红线类别 | 严禁行为 | 后果与原因 |
| :--- | :--- | :--- |
| **命令与别名** | 汉化 `/resume`、`/skills`、flags、按键名 | 改变用户输入习惯，破坏自动化调用 |
| **配置解析值** | 汉化 `/settings` 中的 `default`、`on/off`、`always-proceed` | 导致设置反序列化失败或配置失效 |
| **补丁方式** | 使用 `bytes.replace()` 全局扫描替换二进制 | 破坏代码段、函数符号或未知关键数据 |
| **字节预算** | 中文 UTF-8 字节数超过原英文长度 | Go 字符串长度字段固定，超长会覆盖相邻字符串 |
| **代码签名** | 补丁后未正确执行 ad-hoc hardened runtime 签名 | macOS 会直接 SIGKILL 终止，提示 `zsh: killed agy` |
| **官方备份** | 覆盖或删除已有的 Google 官方原签名备份 | 导致永久丧失官方真理源与干净回滚能力 |
| **服务端文案** | 强行汉化 `/usage` 动态配额组说明 | 该数据由服务端动态下发，二进制中不存在实体 |

---

## 关键文件速查

- **翻译字典真理源**：
  - 二进制 TUI 翻译表：`i18n/binary-translations.json`
  - 内置 Skill 说明翻译表：`i18n/skill-translations.json`
- **核心执行脚本**：
  - 整体安装验收：`scripts/install.sh`
  - 自动增量升级：`scripts/auto_update.sh`
  - 二进制打补丁：`scripts/patch_binary.sh`（底层为 `scripts/patch_binary.py`）
  - 技能说明补丁：`scripts/patch_skill_descriptions.sh`
  - 8 项冒烟测试：`scripts/smoke_test.sh`
- **进阶文档**：
  - 详细操作规范：`SOP.md`
  - 架构与补丁原理：`ARCHITECTURE.md`
  - AI 翻译与字节预算规范：`AI_TRANSLATION_GUIDE.md`
  - 维护契约与完成定义：`AGENTS.md`
