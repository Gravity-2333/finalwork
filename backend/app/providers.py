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


def mock_generate(prompt: str) -> str:
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
    allow_fallback: bool = True,
) -> ProviderResult:
    try:
        if provider == "mock":
            return ProviderResult(mock_generate(prompt), "mock")
        if provider == "local_ollama":
            text = _call_local_ollama(prompt, model or "qwen2.5:7b", base_url or "http://localhost:11434")
            return ProviderResult(text, provider)
        if provider == "cloud_ollama":
            api_key = os.getenv("OLLAMA_API_KEY")
            if not api_key:
                raise ProviderError("未检测到 OLLAMA_API_KEY，无法调用云端 Ollama。")
            text = _call_openai_compatible(
                prompt,
                model or "qwen2.5:7b",
                base_url or "http://localhost:11434/v1",
                api_key,
            )
            return ProviderResult(text, provider)
        if provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ProviderError("未检测到 DEEPSEEK_API_KEY，无法调用 DeepSeek API。")
            text = _call_openai_compatible(
                prompt,
                model or "deepseek-chat",
                base_url or "https://api.deepseek.com/v1",
                api_key,
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


def _call_openai_compatible(prompt: str, model: str, base_url: str, api_key: str) -> str:
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
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()

