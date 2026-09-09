# AGENTS.md

本仓库是面向 AI 协作维护的 Antigravity CLI 简体中文汉化项目。任何自动化代理在修改前都应先阅读本文件，再按需阅读 `README.md`、`AI_TRANSLATION_GUIDE.md`、`ARCHITECTURE.md` 和 `SOP.md`。

## 不可破坏的产品边界

1. 只修改展示文本，不修改 AGY 功能逻辑、网络协议、权限行为或账户数据。
2. `/resume`、`/skills`、命令别名、flags、快捷键名、模型名和品牌名保持原文；只汉化说明和人类可读标签。
3. HUD 默认保持上游原版。`patch_hud.sh --apply` 只是可选实验，不得加入默认安装流程。
4. 当前二进制清单只支持 `agy 1.1.28`、`darwin-arm64` 和清单声明的官方 SHA-256。未知版本必须失败关闭。
5. 禁止对二进制执行全局字符串替换。每条修改必须同时具备精确偏移、预期英文原文、中文译文和上下文。
6. 不删除或覆盖用户已有的 Google 原签名备份，不提交本机令牌、日志、对话、邮箱或其他个人数据。

## 跨平台实验边界

- 本仓库默认安装、清单和完成定义仍只覆盖 macOS arm64；不得为了兼容 Windows 放宽现有校验。
- 仅当用户明确要求时，AI 可以在原生 Windows 主机上按 README 的“Windows AI 自适配协议”生成隔离的本地实验产物；只复用 `en`、`zh`、`context` 和术语，不复用 macOS 的偏移、哈希、签名、路径或脚本。
- Windows 产物不得接入默认 `scripts/install.sh`，不得提交 EXE 或证书，不得关闭 Defender/SmartScreen，也不得在未经用户明确批准时替换 PATH 中的官方 `agy.exe` 或安装代码签名证书。
- macOS 上的 PE 分析和 PowerShell 静态测试不能算 Windows 实机证据；只有原生 Windows 上的哈希、Authenticode、真实 TUI 和回滚验收才能支持“本地适配可用”的结论。

## 信息源优先级

| 目标 | 唯一事实来源 | 修改入口 |
|---|---|---|
| Go TUI 与内置命令说明 | `i18n/binary-translations.json` | `scripts/patch_binary.sh` |
| 已解包内置 Skill 的菜单说明 | `i18n/skill-translations.json` | `scripts/patch_skill_descriptions.sh` |
| HUD 可选实验翻译 | `i18n/hud-translations.json` | `scripts/patch_hud.sh --apply` |
| 默认安装与最终验收 | 脚本行为 | `scripts/install.sh`、`scripts/smoke_test.sh` |

不要把 README 中的示例、终端截图或已安装文件当作翻译源；它们只是验证证据。

## 标准工作流

1. 运行 `git status --short --branch`，保护不相关改动。
2. 阅读 `AI_TRANSLATION_GUIDE.md`，确认术语、占位符和字节预算。
3. 先运行 `bash scripts/patch_binary.sh --dry-run`；失败时停止，不得绕过版本或哈希校验。
4. 修改机器可读清单和对应脚本，避免只改已安装文件。
5. 运行 `python3 -m unittest discover -s tests -v` 和 `bash scripts/install.sh` 完成应用与自动验收。
6. 启动真实 `agy`，输入 `/`，至少检查菜单首屏、末屏和底部快捷键提示。
7. 运行 `git diff --check`，说明验证范围及尚未验证的环境。

## 完成定义

- `agy --version` 仍为清单声明版本；
- `codesign --verify --deep --strict ~/.local/bin/agy` 通过；
- `bash scripts/smoke_test.sh` 通过；
- HUD 原版检查通过；
- 命令名未汉化，右侧说明为中文；
- 回滚路径仍可用；
- 文档、脚本和机器可读清单描述一致。

涉及官方升级、偏移重定位和回滚的具体步骤见 `SOP.md`。二进制原理与风险见 `ARCHITECTURE.md`。

`scripts/auto_update.sh` 只允许机械继承拥有唯一上下文证据的旧译文；发现消失、歧义、
新增或变更的内置 Skill 时必须暂停，并让维护者决定是否把 `.upgrade/` 中的最小差异包
交给 AI。自动流程不得代替真实 TUI 验收，也不得自动提交或推送 Git。
