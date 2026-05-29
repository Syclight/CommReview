# CommReview

> 让 Claude Code 的每一个本地操作都清晰可见

CommReview 是一个 Claude Code Hook，在 Claude 请求执行**本地操作**（Shell 命令、PowerShell、文件写入/编辑等）时，**自动用 AI 解释操作的含义、安全性和执行意图**，帮助用户做出知情判断。

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](./README_EN.md) | 中文

## 效果预览

用户在权限提示选择「允许」后、命令实际执行前，会看到：

```
━━━ CommReview 操作解释 ━━━
$ rm -rf ./dist

🟠 安全性: 中等风险（可能修改文件或安装软件）
📖 含义: 递归删除当前目录下的 dist 文件夹及其所有内容。
🎯 意图: AI 助手正在清理项目的构建输出目录，准备重新构建。
⚠️ 注意: 此操作会永久删除 dist 目录中的所有文件，无法撤销。
━━━━━━━━━━━━━━━━━━━━━━━━━
```

文件写入/编辑同样会被解释：

```
━━━ CommReview 操作解释 ━━━
✎ 写入 src/config.py

🟠 安全性: 中等风险（可能修改文件或安装软件）
📖 含义: 创建或覆盖 src/config.py 文件，写入新的配置内容。
🎯 意图: AI 助手正在为项目添加配置文件。
⚠️ 注意: 若 src/config.py 已存在，其原有内容将被覆盖。
━━━━━━━━━━━━━━━━━━━━━━━━━
```

安全等级一目了然：

| 图标 | 等级 | 示例命令 |
|------|------|----------|
| ✅ | 安全（只读操作） | `ls`、`cat`、`git log` |
| 🟡 | 低风险 | `mkdir`、`git add`、`echo` |
| 🟠 | 中等风险 | `npm install`、`git commit`、文件写入 |
| 🔴 | 高风险 | `rm -rf`、`chmod 777`、`curl \| sh` |

## 支持的操作

CommReview 可解释 Claude Code 的多种本地操作，安装时按需选择拦截范围：

| 工具 | 操作 | 是否默认拦截 |
|------|------|------------|
| `Bash` | Shell 命令（含通过其调用的 `cmd` 等） | ✅ |
| `PowerShell` | PowerShell 命令 | ✅ |
| `Write` | 写入/覆盖文件 | ✅ |
| `Edit` | 编辑文件 | ✅ |
| `NotebookEdit` | 编辑 Jupyter Notebook 单元格 | ✅ |
| `Read` | 读取文件 | ⬜（可选） |
| `Glob` / `Grep` | 查找文件 / 搜索内容 | ⬜（可选） |

> **关于只读操作**：`Read`、`Glob`、`Grep` 等只读操作默认不拦截，因为每次拦截都会增加约 1-3 秒的 AI 调用延迟，全量拦截会明显拖慢 Claude Code。如确有需要，可在安装时选择更大的范围，或编辑 `config.json` 的 `tools` 字段。

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

安装过程中会交互式配置 **AI 模型**、**拦截范围**和**输出语言**（见下方），完成后脚本会自动：
- 将 Hook 文件复制到 `~/.claude/plugins/local/comm-review/`
- 将配置（模型 + 拦截范围 + 语言）写入 `~/.claude/plugins/local/comm-review/config.json`
- 根据所选范围，将 PreToolUse 钩子写入 `~/.claude/settings.json`

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

### 重新配置

重新运行 `python install.py` 即可覆盖现有配置（模型、拦截范围、语言）。

### 手动调整配置

`~/.claude/plugins/local/comm-review/config.json` 支持以下字段：

```json
{
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "tools": ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit"],
  "language": "zh"
}
```

- `tools`：要拦截解释的工具列表，可增删（如加入 `"Read"`、`"Glob"`、`"Grep"`）。
- `language`：输出语言，`"zh"`（中文）或 `"en"`（English）。

