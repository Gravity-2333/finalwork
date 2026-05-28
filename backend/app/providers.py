from __future__ import annotations

import os
from dataclasses import dataclass

import requests


SYSTEM_PROMPT = "你是课程学习助手，请用结构化、充分、适合学生复习的中文回答。"


@dataclass
class ProviderResult:
    text: str
    provider: str
    used_fallback: bool = False
    warning: str = ""


class ProviderError(RuntimeError):
    pass


PROJECT_MODEL_HINTS = ("qwen", "deepseek", "kimi", "glm", "llama", "gpt", "mistral", "minimax", "gemini")


# 离线 Mock 生成器。
# 功能：在没有真实模型或 API Key 时返回可演示的大纲、章节内容和测验，保障课堂演示可运行。
def mock_generate(prompt: str) -> str:
    if "学习大纲" in prompt and "章节标题 - 学习目标" in prompt:
        return (
            "深度学习基础与学习路线 - 理解深度学习的核心概念、应用边界和系统学习路径。\n"
            "神经网络数学基础 - 掌握张量、矩阵运算、梯度下降和参数更新的基础知识。\n"
            "神经网络训练流程 - 理解前向传播、损失函数、反向传播、优化器和训练监控。\n"
            "Keras 与模型构建入门 - 掌握使用 Keras 定义模型、编译模型、训练模型和评估结果。\n"
            "机器学习工作流程 - 掌握数据划分、特征处理、过拟合控制、验证策略和模型选择。\n"
            "计算机视觉模型应用 - 理解卷积神经网络、图像特征提取和视觉任务建模方法。\n"
            "文本与序列模型 - 掌握序列数据表示、嵌入、循环网络和文本任务处理思路。\n"
            "生成式模型与综合实践 - 了解生成式模型思想，并能把深度学习方法迁移到综合项目。"
        )
    if "输出 JSON 数组" in prompt:
        return _mock_quiz_json()
    topic = prompt.splitlines()[0][:36] if prompt.strip() else "课程资料"
    return (
        "## 学习目标\n"
        "- 理解本章在课程知识体系中的位置。\n"
        "- 掌握核心概念、基本流程和常见应用场景。\n"
        "- 能通过测验和错题复盘定位薄弱点。\n\n"
        "## 核心概念\n"
        f"本章围绕“{topic}”展开。学习时需要先区分概念、方法和应用场景：概念用于建立认知框架，方法用于解决具体问题，应用场景则帮助判断知识在项目中的价值。\n\n"
        "## 知识讲解\n"
        "1. **建立知识框架**：先阅读章节目标，明确本章要解决的问题，再把相关术语整理成层级结构。\n"
        "2. **理解关键流程**：对于深度学习资料，应重点关注数据输入、模型结构、损失计算、参数更新和效果评估之间的关系。\n"
        "3. **联系工程实践**：学习模型时不能只记定义，还要理解训练数据、验证方式、过拟合控制和调参策略如何影响结果。\n"
        "4. **通过测验反馈学习**：完成章节学习后，用测验检查是否真正掌握概念区别、应用判断和易错点。\n\n"
        "## 典型例子或应用场景\n"
        "例如在图像分类任务中，学生需要理解输入图片如何转成张量，卷积层如何提取局部特征，验证集如何反映泛化能力。类似思路也能迁移到文本分类、序列预测和生成式模型。\n\n"
        "## 重点难点\n"
        "- 容易把模型结构、训练流程和评估指标混在一起。\n"
        "- 容易只关注准确率，忽略数据划分、过拟合和泛化能力。\n"
        "- 容易记住术语但无法判断实际场景中应该使用哪类方法。\n\n"
        "## 易错点提醒\n"
        "不要把“训练集表现好”直接等同于“模型效果好”；也不要在没有理解数据来源和验证方式的情况下比较模型优劣。\n\n"
        "## 本章小结\n"
        "本章学习应从知识结构、关键流程、应用判断和错题复盘四个角度推进，形成可持续的学习闭环。\n\n"
        "## 复盘建议\n"
        "建议画出概念关系图，复述本章核心流程，再完成测验。若出现错题，回到“重点难点”和“易错点提醒”部分重新阅读。"
    )


