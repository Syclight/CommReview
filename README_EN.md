# CommReview

> Make every local operation of Claude Code clearly visible

CommReview is a Claude Code hook that automatically uses AI to explain the meaning, safety level, and intent of **local operations** (shell commands, PowerShell, file writes/edits, and more) before Claude Code runs them, helping users make informed decisions.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English | [中文](./README.md)

## Preview

After the user selects **Allow** in the permission prompt, but before the command is actually executed, CommReview displays an explanation like this:

```text
━━━ CommReview Operation Explanation ━━━
$ rm -rf ./dist

🟠 Safety: Medium risk (may modify files or install software)
📖 Meaning: Recursively deletes the dist folder in the current directory and all of its contents.
🎯 Intent: The AI assistant is cleaning the project's build output directory before rebuilding.
⚠️ Note: This operation permanently deletes all files in the dist directory and cannot be undone.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

File writes and edits are explained too:

```text
━━━ CommReview Operation Explanation ━━━
✎ Write src/config.py

🟠 Safety: Medium risk (may modify files or install software)
📖 Meaning: Creates or overwrites src/config.py with new configuration content.
🎯 Intent: The AI assistant is adding a configuration file to the project.
⚠️ Note: If src/config.py already exists, its previous content will be overwritten.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Safety levels are easy to scan:

| Icon | Level | Example Commands |
|------|-------|------------------|
| ✅ | Safe (read-only operations) | `ls`, `cat`, `git log` |
| 🟡 | Low risk | `mkdir`, `git add`, `echo` |
| 🟠 | Medium risk | `npm install`, `git commit`, file writes |
| 🔴 | High risk | `rm -rf`, `chmod 777`, `curl \| sh` |

## Supported Operations

CommReview can explain many kinds of Claude Code local operations. You choose the interception scope during installation:

| Tool | Operation | Intercepted by default |
|------|-----------|------------------------|
| `Bash` | Shell commands (including `cmd` invoked through it) | ✅ |
| `PowerShell` | PowerShell commands | ✅ |
| `Write` | Write / overwrite a file | ✅ |
| `Edit` | Edit a file | ✅ |
| `NotebookEdit` | Edit Jupyter Notebook cells | ✅ |
| `Read` | Read a file | ⬜ (optional) |
| `Glob` / `Grep` | Find files / search content | ⬜ (optional) |

> **About read-only operations**: `Read`, `Glob`, and `Grep` are not intercepted by default, because every interception adds roughly 1-3 seconds of AI-call latency and intercepting them all would noticeably slow Claude Code down. If you need them, choose a wider scope during installation or edit the `tools` field in `config.json`.

## Installation

### Requirements

