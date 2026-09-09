# agy-zh — Antigravity CLI 简体中文汉化

> 为 Google Antigravity CLI（`agy`）提供简体中文界面汉化。
> **只做 UI 文字汉化，不碰任何功能逻辑。**

## 项目定位

本项目专注 Antigravity CLI 的终端界面，不修改 IDE 桌面壳。它采用机器可读翻译清单、
版本锁定的精确偏移补丁、原子替换和真实 TUI 验收，便于 AI 持续定位、翻译、验证和升级。

本仓库有意采用 **macOS 主线维护 + AI 按宿主机自适配** 的策略，而不是由维护者长期维护
多套平台脚本。当前可直接安装和经过真实验收的只有 macOS arm64；Windows 用户应把本
仓库交给运行在原生 Windows 主机上的 AI，让它复用翻译语义和安全契约，重新生成该平台、
该架构、该版本专用的本地实验适配。

## 先让 AI 读这里

| 平台 | 当前状态 | AI 应采取的动作 |
|---|---|---|
| macOS arm64 | 仓库维护；已有安装、回滚和真实 TUI 验收 | 严格运行下文默认流程 |
| Windows amd64 / arm64 | 未提供现成脚本；允许 AI 本地实验适配 | 阅读“Windows AI 自适配协议”，不得直接运行 macOS 脚本 |
| 其他平台或架构 | 未适配 | 先做只读研究，不得把现有偏移或哈希套用过去 |

无论在哪个平台，AI 在改动前都必须依次阅读 [AGENTS.md](AGENTS.md)、
[AI_TRANSLATION_GUIDE.md](AI_TRANSLATION_GUIDE.md)、[ARCHITECTURE.md](ARCHITECTURE.md)
和 [SOP.md](SOP.md)，并先运行 `git status`。README 是入口，不会替代这些约束。

可以把下面这段直接交给 Windows 上的 AI：

```text
请先完整阅读本仓库的 AGENTS.md、README.md、AI_TRANSLATION_GUIDE.md、
ARCHITECTURE.md 和 SOP.md。你正在原生 Windows 主机上做本地实验适配：
只复用现有清单中的 en、zh、context 和术语，不复用 macOS 的 offset、SHA、
下载地址、签名方式、路径或 shell 脚本。先只读确认 Windows 架构、agy 版本、
官方发布清单、原始 EXE 哈希、Authenticode 状态、实际 Skill/HUD 路径和 Git 状态；
再为这个 Windows 架构与版本生成隔离的精确偏移清单、PowerShell 补丁/回滚脚本、
测试和证据报告。禁止全局字符串替换，禁止直接修改唯一的官方 EXE，禁止覆盖旧备份，
禁止绕过 Defender/SmartScreen，禁止安装证书或替换 PATH 中的 agy.exe，除非我明确批准。
未知版本或任一原文、哈希、签名、偏移不匹配时必须失败关闭。最后必须在真实 Windows
终端中检查斜杠菜单首屏、末屏、底部快捷键，并实际验证回滚。
```

## 汉化效果

![Antigravity CLI 汉化效果：命令名保持英文，右侧说明及快捷键提示为中文](assets/agy-cli-zh-preview.png)

## 当前 macOS 实现

AGY CLI 的显示来自 **三处**。本项目汉化 Go 二进制主体和已解包的内置 Skill
说明；HUD 保持插件原版：

```
┌──────────────────────────────────────────────────────────┐
│  第一层：HUD 插件（JavaScript，默认不汉化）               │
│  位置：插件源码 + ~/.gemini/antigravity-cli/...运行时    │
│  内容：状态栏 · 令牌统计 · 额度显示 · 元数据行            │
│  方式：保持上游原版，可选实验性汉化、可随时恢复            │
│  难度：★☆☆ 低                                            │
├──────────────────────────────────────────────────────────┤
│  第二层：Go 二进制主体                                    │
│  位置：~/.local/bin/agy (Mach-O arm64, ~170MB)           │
│  内容：斜杠命令说明 · /settings · /usage · 快捷键等       │
│  方式：官方哈希校验 + 精确偏移 patch + ad-hoc 重签名      │
│  难度：★★☆ 中                                            │
├──────────────────────────────────────────────────────────┤
│  第三层：已解包的内置 Skill                               │
│  内容：系统内置 Skill 的右侧说明                         │
│  方式：仅替换 SKILL.md 的 YAML description，并保留备份    │
└──────────────────────────────────────────────────────────┘
```

