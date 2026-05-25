from __future__ import annotations

import os
from dataclasses import dataclass

import requests


SYSTEM_PROMPT = "你是课程学习助手，请用结构化、简洁、适合学生复习的中文回答。"


@dataclass
class ProviderResult:
    text: str
    provider: str
    used_fallback: bool = False
    warning: str = ""


class ProviderError(RuntimeError):
    pass


PROJECT_MODEL_HINTS = ("qwen", "deepseek", "kimi", "glm", "llama", "gpt", "mistral", "minimax", "gemini")


def mock_generate(prompt: str) -> str:
    if "生成4个章节的学习大纲" in prompt:
        return (
            "人工智能课程概览 - 理解人工智能的发展脉络、应用场景和课程学习路径。\n"
            "本地知识库学习方法 - 掌握资料上传、文本切割、检索和知识整理方法。\n"
            "大语言模型与智能体应用 - 理解提示词、Provider 切换、LangGraph 编排和 LangSmith 追踪。\n"
            "测验复盘与学习改进 - 通过在线测验、错题归档和进度记录形成闭环学习。"
        )
    if "输出 JSON 数组" in prompt:
        return (
            "["
            "{\"question\":\"知识库构建的第一步通常是什么？\",\"options\":[\"上传并加载课程资料\",\"直接提交测验\",\"删除章节\",\"关闭服务\"],\"answer\":\"上传并加载课程资料\",\"explanation\":\"资料加载后才能进行切割、检索和生成。\"},"
            "{\"question\":\"LangGraph 在本系统中的作用是什么？\",\"options\":[\"编排学习助手流程\",\"替代浏览器\",\"保存图片\",\"发送邮件\"],\"answer\":\"编排学习助手流程\",\"explanation\":\"LangGraph 负责串联检索、提示词组织和生成节点。\"},"
            "{\"question\":\"错题归档最有助于完成哪项学习活动？\",\"options\":[\"定位薄弱点并复盘\",\"隐藏学习记录\",\"跳过章节内容\",\"减少资料数量\"],\"answer\":\"定位薄弱点并复盘\",\"explanation\":\"错题记录能帮助学生针对薄弱知识点再次学习。\"}"
            "]"
        )
    topic = prompt.splitlines()[0][:36] if prompt.strip() else "课程资料"
    return (
        f"基于当前知识库，围绕“{topic}”整理如下学习内容：\n"
        "1. 先把核心概念建立成知识框架，明确每个概念解决的问题。\n"
        "2. 再结合资料中的章节顺序学习定义、流程、注意事项和典型应用。\n"
        "3. 最后通过测验检查薄弱点，将错题归档后进行二次复盘。\n"
        "该内容由 Mock Provider 生成，用于无密钥或离线环境下完整演示系统流程。"
    )


def call_provider(
    provider: str,
    prompt: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
    allow_fallback: bool = True,
) -> ProviderResult:
    try:
        if provider == "mock":
            return ProviderResult(mock_generate(prompt), "mock")
        if provider == "local_ollama":
            text = _call_local_ollama(prompt, model or "qwen2.5:7b", base_url or "http://localhost:11434")
            return ProviderResult(text, provider)
        if provider == "cloud_ollama":
            resolved_key = _resolve_api_key(api_key, api_key_env or "OLLAMA_API_KEY")
            text = _call_openai_compatible(
                prompt,
                model or "qwen3-coder-next",
                _normalize_openai_base_url(base_url or "https://ollama.com/v1"),
                resolved_key,
            )
            return ProviderResult(text, provider)
        if provider == "openai_compatible":
            resolved_key = _resolve_api_key(api_key, api_key_env)
            text = _call_openai_compatible(
                prompt,
                model or "deepseek-chat",
                _normalize_openai_base_url(base_url),
                resolved_key,
            )
            return ProviderResult(text, provider)
        raise ProviderError(f"不支持的模型来源：{provider}")
    except Exception as exc:
        if not allow_fallback:
            raise
        return ProviderResult(
            text=mock_generate(prompt),
            provider="mock",
            used_fallback=True,
            warning=f"{provider} 调用失败，已切换 Mock 演示：{exc}",
        )


def test_provider(
    provider: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
) -> dict:
    result = call_provider(
        provider,
        "请只回复 OK，用于测试模型连接。",
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_key_env=api_key_env,
        allow_fallback=False,
    )
    return {"ok": True, "provider": result.provider, "message": result.text[:120]}


def cloud_ollama_models(
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
    probe_limit: int = 8,
) -> list[dict]:
    resolved_key = _resolve_api_key(api_key, api_key_env or "OLLAMA_API_KEY")
    root = _normalize_openai_base_url(base_url or "https://ollama.com/v1").rstrip("/")
    response = requests.get(
        f"{root}/models",
        headers={"Authorization": f"Bearer {resolved_key}"},
        timeout=30,
    )
    response.raise_for_status()
    raw_models = response.json().get("data", [])
    names = [item.get("id", "") for item in raw_models if item.get("id")]
    candidates = _rank_project_models(names)
    usable = []
    for name in candidates[: max(probe_limit, 1)]:
        try:
            result = _call_openai_compatible("请只回复 OK", name, root, resolved_key, timeout=35, max_tokens=8)
            usable.append({"id": name, "name": name, "tested": True, "message": result[:80]})
        except Exception:
            continue
    return usable


def _call_local_ollama(prompt: str, model: str, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/api/chat"
    response = requests.post(
        url,
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("message", {}).get("content", "").strip() or "本地 Ollama 返回为空。"


def _call_openai_compatible(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: int = 60,
    max_tokens: int = 800,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _resolve_api_key(api_key: str = "", api_key_env: str = "") -> str:
    if api_key.strip():
        return api_key.strip()
    if api_key_env.strip():
        value = os.getenv(api_key_env.strip())
        if value:
            return value
        raise ProviderError(f"未检测到环境变量 {api_key_env.strip()}，请手动填写 API Key 或检查系统环境变量。")
    raise ProviderError("请填写 API Key，或填写保存 API Key 的系统环境变量名。")


def _normalize_openai_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        raise ProviderError("请填写 OpenAI-compatible base_url。")
    if cleaned.endswith("/api"):
        return cleaned[:-4] + "/v1"
    return cleaned


def _rank_project_models(names: list[str]) -> list[str]:
    def score(name: str) -> tuple[int, str]:
        lowered = name.lower()
        bad = any(token in lowered for token in ("embed", "image", "vision", "audio", "whisper", "tts"))
        hint = any(token in lowered for token in PROJECT_MODEL_HINTS)
        coder_penalty = 1 if "coder" in lowered else 0
        return (10 if bad else 0, 0 if hint else 1, coder_penalty, name)

    return sorted(names, key=score)