- [Claude Code](https://claude.ai/code) installed
- Python 3.10+ (Windows users should install it from [python.org](https://python.org), **not** from the Microsoft Store)
- Access credentials for an AI model provider (see [Model Configuration](#model-configuration))

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/Syclight/CommReview.git
cd CommReview
```

**2. Run the installer**

```bash
python install.py
```

During installation, the script interactively configures the **AI model**, the **interception scope**, and the **output language**. When finished, it automatically:

- Copies the hook files to `~/.claude/plugins/local/comm-review/`
- Writes the configuration (model + scope + language) to `~/.claude/plugins/local/comm-review/config.json`
- Adds the PreToolUse hook to `~/.claude/settings.json` based on the chosen scope

**3. Restart Claude Code**

Close and reopen Claude Code for the configuration to take effect.

> **Install from inside Claude Code**: enter `! python install.py` in the input box.

## Model Configuration

The installer prompts you to choose a model provider. Two types of interfaces are supported.

### 1. Anthropic Claude (recommended)

Authentication priority:

1. `ANTHROPIC_AUTH_TOKEN` environment variable
2. `ANTHROPIC_API_KEY` environment variable
3. Automatic loading from `~/.claude/.credentials.json` (created after `claude login`)

### 2. OpenAI-Compatible APIs

CommReview supports OpenAI, Azure OpenAI, DeepSeek, local models such as Ollama, and any service compatible with the OpenAI Chat Completions API.

Set the corresponding API key environment variable beforehand. The default is `OPENAI_API_KEY`.

### Reconfigure

Run `python install.py` again to overwrite the existing configuration (model, scope, language).

### Manual Configuration

`~/.claude/plugins/local/comm-review/config.json` supports the following fields:

```json
{
  "provider": "anthropic",
  "model": "claude-haiku-4-5-20251001",
  "tools": ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit"],
  "language": "zh"
}
```

- `tools`: the list of tools to intercept and explain; add or remove entries (e.g. add `"Read"`, `"Glob"`, `"Grep"`).
- `language`: output language, `"zh"` (Chinese) or `"en"` (English).

> ⚠️ After changing `tools`, keep the `matcher` of the PreToolUse hook in `~/.claude/settings.json` in sync with it (a `|`-separated regex of tool names). The easiest way is to re-run `python install.py`.

## How It Works

CommReview uses Claude Code's **PreToolUse hook** mechanism:

```text
Claude wants to perform a local operation (shell command, file write/edit, etc.)
       ↓
The user sees the permission prompt and selects "Allow"
       ↓
The PreToolUse hook is triggered (only for tools within the configured scope)
       ↓
comm_review.py reads config.json, builds a description from the operation type, and calls the configured AI model (~1-3 seconds)
       ↓
It generates an explanation (meaning + safety + intent) in the configured language
       ↓
The explanation is displayed to the user as a systemMessage
       ↓
The operation is executed
```

- **Timeouts**: 8-second API call timeout + 15-second total hook timeout
- **Graceful fallback**: Any error, including network failure, missing authentication, or timeout, is silently skipped so Claude Code continues to work normally

## Project Structure

```text
CommReview/
├── hooks/
│   ├── comm_review.py       # Main hook script: intercept operation → call AI → format output
│   └── python_finder.sh     # Cross-platform Python resolver
├── hooks.json               # Hook configuration template for reference
├── install.py               # Automatic installer
├── README.MD
└── README_CN.md
```

After installation, the following files are generated:

```text
~/.claude/plugins/local/comm-review/
├── hooks/                   # Same as above
└── config.json              # Configuration: model + scope + language, generated by install.py
```

## Uninstall

```bash
rm -rf ~/.claude/plugins/local/comm-review/
```

Then manually edit `~/.claude/settings.json` and remove the entry under `hooks.PreToolUse` that contains `comm_review.py`.

## FAQ

**Q: After selecting "Allow", no explanation appears and the command runs directly. Why?**

Possible causes:

1. The operation is outside the interception scope (e.g. `Read`/`Glob`/`Grep` are not intercepted by default — see [Supported Operations](#supported-operations))
2. Authentication is unavailable (Claude Code is not logged in and the corresponding API key environment variable is not set)
3. A network issue caused the API call to time out
4. Python is not installed correctly (Windows users should check whether they installed the Microsoft Store version)

CommReview is designed to fail silently in these cases, so Claude Code continues working normally.

**Q: Will this slow down Claude Code?**

It depends on the configured model, but explanations usually complete within 1-3 seconds. The hook only applies to the configured interception scope — by default shell commands plus file writes/edits. Read-only operations are not intercepted by default, so normal reads are not slowed down.

**Q: Does CommReview support English output?**

Yes. You can choose the output language during installation, or change the `language` field in `config.json` at any time (`"zh"` / `"en"`).

**Q: Does it support PowerShell / cmd?**

Yes. The `PowerShell` tool is within the default interception scope, and `cmd` commands invoked through Bash or PowerShell are explained along with their respective tool.

**Q: Will command contents be sent to an external service?**

Yes. Command contents are sent to the configured AI service API to generate the explanation. When using Anthropic Claude, CommReview uses the same API endpoint and authentication as Claude Code itself.

## License

MIT
