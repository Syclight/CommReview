#!/usr/bin/env python3
"""
CommReview 安装脚本

将 Hook 文件复制到 ~/.claude/plugins/local/comm-review/
将钩子配置合并写入 ~/.claude/settings.json
将模型配置写入 ~/.claude/plugins/local/comm-review/config.json
"""
import json
import os
import shutil
import sys
import tempfile

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLAUDE_MODELS = {
    "1": ("claude-haiku-4-5-20251001", "Claude Haiku（默认，速度快，成本低）"),
    "2": ("claude-sonnet-4-5", "Claude Sonnet（更准确，稍慢）"),
    "3": ("claude-opus-4-5", "Claude Opus（最强，较慢）"),
}

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# 拦截范围预设。只读类工具（Read/Glob/Grep）会让每次读取/搜索都增加 AI 延迟，
# 因此默认不包含，按需选择。
SCOPE_PRESETS = {
    "1": (
        ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit"],
        "Shell + 写入类（推荐）：Bash/PowerShell 命令 + 文件写入/编辑",
    ),
    "2": (
        ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit", "Read"],
        "Shell + 写入 + 读取：额外拦截文件读取（每次读文件会慢 1-3 秒）",
    ),
    "3": (
        ["Bash", "PowerShell", "Write", "Edit", "NotebookEdit", "Read", "Glob", "Grep"],
        "全部操作：再加上 Glob/Grep 搜索（覆盖最全，整体最慢）",
    ),
}

DEFAULT_SCOPE = "1"

LANGUAGES = {
    "1": ("zh", "中文（默认）"),
    "2": ("en", "English"),
}

DEFAULT_LANGUAGE = "zh"


def configure_scope() -> list:
    """Interactive interception-scope selection. Returns list of tool names."""
    print("─── 拦截范围 ───────────────────────────────")
    print("CommReview 在哪些操作前显示解释？")
    print()
    for key, (_tools, label) in SCOPE_PRESETS.items():
        print(f"  {key}. {label}")
    print()
    choice = input("请选择 [1-3]（默认 1）: ").strip() or DEFAULT_SCOPE
    tools = SCOPE_PRESETS.get(choice, SCOPE_PRESETS[DEFAULT_SCOPE])[0]
    print(f"✓ 拦截工具: {', '.join(tools)}")
    print()
    return tools


def configure_language() -> str:
    """Interactive output-language selection. Returns language code."""
    print("─── 输出语言 ───────────────────────────────")
    for key, (_code, label) in LANGUAGES.items():
        print(f"  {key}. {label}")
    print()
    choice = input("请选择 [1/2]（默认 1）: ").strip() or "1"
    language = LANGUAGES.get(choice, LANGUAGES["1"])[0]
    print(f"✓ 输出语言: {language}")
    print()
    return language


def configure_model() -> dict:
    """Interactive model configuration. Returns config dict."""
    print("─── 模型配置 ───────────────────────────────")
    print("CommReview 使用哪个模型来解释命令？")
    print()
    print("  1. Anthropic Claude（使用 Claude Code 登录凭据或 ANTHROPIC_API_KEY）")
    print("  2. OpenAI 兼容接口（支持 OpenAI、Azure、本地模型等）")
    print()
    provider_choice = input("请选择 [1/2]（默认 1）: ").strip() or "1"

    if provider_choice == "2":
        return _configure_openai_compatible()
    else:
        return _configure_claude()


def _configure_claude() -> dict:
    print()
    print("选择 Claude 模型：")
    for key, (model_id, label) in CLAUDE_MODELS.items():
        print(f"  {key}. {label}")
    print("  4. 自定义模型 ID")
    print()
    choice = input("请选择 [1-4]（默认 1）: ").strip() or "1"

    if choice == "4":
        model = input("输入模型 ID: ").strip()
        if not model:
            model = DEFAULT_CLAUDE_MODEL
    else:
        model = CLAUDE_MODELS.get(choice, CLAUDE_MODELS["1"])[0]

    config = {
        "provider": "anthropic",
        "model": model,
    }
    print(f"✓ 使用模型: {model}")
    return config