斜杠命令名及别名始终保持英文，例如 `/resume`、`/skills`；只汉化它们右侧的解释。
`/settings` 会汉化字段标签、底部说明和确认过的纯展示选项；同时参与配置解析的
`default`、`on/off`、`always-proceed`、配色方案名等值保持原文，以免破坏已有配置。

`/usage` 会汉化客户端内置的标题、账户标签、额度状态、刷新提示、AI 点数说明和底部
操作提示。模型名保持原文；分组名、额度周期名、组内模型说明和页面末尾的额度规则说明
由服务端通过 `QuotaSummaryGroup/QuotaSummaryBucket` 动态返回，不存在于版本锁定的
二进制字符串表中，因此当前安全补丁不会改写这些服务端内容。

## macOS 依赖

- macOS arm64
- `curl`、`python3`、Node.js、Go（官方原包下载、补丁、HUD 检查和偏移维护）
- `agy` v1.1.28（当前偏移表严格锁定此版本）
- `agy-hud` 插件（仅用于状态栏，保持原版）

## macOS 快速开始

```bash
# 自动完成 HUD 原版检查、版本预检、安装和验收
bash scripts/install.sh
```

安装脚本不会汉化 HUD，也不会修改斜杠命令名。如果只想检查而不写入二进制：

```bash
bash scripts/patch_hud.sh --check-original
bash scripts/patch_binary.sh --dry-run
```

二进制层会从清单固定的官方 HTTPS 地址取得发布包，依次校验归档 SHA-512、解包后
SHA-256、版本号和 Google Developer ID 签名，再按版本保留原件，例如
`~/.local/bin/agy.zh-backup-1.1.28`。汉化后的可执行文件使用 macOS ad-hoc
hardened-runtime 签名。升级到其他 `agy` 版本时，脚本会失败关闭，不会拿旧备份覆盖
新版；旧的无版本号备份也不会被删除或覆盖。

官方 `agy` 会在日常运行中后台自更新，因此一次安装不能永久跨越未来版本。新版本发布
后需要先为该版本重新定位精确偏移；适配完成后再次运行 `bash scripts/install.sh` 即可从
干净官方原件重建汉化版，避免把增量更新后的中英混合二进制继续当作补丁来源。

## 低 token 自动升级

日常升级不需要让 AI 重新读取 170MB 二进制或重译整张表。维护者可运行：

```bash
bash scripts/auto_update.sh
```

流程先读取官方在线发布清单并验证版本、归档 SHA-512、二进制 SHA-256 与 Google
Developer ID 签名；若 PATH 中恰好是同版本的 Google 原签名文件，会直接复用以节省下载。
每条旧译文只在“英文原文仍存在，且至少一侧 32–128 字节上下文在新二进制中唯一匹配”
时自动继承新偏移，不按出现次数猜测，也不做全局替换。零待审项时，脚本才会更新清单、
运行测试并重新安装汉化版。

若旧文案消失、上下文歧义、内置 Skill 新增或说明变更，自动流程会以退出码 `2` 暂停，
在 `.upgrade/<版本>/report.json` 写入短报告，并生成只含差异的 `AI_REVIEW.md`。维护者只需
查看这几十行内容，再决定是否交给 AI；历史译文和已确认偏移不会进入提示词，从而把 token
消耗限制在真正新增的部分。`.upgrade/` 已被 Git 忽略，不会误提交本机扫描产物。

这套流程不会自动提交或推送 Git，也不会声称仅靠静态扫描发现了所有全新二进制界面。
发布前仍必须启动真实 `agy`，检查 `/` 菜单首尾、`/settings`、`/usage` 和底部快捷键；
若真实界面出现报告未覆盖的新英文，再把那一小段交给 AI。这样自动化负责可证明的机械
工作，人类只负责新增语义和最终视觉验收。

## Windows AI 自适配协议

