# CommReview

> 让 Claude Code 的每一条命令都清晰可见

CommReview 是一个 Claude Code Hook，在 Claude 请求执行 Bash 命令时，**自动用 AI 解释命令的含义、安全性和执行意图**，帮助用户做出知情判断。

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

## 效果预览

用户在权限提示选择「允许」后、命令实际执行前，会看到：

```
━━━ CommReview 命令解释 ━━━
$ rm -rf ./dist

🟠 安全性: 中等风险（可能修改文件或安装软件）
📖 含义: 递归删除当前目录下的 dist 文件夹及其所有内容。
🎯 意图: AI 助手正在清理项目的构建输出目录，准备重新构建。
⚠️ 注意: 此操作会永久删除 dist 目录中的所有文件，无法撤销。
━━━━━━━━━━━━━━━━━━━━━━━━━
```

安全等级一目了然：

| 图标 | 等级 | 示例命令 |
|------|------|----------|
| ✅ | 安全（只读操作） | `ls`、`cat`、`git log` |
| 🟡 | 低风险 | `mkdir`、`git add`、`echo` |
| 🟠 | 中等风险 | `npm install`、`git commit`、文件写入 |
| 🔴 | 高风险 | `rm -rf`、`chmod 777`、`curl \| sh` |

## 安装

### 前提条件

- [Claude Code](https://claude.ai/code) 已安装
- Python 3.10+（Windows 用户请从 [python.org](https://python.org) 安装，**不要**用 Microsoft Store 版本）
- AI 模型的访问凭据（见下方模型配置）

### 步骤

**1. 克隆仓库**

```bash
git clone https://github.com/Syclight/CommReview.git
cd CommReview
```

**2. 运行安装脚本**

```bash
python install.py
```

安装过程中会交互式配置使用的 AI 模型（见下方），完成后脚本会自动：
- 将 Hook 文件复制到 `~/.claude/plugins/local/comm-review/`
- 将模型配置写入 `~/.claude/plugins/local/comm-review/config.json`
- 将 PreToolUse 钩子写入 `~/.claude/settings.json`

**3. 重启 Claude Code**

关闭并重新打开 Claude Code，配置即刻生效。

> **在 Claude Code 中安装**：在输入框输入 `! python install.py` 直接运行。

## 模型配置

安装时会提示选择模型，支持两类接口：

### 1. Anthropic Claude（推荐）

认证优先级：
1. 环境变量 `ANTHROPIC_AUTH_TOKEN`
2. 环境变量 `ANTHROPIC_API_KEY`
3. 自动读取 `~/.claude/.credentials.json`（`claude login` 后自动存在）

### 2. OpenAI 兼容接口

支持 OpenAI、Azure OpenAI、DeepSeek、本地模型（Ollama 等）任何兼容 OpenAI Chat Completions API 的服务。

需要提前设置对应的 API Key （默认 OPENAI_API_KEY）环境变量。

### 重新配置模型

重新运行 `python install.py` 即可覆盖现有配置。

## 工作原理

CommReview 利用 Claude Code 的 **PreToolUse 钩子**机制：

```
Claude 想执行 Bash 命令
       ↓
用户看到权限提示，选择「允许」
       ↓
PreToolUse 钩子触发
       ↓
comm_review.py 读取 config.json，调用配置的 AI 模型（~1-3 秒）
       ↓
生成中文解释（含义 + 安全性 + 意图）
       ↓
以 systemMessage 展示给用户
       ↓
命令实际执行
```

- **超时**：8 秒 API 调用超时 + 15 秒钩子总超时
- **降级**：任何错误（无网络、无认证、超时）均静默跳过，不影响正常使用

## 项目结构

```
CommReview/
├── hooks/
│   ├── comm_review.py       # 主钩子脚本：拦截命令 → 调用 AI → 格式化输出
│   └── python_finder.sh     # 跨平台 Python 解析器
├── hooks.json               # 钩子配置结构模板
├── install.py               # 自动安装脚本
└── README.md
```

安装后会额外生成：

```
~/.claude/plugins/local/comm-review/
├── hooks/                   # 同上
└── config.json              # 模型配置（由 install.py 生成）
```

## 卸载

```bash
rm -rf ~/.claude/plugins/local/comm-review/
```

然后手动编辑 `~/.claude/settings.json`，删除 `hooks.PreToolUse` 中包含 `comm_review.py` 的条目。

## 常见问题

**Q: 选择「允许」后没有显示解释，命令直接执行了？**

可能原因：
1. 认证不可用（未登录 Claude Code，且未设置对应的 API Key 环境变量）
2. 网络问题导致 API 调用超时
3. Python 未正确安装（Windows 用户检查是否为 Microsoft Store 版本）

CommReview 设计为静默降级，以上情况不会报错，Claude Code 正常工作不受影响。

**Q: 会拖慢 Claude Code 的速度吗？**

取决于所配置的模型，通常在 1-3 秒内完成。Hook 仅对 Bash 命令生效，文件读写等操作不受影响。

**Q: 支持英文输出吗？**

目前默认输出中文。如需英文，修改 `hooks/comm_review.py` 中的 `EXPLAIN_PROMPT` 变量，将提示词改为英文即可。

**Q: 命令内容会被发送到外部吗？**

是的，命令内容会发送至所配置的 AI 服务 API 以生成解释。使用 Anthropic Claude 时与 Claude Code 本身使用相同的 API 端点和认证。

## License

MIT