> ⚠️ 修改 `tools` 后，还需让 `~/.claude/settings.json` 中 PreToolUse 钩子的 `matcher` 与之一致（以 `|` 分隔的工具名正则），最简单的方式是重新运行 `python install.py`。

## 工作原理

CommReview 利用 Claude Code 的 **PreToolUse 钩子**机制：

```
Claude 想执行某个本地操作（Shell 命令、文件写入/编辑等）
       ↓
用户看到权限提示，选择「允许」
       ↓
PreToolUse 钩子触发（仅对配置范围内的工具生效）
       ↓
comm_review.py 读取 config.json，根据操作类型构造说明，调用配置的 AI 模型（~1-3 秒）
       ↓
生成解释（含义 + 安全性 + 意图），语言由 config.json 决定
       ↓
以 systemMessage 展示给用户
       ↓
操作实际执行
```

- **超时**：8 秒 API 调用超时 + 15 秒钩子总超时
- **降级**：任何错误（无网络、无认证、超时）均静默跳过，不影响正常使用

## 项目结构

```
CommReview/
├── hooks/
│   ├── comm_review.py       # 主钩子脚本：拦截操作 → 调用 AI → 格式化输出
│   └── python_finder.sh     # 跨平台 Python 解析器
├── hooks.json               # 钩子配置结构模板
├── install.py               # 自动安装脚本
└── README.md
```

安装后会额外生成：

```
~/.claude/plugins/local/comm-review/
├── hooks/                   # 同上
└── config.json              # 配置：模型 + 拦截范围 + 语言（由 install.py 生成）
```

## 卸载

```bash
rm -rf ~/.claude/plugins/local/comm-review/
```

然后手动编辑 `~/.claude/settings.json`，删除 `hooks.PreToolUse` 中包含 `comm_review.py` 的条目。

## 常见问题

**Q: 选择「允许」后没有显示解释，命令直接执行了？**

可能原因：
1. 该操作不在拦截范围内（如默认不拦截 `Read`/`Glob`/`Grep`，见「支持的操作」）
2. 认证不可用（未登录 Claude Code，且未设置对应的 API Key 环境变量）
3. 网络问题导致 API 调用超时
4. Python 未正确安装（Windows 用户检查是否为 Microsoft Store 版本）

CommReview 设计为静默降级，以上情况不会报错，Claude Code 正常工作不受影响。

**Q: 为什么解释只在我选择「允许」之后才出现，而不是之前？**

这是由 CommReview 所依赖的 Claude Code **PreToolUse 钩子**机制决定的，而非 CommReview 自身的限制：

1. **钩子的触发时机固定**：在 Claude Code 的工具调用流程中，PreToolUse 钩子只在用户对权限提示作出选择（允许）之后、操作真正执行之前被触发。CommReview 无法让自己「抢在」权限提示之前运行。
2. **拒绝时不会执行**：如果你在权限提示中选择「拒绝」，该操作会被直接终止，钩子根本不会被调用，自然也不会（也无需）生成解释。
3. **解释正好落在「已授权但未执行」的窗口**：因此你看到的解释描述的就是即将执行的那一次操作；若解释让你改变主意，仍可在操作执行前将其中止（如 Ctrl+C）。

**Q: 会拖慢 Claude Code 的速度吗？**

取决于所配置的模型，通常在 1-3 秒内完成。Hook 只对配置的拦截范围生效，默认覆盖 Shell 命令与文件写入/编辑；只读操作默认不拦截，因此不会拖慢正常读取。

**Q: 支持英文输出吗？**

支持。安装时可选择输出语言，或随时修改 `config.json` 的 `language` 字段（`"zh"` / `"en"`）。

**Q: 支持 PowerShell / cmd 吗？**

支持。`PowerShell` 工具默认在拦截范围内；通过 Bash 或 PowerShell 调用的 `cmd` 命令也会随对应工具一并被解释。

**Q: 命令内容会被发送到外部吗？**

是的，命令内容会发送至所配置的 AI 服务 API 以生成解释。使用 Anthropic Claude 时与 Claude Code 本身使用相同的 API 端点和认证。

## License

MIT