def _configure_openai_compatible() -> dict:
    print()
    base_url = input("API Base URL（如 https://api.openai.com/v1）: ").strip()
    if not base_url:
        print("⚠ 未输入 Base URL，已取消，使用默认 Claude 配置")
        return {"provider": "anthropic", "model": DEFAULT_CLAUDE_MODEL}

    model = input("模型名称（如 gpt-4o、deepseek-chat）: ").strip()
    if not model:
        print("⚠ 未输入模型名称，已取消，使用默认 Claude 配置")
        return {"provider": "anthropic", "model": DEFAULT_CLAUDE_MODEL}

    api_key_env = input("API Key 环境变量名（默认 OPENAI_API_KEY）: ").strip() or "OPENAI_API_KEY"

    config = {
        "provider": "openai",
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
    }
    print(f"✓ 使用模型: {model}（{base_url}）")
    return config


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    home = os.path.expanduser("~")
    install_dir = os.path.join(home, ".claude", "plugins", "local", "comm-review")
    settings_path = os.path.join(home, ".claude", "settings.json")
    config_path = os.path.join(install_dir, "config.json")

    print("CommReview 安装程序")
    print(f"安装目录: {install_dir}")
    print(f"Settings: {settings_path}")
    print()

    # Interactive configuration
    model_config = configure_model()
    print()
    tools = configure_scope()
    language = configure_language()
    model_config["tools"] = tools
    model_config["language"] = language

    # Copy plugin files
    if os.path.exists(install_dir):
        shutil.rmtree(install_dir)
    os.makedirs(install_dir, exist_ok=True)

    hooks_src = os.path.join(script_dir, "hooks")
    hooks_dst = os.path.join(install_dir, "hooks")
    shutil.copytree(hooks_src, hooks_dst)
    print(f"✓ 已复制 hooks/ 到 {hooks_dst}")

    # Write model config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(model_config, f, ensure_ascii=False, indent=2)
    print(f"✓ 已写入模型配置: {config_path}")

    # Build the hook command with the actual install path
    install_dir_fwd = install_dir.replace("\\", "/")
    hook_command = (
        f'bash "{install_dir_fwd}/hooks/python_finder.sh"'
        f' "{install_dir_fwd}/hooks/comm_review.py"'
    )

    # Load existing settings.json
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠ 警告: 无法读取 settings.json ({e})，将创建新文件")

    # Matcher is a regex alternation over the configured tool names, so the
    # hook fires for every operation in the chosen scope.
    matcher = "|".join(tools)

    # Build the new hook entry
    new_hook_entry = {
        "matcher": matcher,
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": 15,
            }
        ],
    }

    # Merge into PreToolUse list, avoiding duplicates
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    pre_tool_use[:] = [
        entry for entry in pre_tool_use
        if not any(
            "comm_review.py" in h.get("command", "")
            for h in entry.get("hooks", [])
        )
    ]
    pre_tool_use.append(new_hook_entry)

    # Write back atomically
    settings_dir = os.path.dirname(settings_path)
    os.makedirs(settings_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=settings_dir, delete=False, suffix=".tmp", encoding="utf-8"
    ) as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        tmp_path = f.name
    os.replace(tmp_path, settings_path)
    print(f"✓ 已更新 {settings_path}")

    print()
    print("✅ 安装完成！请重启 Claude Code 使 Hook 生效。")
    print()
    print("说明：")
    print(f"  拦截范围: {', '.join(tools)}")
    print(f"  输出语言: {language}")
    print("  用户选择允许后、操作实际执行前，")
    print(f"  CommReview 会调用 {model_config['model']} 解释该操作的含义与风险。")
    print()
    print("注意：")
    if model_config["provider"] == "anthropic":
        print("  - 使用 Claude Code 登录凭据（OAuth）或 ANTHROPIC_API_KEY")
    else:
        print(f"  - 需要设置环境变量 {model_config.get('api_key_env', 'OPENAI_API_KEY')}")
    print("  - 若认证不可用，Hook 静默跳过，不影响正常使用")
    print()
    print("重新配置模型：")
    print("  重新运行 python install.py 即可")
    print()
    print("卸载：")
    print(f"  删除 {install_dir}")
    print(f"  并从 {settings_path} 中移除 comm_review.py 相关条目")


if __name__ == "__main__":
    main()
