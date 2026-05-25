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
