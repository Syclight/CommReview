#!/usr/bin/env python3
"""
CommReview — 在 Claude Code 执行本地操作前用 AI 解释其含义

通过 PreToolUse 钩子拦截本地操作（Shell 命令、文件写入/编辑等），
调用 AI 模型生成解释（含义、安全性、执行意图），以 systemMessage
展示给用户供参考。任何错误均静默降级（exit 0），不影响 Claude Code
正常工作流。

支持的工具由 config.json 的 "tools" 字段控制，默认覆盖：
  - Bash / PowerShell  —— Shell 命令（含通过其调用的 cmd 等）
  - Write / Edit / NotebookEdit —— 文件写入与编辑
可按需加入 Read / Glob / Grep 等只读操作（注意每次拦截会增加 AI 延迟）。

输出语言由 config.json 的 "language" 字段控制（"zh" 中文 / "en" 英文）。
"""
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
API_TIMEOUT_S = 8
MAX_TOKENS = 300

# 默认拦截的工具集合。只读类（Read/Glob/Grep）默认不拦截，避免拖慢正常读取，
# 可在 config.json 的 "tools" 字段中显式加入。
DEFAULT_TOOLS = ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit"]

# 单个文本字段（命令、文件内容、替换片段等）送入 AI 前截断的最大长度，
# 防止超大内容撑爆 token 预算。
MAX_FIELD_CHARS = 1500
# 在用户界面 header 中展示的操作摘要的最大长度。
MAX_DISPLAY_CHARS = 80

SAFETY_ICONS = {
    "safe": "✅",
    "low_risk": "🟡",
    "medium_risk": "🟠",
    "high_risk": "🔴",
}

STRINGS = {
    "zh": {
        "header": "━━━ CommReview 操作解释 ━━━",
        "footer": "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "safety_prefix": "安全性",
        "meaning_prefix": "📖 含义",
        "intent_prefix": "🎯 意图",
        "note_prefix": "⚠️ 注意",
        "safety_labels": {
            "safe": "安全（只读操作）",
            "low_risk": "低风险",
            "medium_risk": "中等风险（可能修改文件或安装软件）",
            "high_risk": "高风险（可能删除数据或影响系统）",
        },
        "op_shell": "{shell} 命令：\n{command}",
        "op_write": "写入文件 {path}，内容如下：\n{content}",
        "op_edit": "编辑文件 {path}。\n原内容：\n{old}\n替换为：\n{new}",
        "op_notebook": "编辑 Jupyter Notebook {path}（单元格 {cell}，模式 {mode}），新内容：\n{source}",
        "op_read": "读取文件 {path}",
        "op_search": "在 {path} 中搜索：{pattern}",
        "op_generic": "{tool} 操作，参数：\n{params}",
        "disp_write": "✎ 写入 {path}",
        "disp_edit": "✎ 编辑 {path}",
        "disp_notebook": "✎ Notebook {path}",
        "disp_read": "👁 读取 {path}",
        "disp_search": "🔍 搜索 {path}",
        "disp_generic": "{tool}",
        "prompt": """\
请用中文简洁地分析以下操作，以 JSON 格式返回分析结果（只返回 JSON，无其他内容）：

操作:
{subject}

返回格式：
{{
  "explanation": "操作功能的简单解释（1-2句话，面向非技术用户）",
  "safety": "safe|low_risk|medium_risk|high_risk",
  "intent": "AI 助手可能执行此操作的原因（1句话）",
  "details": "若存在风险则说明具体风险（如：会永久删除文件、覆盖重要内容），否则为空字符串"
}}

安全等级定义：
- safe：只读操作，无任何风险（如 ls、cat、读取文件、搜索）
- low_risk：轻微变更，风险极低（如 mkdir、git add、新建文件）
- medium_risk：可能修改文件或安装软件（如 npm install、git commit、写入/编辑文件）
- high_risk：可能删除数据、修改系统配置或执行网络操作（如 rm -rf、chmod 777、curl | sh、覆盖关键文件）""",
    },
    "en": {
        "header": "━━━ CommReview Operation Explanation ━━━",
        "footer": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "safety_prefix": "Safety",
        "meaning_prefix": "📖 Meaning",
        "intent_prefix": "🎯 Intent",
        "note_prefix": "⚠️ Note",
        "safety_labels": {
            "safe": "Safe (read-only operation)",
            "low_risk": "Low risk",
            "medium_risk": "Medium risk (may modify files or install software)",
            "high_risk": "High risk (may delete data or affect the system)",
        },
        "op_shell": "{shell} command:\n{command}",
        "op_write": "Write to file {path}, with content:\n{content}",
        "op_edit": "Edit file {path}.\nOld:\n{old}\nReplaced with:\n{new}",
        "op_notebook": "Edit Jupyter Notebook {path} (cell {cell}, mode {mode}), new content:\n{source}",
        "op_read": "Read file {path}",
        "op_search": "Search in {path} for: {pattern}",
        "op_generic": "{tool} operation, parameters:\n{params}",
        "disp_write": "✎ Write {path}",
        "disp_edit": "✎ Edit {path}",
        "disp_notebook": "✎ Notebook {path}",
        "disp_read": "👁 Read {path}",
        "disp_search": "🔍 Search {path}",
        "disp_generic": "{tool}",
        "prompt": """\
Concisely analyze the following operation in English and return the result as JSON (return only JSON, nothing else):

Operation:
{subject}

Response format:
{{
  "explanation": "A simple explanation of what the operation does (1-2 sentences, for non-technical users)",
  "safety": "safe|low_risk|medium_risk|high_risk",
  "intent": "Why the AI assistant might perform this operation (1 sentence)",
  "details": "If there is a risk, describe it specifically (e.g. permanently deletes files, overwrites important content); otherwise an empty string"
}}

Safety levels:
- safe: read-only, no risk (e.g. ls, cat, reading files, searching)
- low_risk: minor change, very low risk (e.g. mkdir, git add, creating a new file)
- medium_risk: may modify files or install software (e.g. npm install, git commit, writing/editing files)
- high_risk: may delete data, change system configuration, or perform network operations (e.g. rm -rf, chmod 777, curl | sh, overwriting critical files)""",
    },
}