Windows 版和 macOS 版共享的是 UI 文本、术语、字节预算、失败关闭和验收原则，不共享
二进制事实。[官方 PowerShell 安装器](https://antigravity.google/cli/install.ps1) 当前把 `agy.exe` 安装到
`$env:LOCALAPPDATA\agy\bin\agy.exe`，并使用 `windows_amd64` 或 `windows_arm64`
发布清单；AI 每次工作时都应从官方安装器和在线清单重新确认，不能把 README 中的路径
或版本当作永久事实。生成的 Windows 适配由当地用户和执行它的 AI 负责，本仓库不承诺
发布、追踪或维护专门的 Windows 版本。

### 1. 只读建立 Windows 基线

AI 应先在原生 Windows PowerShell 中确认事实，不得先修改文件：

```powershell
$agy = (Get-Command agy).Source
& $agy --version
Get-FileHash $agy -Algorithm SHA256
Get-AuthenticodeSignature $agy | Format-List Status, StatusMessage, SignerCertificate

$arch = if ($env:PROCESSOR_ARCHITEW6432) {
    $env:PROCESSOR_ARCHITEW6432
} else {
    $env:PROCESSOR_ARCHITECTURE
}
$platform = switch ($arch) {
    'AMD64' { 'windows_amd64' }
    'ARM64' { 'windows_arm64' }
    default { throw "Unsupported architecture: $arch" }
}
$manifestUrl = "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/$platform.json"
$release = Invoke-RestMethod $manifestUrl
$release | Format-List version, url, sha512
```

必须另外确认 `Get-Command agy` 的结果与官方清单是同一版本，并用清单中的 SHA-512 校验
重新下载的干净原件。若 PATH 中的文件已经被修改、签名状态异常或版本不一致，AI 不得
把它当作定位来源；应先保留现场，再转向通过官方清单校验的干净原件。若官方原件仍无法
通过哈希、架构或签名检查，则报告并停止，不能猜测来源。

### 2. 只复用翻译语义

AI 可以从 `i18n/binary-translations.json` 复用：

- `en`：要寻找的精确英文原文；
- `zh`：中文译文与 UTF-8 字节预算；
- `context`：必须通过真实界面和反汇编共同确认的用途。

以下内容必须在 Windows PE 文件上重新取得：平台、架构、版本、官方 URL、SHA-512、
二进制 SHA-256、文件偏移、函数/引用上下文、签名状态和安装路径。不得将 Mach-O 偏移
加减一个固定差值后当作 Windows 偏移，也不得用 `bytes.replace()` 或 PowerShell
`-replace` 扫描整个 EXE。

### 3. 隔离 Windows 产物

建议 AI 把生成内容放在个人分支或 `ports/windows/<arch>/<version>/` 下，至少包含：

```text
manifest.json          # Windows 专用版本、架构、官方哈希和逐条精确偏移
patch_binary.ps1       # dry-run、应用、状态和回滚；默认只处理暂存副本
smoke_test.ps1         # 哈希、版本、补丁状态、Skill/HUD 和启动验收
EVIDENCE.md            # 原件来源、定位依据、签名影响和真实 Windows 测试证据
```

这些文件不得接入当前默认 `scripts/install.sh`，也不得把 Windows 适配写成仓库已正式支持。
不要提交 `.exe`、证书、令牌、邮箱、日志、对话或其他个人数据。

### 4. 单独处理 Authenticode

修改 PE 内容会破坏原发布者的 Authenticode 签名；Windows 没有与 macOS ad-hoc 签名
完全等价的默认路径。因此 AI 必须：

1. 在补丁前记录官方 EXE 的哈希、签名状态和发布者，并保留只读的版本化备份；
2. 只在同目录暂存副本上打补丁，逐条验证 `offset + en + context` 后再测试；
3. 明确报告补丁后 `Get-AuthenticodeSignature` 的真实状态，绝不能继续声称是 Google 签名；
4. 不得自动创建、安装或信任自签名证书，不得关闭 Defender、SmartScreen 或系统策略；
5. 若用户没有明确选择本地未签名实验或提供自己的代码签名方案，停在“已生成并验证暂存
   产物”阶段，不替换 PATH 中的官方 `agy.exe`。

版本化备份可采用
`$env:LOCALAPPDATA\agy\bin\agy.zh-backup-<version>-<arch>.exe`，但 AI 必须先确认目标
不存在；任何已有备份均不可覆盖。

### 5. Windows 完成定义

只有在原生 Windows 主机上完成以下项目，AI 才能说“此本地 Windows 适配可用”：

- 官方清单 SHA-512、原件 SHA-256、版本、架构和补丁逐条原文全部匹配；
- `agy.exe --version`、PowerShell 冒烟和补丁状态检查通过；
- 命令名、flags、快捷键、模型名和品牌名仍为原文；
- 真实 Windows Terminal 中 `/` 菜单首屏、末屏和底部提示显示正常；
- 内置 Skill 说明的实际 Windows 路径由运行时证据确认，而不是照抄 macOS 路径；
- HUD 默认仍为上游原版；
- 已实际回滚到官方原件，并再次核对哈希、版本和 Authenticode；
- 模拟未知版本时补丁失败关闭，且不会使用旧备份覆盖新版本。

在 macOS 上分析 PE、生成 PowerShell 或做静态测试，只能报告为“静态/契约验证”，不能
声称 Windows 实机通过。官方后台更新仍可能覆盖本地汉化；AI 必须沿用按版本重新适配的
策略，不能通过禁用更新或安全功能来维持汉化。

## macOS 回滚

```bash
# 仅在曾主动运行 --apply 时恢复 HUD；默认安装无需执行
bash scripts/patch_hud.sh --restore

# 二进制层回滚（从备份恢复）
bash scripts/patch_binary.sh --restore

# 内置 Skill 说明回滚
bash scripts/patch_skill_descriptions.sh --restore
```

## AI 维护入口

- [AGENTS.md](AGENTS.md)：AI 代理必须遵守的产品边界、信息源和完成定义；
- [AI_TRANSLATION_GUIDE.md](AI_TRANSLATION_GUIDE.md)：术语、占位符、字节预算和新增翻译流程；
- [ARCHITECTURE.md](ARCHITECTURE.md)：二进制、HUD 与内置 Skill 的实现原理；
- [SOP.md](SOP.md)：首次安装、官方升级、故障诊断和回滚步骤。

机器可读翻译只存放在 `i18n/*.json`；已安装文件、终端截图和 README 示例都不是翻译事实来源。

## 目录结构

```
agy-zh/
├── README.md                    # 本文件
├── AGENTS.md                    # AI 代理维护契约
├── AI_TRANSLATION_GUIDE.md      # AI 汉化规范
├── ARCHITECTURE.md              # 架构与汉化原理详解
├── SOP.md                       # 升级与维护流程
├── LICENSE                      # MIT License
├── assets/
│   └── agy-cli-zh-preview.png   # README 汉化效果图
├── hud/                         # 内置增强版 agy-hud 完整源码（双窗口 5h/1W、权威配额抓取）
├── i18n/
│   ├── hud-translations.json    # HUD 可选实验翻译表
│   ├── binary-translations.json # 二进制层翻译表（en → zh 对照）
│   └── skill-translations.json  # 内置 Skill 菜单说明翻译表
├── presets/
│   └── agy-hud.config.json      # HUD 推荐极简配置预设（赛博朋克 / 双模型内联）
├── scripts/
│   ├── install_hud.sh           # 内置 HUD 一键部署与配置应用入口
│   ├── patch_hud.sh             # HUD 可选汉化/原版恢复入口
│   ├── install.sh               # 默认安装与完整验收入口
│   ├── patch_binary.py          # 哈希、偏移、签名、原子替换
│   ├── patch_binary.sh          # 二进制层汉化入口
│   ├── prepare_upgrade.py       # 低 token 重定位、差异报告与 AI 最小接入包
│   ├── auto_update.sh           # 非交互升级、测试与安装入口
│   ├── patch_skill_descriptions.sh # 内置 Skill 说明汉化入口
│   ├── go_func_ranges.go        # 从 Go pclntab 定位渲染函数
│   └── smoke_test.sh            # 一键冒烟测试
└── tests/
    └── test_patch_binary.py     # 版本失败关闭、备份选择与清单契约测试
```

## 适用版本

| 组件 | 版本 | 说明 |
|------|------|------|
| `agy` 二进制 | v1.1.28 | SHA-256 锁定适配版本 |
| `agy-hud` 插件 | 内置增强版 | 内置完整源码，支持官方 1.1.28 双配额窗口 (5h/1W) 与极简展示预设 |
| 平台 | macOS arm64 | 当前唯一维护和实机验证的平台；Windows 仅提供 AI 自适配协议 |

## 致谢与开源协议

- 本项目基于 [MIT](LICENSE) 协议开源。
- 状态栏增强与 HUD 模块已内置于本项目（`hud/`），提供生态兼容与开箱即用的配置预设。