def _mock_quiz_json() -> str:
    items = [
        ("基础记忆题", "easy", "深度学习模型训练通常首先需要什么？", ["准备并理解训练数据", "直接删除验证集", "只查看最终截图", "跳过损失函数"], "准备并理解训练数据"),
        ("基础记忆题", "easy", "损失函数的主要作用是什么？", ["衡量预测与真实目标的差距", "保存上传文件", "替代训练数据", "关闭模型"], "衡量预测与真实目标的差距"),
        ("基础记忆题", "easy", "验证集主要用于什么？", ["评估模型泛化表现", "参与最终答案泄露", "替代训练集", "删除错题"], "评估模型泛化表现"),
        ("概念理解题", "normal", "过拟合通常表示什么？", ["模型在训练集表现好但泛化差", "模型完全没有学习", "数据无法切分", "测验题数量太多"], "模型在训练集表现好但泛化差"),
        ("概念理解题", "normal", "为什么要把学习内容和测验结合起来？", ["用结果反馈学习薄弱点", "让资料卡片显示更多文字", "减少章节数量", "避免理解概念"], "用结果反馈学习薄弱点"),
        ("概念理解题", "normal", "知识库切片的意义更接近哪一项？", ["把长资料拆成可检索片段", "把资料转成图片", "压缩为文件名", "绕过模型调用"], "把长资料拆成可检索片段"),
        ("应用分析题", "normal", "如果章节测验正确率较低，最合适的做法是？", ["查看解析并复盘对应知识点", "立刻清空资料库", "忽略错题继续下一章", "随机更换答案"], "查看解析并复盘对应知识点"),
        ("应用分析题", "normal", "当模型返回内容过于泛泛时，优先应优化什么？", ["提示词和检索上下文", "浏览器主题颜色", "文件名长度", "登录按钮位置"], "提示词和检索上下文"),
        ("易错辨析题", "hard", "下列哪项最容易导致学习效果被高估？", ["只看训练表现不看验证结果", "记录错题", "复盘解析", "分章节学习"], "只看训练表现不看验证结果"),
        ("拓展思考题", "hard", "一个完整学习助手最应该形成什么闭环？", ["资料入库、内容学习、测验反馈和错题复盘", "只上传文件", "只显示首页", "只切换模型"], "资料入库、内容学习、测验反馈和错题复盘"),
    ]
    objects = []
    for type_name, difficulty, question, options, answer in items:
        objects.append(
            {
                "type": type_name,
                "difficulty": difficulty,
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": f"正确答案是“{answer}”。本题考察{type_name}，需要结合章节内容理解概念含义、应用条件和常见误区，其他选项要么偏离学习流程，要么忽略了测验复盘的作用。",
            }
        )
    import json

    return json.dumps(objects, ensure_ascii=False)


# 统一模型 Provider 调用入口。
# 功能：按当前配置路由到 Mock、本地 Ollama、云端 Ollama 或 OpenAI-compatible 接口；失败时可回退 Mock。
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


# 测试当前模型连接。
# 功能：发送极短测试 Prompt，验证模型来源、模型名、base_url 和 API Key 是否可用。
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


# 获取并筛选云端 Ollama 可用模型。
# 功能：拉取模型列表，过滤不适合文本学习助手的模型，并逐个探测保留当前项目可调用的模型。
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


# 调用本地 Ollama /api/chat。
# 功能：用于无云端密钥的本机模型推理，默认连接 localhost:11434。
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


# 调用 OpenAI-compatible Chat Completions 接口。
# 功能：统一适配 DeepSeek、云端 Ollama 等兼容 /chat/completions 的服务。
def _call_openai_compatible(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout: int = 60,
    max_tokens: int = 2600,
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


# 解析 API Key 来源。
# 功能：优先使用用户手动输入的 Key；为空时按环境变量名读取，缺失则给出明确错误。
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
    bad_tokens = ("embed", "embedding", "image", "vision", "audio", "whisper", "tts", "speech", "rerank")

    def suitable(name: str) -> bool:
        lowered = name.lower()
        if any(token in lowered for token in bad_tokens):
            return False
        return any(token in lowered for token in PROJECT_MODEL_HINTS)

    def score(name: str) -> tuple[int, str]:
        lowered = name.lower()
        hint = any(token in lowered for token in PROJECT_MODEL_HINTS)
        coder_penalty = 1 if "coder" in lowered else 0
        size_penalty = 1 if any(token in lowered for token in ("70b", "72b", "671b", "405b")) else 0
        return (0 if hint else 1, size_penalty, coder_penalty, name)

    return sorted([name for name in names if suitable(name)], key=score)
