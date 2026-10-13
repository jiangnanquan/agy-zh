# SOP — 升级与维护流程

## 场景一：首次汉化

```bash
# 1. 克隆项目
git clone https://github.com/jiangnanquan/agy-zh.git
cd agy-zh

# 2. 预检、安装并自动验收
bash scripts/install.sh

# 3. 人工验收
# 再启动 agy，观察真实交互界面
```

人工验收时输入 `/`，至少检查菜单首屏、末屏和底部快捷键提示；命令名应保持英文，
右侧说明应为中文，HUD 应保持上游原版。

## 场景二：AGY 官方升级后重新汉化

优先运行低 token 自动流程：

```bash
bash scripts/auto_update.sh
```

旧译文能通过唯一上下文确认时会自动继承；发现新增/变更 Skill、消失文案或歧义偏移时，
命令以退出码 `2` 暂停。先阅读 `.upgrade/<版本>/report.json`；只有需要 AI 时，才把同目录
的 `AI_REVIEW.md` 交给 AI。处理清单后重新运行命令。自动流程不会提交 Git，也不能替代
本节末尾的真实 TUI 检查。

需要逐步诊断时使用下面的人工流程：

```bash
# 1. 确认新版本
agy --version

# 2. HUD 层：确认仍为上游原版
bash scripts/patch_hud.sh --check-original

# 3. 二进制层：先干跑；已适配版本会从官方原包重新验证，未知版本安全拒绝
bash scripts/patch_binary.sh --dry-run

# 如果这里失败，停止。不得复制旧偏移、跳过哈希或直接全局替换字符串。

# 4. 维护者用 pclntab 和反汇编确认新偏移，同时更新官方归档 URL、SHA-512、
#    解包后 SHA-256 和版本号，再安装
go run scripts/go_func_ranges.go ~/.local/bin/agy HintNavigate HintScrollPage
bash scripts/patch_binary.sh
bash scripts/patch_skill_descriptions.sh
bash scripts/smoke_test.sh
```

最后启动真实 `agy`，依次检查 `/` 菜单首屏与末屏、`/settings`、`/usage` 和底部快捷键。
若发现全新的二进制界面英文，把该屏幕与对应上下文作为新的小型 AI 输入；不要重新发送
整张历史翻译表或整个二进制。

## 场景三：汉化不生效

```bash
# 1. HUD 层：同时检查插件源码与真正执行的已部署 runtime 均为原版
bash scripts/patch_hud.sh --check-original

# 2. 检查已部署 runtime 使用自动语言设置
grep '"language": "auto"' ~/.gemini/antigravity-cli/agy-hud-runtime/runtime/agy-hud.config.json

# 3. 二进制层：检查签名与 patch 状态；后台升级后的中英混合文件会显示未知状态
bash scripts/patch_binary.sh --status

# 4. 内置 Skill：检查菜单说明状态
bash scripts/patch_skill_descriptions.sh --check
```

## 场景四：回滚到英文

```bash
# HUD 层：仅在曾主动运行 --apply 时恢复
bash scripts/patch_hud.sh --restore

# 二进制层
bash scripts/patch_binary.sh --restore

# 内置 Skill 说明
bash scripts/patch_skill_descriptions.sh --restore
```

## 场景五：贡献新翻译

```bash
# 1. 先阅读 AI_TRANSLATION_GUIDE.md，再编辑翻译表
# 二进制偏移必须有目标版本的函数定位、原文字节和真实 TUI 证据
# HUD 层（可选实验，不属于默认安装）→ i18n/hud-translations.json
# 二进制层 → i18n/binary-translations.json
# 内置 Skill 说明 → i18n/skill-translations.json

# 2. 重新应用
bash scripts/patch_hud.sh --check-original
bash scripts/patch_binary.sh
bash scripts/patch_skill_descriptions.sh

# 3. 验证仓库一致性和真实安装
python3 -m unittest discover -s tests -v
bash scripts/smoke_test.sh
git diff --check
```

## 场景六：安全诊断 `zsh: killed agy`

```bash
# 1. 查看当前状态；签名无效时脚本会明确报错
bash scripts/patch_binary.sh --status

# 2. 从当前清单版本的 Google 原签名备份恢复
bash scripts/patch_binary.sh --restore

# 3. 确认原版可启动后，再按当前清单重新安装
agy --version
bash scripts/install.sh
```

不要重新运行旧的全局字符串替换脚本。macOS 会直接杀死签名失效的 Mach-O，表现为
`zsh: killed agy`，这不是普通的 TUI 崩溃。

## 场景七：交付闭环与 Git 提交/推送规程

当完成新版本适配、词条补齐并通过全部测试（`smoke_test.sh` 8 步冒烟全绿、单元测试通过、`git diff --check` 无空白缺陷）后：

1. **工作区审计**：`git status` 确认仅有本次合规修改的资产文件（如 `i18n/*.json`），无测试产物或敏感数据残留；
2. **规范原子提交**：
   ```bash
   git add i18n/ scripts/ SKILL.md SOP.md
   git commit -m "feat(compat): 适配 agy <版本号> 界面汉化"
   ```
3. **推送决策（主动询问 vs 授权主动推送）**：
   - **默认策略（主动询问）**：在交付报告中列出验收证据与提交哈希，主动询问人类用户：
     > “本地已规范提交完成（`<commit-hash>`），是否执行 `git push origin main` 推送至远端？”
   - **授权策略（主动推送）**：若用户指令中已包含“提交并 push”、“自动推送”或随后明确授权，直接在当前终端执行 `git push origin main`，并向用户汇报推送成功状态与远端分支同步结果。
   - **红线**：冒烟未通过、签名未校验或工作区有未审计改动时，严禁提交或推送。
