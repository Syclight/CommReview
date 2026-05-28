#!/usr/bin/env python3
"""
CommReview — 在 Claude Code 执行 Bash 命令前用 AI 解释命令含义

通过 PreToolUse 钩子拦截 Bash 命令，调用 AI 模型生成中文解释
（含义、安全性、执行意图），以 systemMessage 展示给用户供参考。
任何错误均静默降级（exit 0），不影响 Claude Code 正常工作流。
"""
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
API_TIMEOUT_S = 8
MAX_TOKENS = 300

SAFETY_ICONS = {
    "safe": "✅",
    "low_risk": "🟡",
    "medium_risk": "🟠",
    "high_risk": "🔴",
}

SAFETY_LABELS = {
    "safe": "安全（只读操作）",
    "low_risk": "低风险",
    "medium_risk": "中等风险（可能修改文件或安装软件）",
    "high_risk": "高风险（可能删除数据或影响系统）",
}

EXPLAIN_PROMPT = """\
请用中文简洁地分析以下 shell 命令，以 JSON 格式返回分析结果（只返回 JSON，无其他内容）：

命令:
{command}

返回格式：
{{
  "explanation": "命令功能的简单解释（1-2句话，面向非技术用户）",
  "safety": "safe|low_risk|medium_risk|high_risk",
  "intent": "AI 助手可能执行此命令的原因（1句话）",
  "details": "若存在风险操作则说明具体风险（如：会永久删除文件），否则为空字符串"
}}

安全等级定义：
- safe：只读操作，无任何风险（如 ls、cat、git log）
- low_risk：轻微变更，风险极低（如 mkdir、git add）
- medium_risk：可能修改文件或安装软件（如 npm install、git commit、编辑文件）
- high_risk：可能删除数据、修改系统配置或执行网络操作（如 rm -rf、chmod 777、curl | sh）"""


def _load_config() -> dict:
    """Load config.json from the same directory as this script."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"provider": "anthropic", "model": DEFAULT_MODEL}


def _read_oauth_token() -> str:
    """Read OAuth access token from ~/.claude/.credentials.json if not expired."""
    import time
    creds_path = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
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


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        input_data = json.loads(raw)
    except Exception:
        sys.exit(0)

    if input_data.get("tool_name") != "Bash":
        sys.exit(0)

    command = (input_data.get("tool_input") or {}).get("command", "").strip()
    if not command:
        sys.exit(0)

    config = _load_config()
    provider = config.get("provider", "anthropic")
    model = config.get("model", DEFAULT_MODEL)

    if provider == "openai":
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.environ.get(api_key_env, "").strip()
        if not api_key:
            sys.exit(0)
        base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        result = call_openai(command, model=model, base_url=base_url, api_key=api_key)
    else:
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not auth_token and not api_key:
            auth_token = _read_oauth_token()
        if not auth_token and not api_key:
            sys.exit(0)
        result = call_anthropic(command, model=model, auth_token=auth_token, api_key=api_key)

    if not result:
        sys.exit(0)

    message = format_explanation(command, result)
    sys.stdout.buffer.write(
        json.dumps({"systemMessage": message}, ensure_ascii=False).encode("utf-8") + b"\n"
    )
    sys.stdout.buffer.flush()
    sys.exit(0)


def call_anthropic(command: str, *, model: str, auth_token: str, api_key: str) -> dict | None:
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
        "messages": [{"role": "user", "content": EXPLAIN_PROMPT.format(command=command)}],
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


def call_openai(command: str, *, model: str, base_url: str, api_key: str) -> dict | None:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": EXPLAIN_PROMPT.format(command=command)}],
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


def format_explanation(command: str, data: dict) -> str:
    safety = data.get("safety", "low_risk")
    icon = SAFETY_ICONS.get(safety, "🟡")
    label = SAFETY_LABELS.get(safety, safety)

    display_cmd = command if len(command) <= 80 else command[:77] + "..."

    lines = [
        "━━━ CommReview 命令解释 ━━━",
        f"$ {display_cmd}",
        "",
        f"{icon} 安全性: {label}",
        f"📖 含义: {data.get('explanation', '').strip()}",
        f"🎯 意图: {data.get('intent', '').strip()}",
    ]

    details = (data.get("details") or "").strip()
    if details:
        lines.append(f"⚠️ 注意: {details}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