def _truncate(text: str, limit: int = MAX_FIELD_CHARS) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _load_config() -> dict:
    """Load config.json from the plugin root (parent of this script's dir)."""
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_oauth_token() -> str:
    """Read OAuth access token from ~/.claude/.credentials.json if not expired."""
    import time

    creds_path = os.path.join(
        os.path.expanduser("~"), ".claude", ".credentials.json"
    )
    try:
        with open(creds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        oauth = data.get("claudeAiOauth", {})
        expires_at = oauth.get("expiresAt", 0)
        if expires_at and time.time() * 1000 > expires_at:
            return ""
        return oauth.get("accessToken", "").strip()
    except Exception:
        return ""


def build_operation(tool_name: str, tool_input: dict, s: dict):
    """Map a tool invocation to (display, subject).

    `display` is the short summary shown in the explanation header.
    `subject` is the operation description fed to the AI model.
    Returns None when there is nothing meaningful to explain.
    """
    tool_input = tool_input or {}

    if tool_name in ("Bash", "PowerShell"):
        command = (tool_input.get("command") or "").strip()
        if not command:
            return None
        shell = "PowerShell" if tool_name == "PowerShell" else "Bash/Shell"
        display = f"$ {command}"
        subject = s["op_shell"].format(shell=shell, command=_truncate(command))
        return display, subject

    if tool_name == "Write":
        path = (tool_input.get("file_path") or "").strip()
        if not path:
            return None
        display = s["disp_write"].format(path=path)
        subject = s["op_write"].format(
            path=path, content=_truncate(tool_input.get("content", ""))
        )
        return display, subject

    if tool_name in ("Edit", "MultiEdit"):
        path = (tool_input.get("file_path") or "").strip()
        if not path:
            return None
        display = s["disp_edit"].format(path=path)
        if tool_name == "MultiEdit":
            edits = tool_input.get("edits") or []
            old = "\n---\n".join((e.get("old_string") or "") for e in edits)
            new = "\n---\n".join((e.get("new_string") or "") for e in edits)
        else:
            old = tool_input.get("old_string", "")
            new = tool_input.get("new_string", "")
        subject = s["op_edit"].format(
            path=path, old=_truncate(old), new=_truncate(new)
        )
        return display, subject

    if tool_name == "NotebookEdit":
        path = (tool_input.get("notebook_path") or "").strip()
        if not path:
            return None
        display = s["disp_notebook"].format(path=path)
        subject = s["op_notebook"].format(
            path=path,
            cell=tool_input.get("cell_id", "-"),
            mode=tool_input.get("edit_mode", "replace"),
            source=_truncate(tool_input.get("new_source", "")),
        )
        return display, subject

    if tool_name == "Read":
        path = (tool_input.get("file_path") or "").strip()
        if not path:
            return None
        display = s["disp_read"].format(path=path)
        subject = s["op_read"].format(path=path)
        return display, subject

    if tool_name in ("Glob", "Grep"):
        pattern = (tool_input.get("pattern") or "").strip()
        path = (tool_input.get("path") or ".").strip()
        if not pattern:
            return None
        display = s["disp_search"].format(path=path)
        subject = s["op_search"].format(path=path, pattern=_truncate(pattern, 200))
        return display, subject

    # Fallback: explain any other intercepted tool generically.
    params = _truncate(json.dumps(tool_input, ensure_ascii=False))
    display = s["disp_generic"].format(tool=tool_name)
    subject = s["op_generic"].format(tool=tool_name, params=params)
    return display, subject


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        input_data = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    config = _load_config()
    tools = config.get("tools") or DEFAULT_TOOLS
    if tool_name not in tools:
        sys.exit(0)

    lang = config.get("language", "zh")
    s = STRINGS.get(lang, STRINGS["zh"])

    operation = build_operation(tool_name, tool_input, s)
    if not operation:
        sys.exit(0)
    display, subject = operation
    prompt = s["prompt"].format(subject=subject)

    provider = config.get("provider", "anthropic")
    model = config.get("model", DEFAULT_MODEL)

    if provider == "openai":
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            sys.exit(0)
        base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        result = call_openai(prompt, model=model, base_url=base_url, api_key=api_key)
    else:
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not auth_token and not api_key:
            auth_token = _read_oauth_token()
        if not auth_token and not api_key:
            sys.exit(0)
        result = call_anthropic(prompt, model=model, auth_token=auth_token, api_key=api_key)

    if not result:
        sys.exit(0)

    message = format_explanation(display, result, s)
    sys.stdout.buffer.write(
        json.dumps({"systemMessage": message}, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    sys.stdout.buffer.flush()
    sys.exit(0)


def call_anthropic(prompt: str, *, model: str, auth_token: str, api_key: str) -> dict | None:
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
        headers["anthropic-beta"] = "oauth-2025-04-20"
    else:
        headers["x-api-key"] = api_key

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
        for block in data.get("content", []):
            if block.get("type") == "text":
                return _parse_json_response(block["text"])
    except Exception:
        pass
    return None


def call_openai(prompt: str, *, model: str, base_url: str, api_key: str) -> dict | None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return _parse_json_response(text)
    except Exception:
        pass
    return None


def _parse_json_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception:
        return None


def format_explanation(display: str, data: dict, s: dict) -> str:
    safety = data.get("safety", "low_risk")
    icon = SAFETY_ICONS.get(safety, "🟡")
    label = s["safety_labels"].get(safety, safety)

    display_line = display if len(display) <= MAX_DISPLAY_CHARS else display[: MAX_DISPLAY_CHARS - 3] + "..."

    lines = [
        s["header"],
        display_line,
        "",
        f"{icon} {s['safety_prefix']}: {label}",
        f"{s['meaning_prefix']}: {data.get('explanation', '').strip()}",
        f"{s['intent_prefix']}: {data.get('intent', '').strip()}",
    ]

    details = (data.get("details") or "").strip()
    if details:
        lines.append(f"{s['note_prefix']}: {details}")

    lines.append(s["footer"])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
