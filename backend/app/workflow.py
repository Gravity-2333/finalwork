from __future__ import annotations

import json
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .database import connect, decode_options, row_to_dict
from .knowledge import all_context, has_documents, search_chunks
from .providers import call_provider


class AssistantState(TypedDict, total=False):
    task: str
    chapter_id: int
    provider: str
    model: str
    base_url: str
    api_key: str
    api_key_env: str
    context: str
    chapter_title: str
    chapter_objective: str
    prompt_templates: dict[str, str]
    prompt: str
    result: str
    warning: str


DEFAULT_PROMPTS = {
    "outline": (
        "你是课程学习大纲生成器。\n"
        "请严格基于课程资料生成 4 个章节的学习大纲。\n\n"
        "输出规则：\n"
        "1. 只输出 4 行。\n"
        "2. 每行格式必须是：章节标题 - 学习目标\n"
        "3. 不要输出寒暄语。\n"
        "4. 不要输出“好的”“下面是”“这是为你生成的”等说明。\n"
        "5. 不要输出 Markdown 代码块。\n"
        "6. 不要输出编号以外的解释文字。\n\n"
        "课程资料：\n{{context}}"
    ),
    "chapter": (
        "你是课程章节内容生成器。\n"
        "请严格基于资料，为章节《{{chapter_title}}》生成可直接展示给学生阅读的 Markdown 学习内容。\n\n"
        "章节目标：\n{{chapter_objective}}\n\n"
        "输出要求：\n"
        "1. 只输出正文 Markdown。\n"
        "2. 第一行必须直接是二级标题，例如：## 核心概念\n"
        "3. 不要输出“好的”“下面是”“这是为你生成的”“以下内容”等寒暄或说明。\n"
        "4. 不要重复章节标题和章节目标。\n"
        "5. 不要使用 Markdown 代码围栏。\n"
        "6. 内容必须包含：核心概念、学习步骤、重点难点、复盘建议。\n"
        "7. 尽量结合资料内容，不要泛泛而谈。\n\n"
        "课程资料：\n{{context}}"
    ),
    "quiz": (
        "你是章节测验出题器。\n"
        "请严格基于资料，为章节《{{chapter_title}}》生成 3 道单选题。\n\n"
        "章节目标：\n{{chapter_objective}}\n\n"
        "输出规则：\n"
        "1. 只输出 JSON 数组。\n"
        "2. 不要输出 Markdown 代码块。\n"
        "3. 不要输出任何解释文字。\n"
        "4. JSON 数组中每个对象必须包含：question、options、answer、explanation。\n"
        "5. options 必须是 4 个选项的数组。\n"
        "6. answer 必须与 options 中某一项完全一致。\n\n"
        "课程资料：\n{{context}}"
    ),
}


def run_outline(provider: str, model: str = "", base_url: str = "", api_key: str = "", api_key_env: str = "", prompt_templates: dict[str, str] | None = None) -> dict:
    _require_documents()
    state = _graph().invoke(
        {
            "task": "outline",
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "api_key_env": api_key_env,
            "prompt_templates": prompt_templates or {},
        }
    )
    chapters = _parse_outline(state["result"])
    with connect() as conn:
        conn.execute("DELETE FROM chapters")
        conn.execute("DELETE FROM quizzes")
        conn.execute("DELETE FROM wrong_answers")
        conn.executemany(
            "INSERT INTO chapters(title, objective, content) VALUES (?, ?, '')",
            [(item["title"], item["objective"]) for item in chapters],
        )
    return {"chapters": list_chapters(), "warning": state.get("warning", "")}


def generate_chapter(chapter_id: int, provider: str, model: str = "", base_url: str = "", api_key: str = "", api_key_env: str = "", prompt_templates: dict[str, str] | None = None) -> dict:
    _require_documents()
    state = _graph().invoke(
        {
            "task": "chapter",
            "chapter_id": chapter_id,
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "api_key_env": api_key_env,
            "prompt_templates": prompt_templates or {},
        }
    )
    with connect() as conn:
        conn.execute("UPDATE chapters SET content=?, progress=35, status='learning' WHERE id=?", (state["result"], chapter_id))
    return {"chapter": get_chapter(chapter_id), "warning": state.get("warning", "")}


def generate_quiz(chapter_id: int, provider: str, model: str = "", base_url: str = "", api_key: str = "", api_key_env: str = "", prompt_templates: dict[str, str] | None = None) -> dict:
    _require_documents()
    chapter = get_chapter(chapter_id)
    context = "\n".join(item["content"] for item in search_chunks(chapter["title"], 5))
    prompt = _render_prompt(
        (prompt_templates or {}).get("quiz"),
        "quiz",
        {
            "context": context or chapter["content"],
            "chapter_title": chapter["title"],
            "chapter_objective": chapter["objective"],
        },
    )
    result = call_provider(provider, prompt, model, base_url, api_key, api_key_env)
    questions = _parse_quiz(result.text, chapter)
    with connect() as conn:
        conn.execute("DELETE FROM quizzes WHERE chapter_id=?", (chapter_id,))
        conn.executemany(
            "INSERT INTO quizzes(chapter_id, question, options, answer, explanation) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    chapter_id,
                    item["question"],
                    json.dumps(item["options"], ensure_ascii=False),
                    item["answer"],
                    item["explanation"],
                )
                for item in questions
            ],
        )
    return {"quizzes": list_quizzes(chapter_id), "warning": result.warning}


def submit_quiz(chapter_id: int, answers: dict[str, str]) -> dict:
    quizzes = list_quizzes(chapter_id)
    if not quizzes:
        raise ValueError("当前章节暂无测验，请先生成测验题目。")
    score = 0
    details = []
    with connect() as conn:
        for quiz in quizzes:
            selected = answers.get(str(quiz["id"]), "")
            correct = selected == quiz["answer"]
            score += 1 if correct else 0
            if not correct:
                conn.execute("INSERT INTO wrong_answers(quiz_id, selected) VALUES (?, ?)", (quiz["id"], selected))
            details.append({**quiz, "selected": selected, "correct": correct})
        progress = 100 if score == len(quizzes) else max(60, int(score / max(len(quizzes), 1) * 100))
        conn.execute(
            "UPDATE chapters SET progress=?, status=? WHERE id=?",
            (progress, "completed" if progress == 100 else "reviewing", chapter_id),
        )
    return {"score": score, "total": len(quizzes), "details": details, "chapter": get_chapter(chapter_id)}


def list_chapters() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    return [row_to_dict(row) for row in rows]


def get_chapter(chapter_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
    if not row:
        raise ValueError("章节不存在，请先生成课程大纲。")
    return row_to_dict(row)


def list_quizzes(chapter_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM quizzes WHERE chapter_id=? ORDER BY id", (chapter_id,)).fetchall()
    return [{**row_to_dict(row), "options": decode_options(row["options"])} for row in rows]


def wrong_answers() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT wrong_answers.id, wrong_answers.selected, wrong_answers.created_at,
                   quizzes.question, quizzes.options, quizzes.answer, quizzes.explanation,
                   chapters.title AS chapter_title
            FROM wrong_answers
            JOIN quizzes ON quizzes.id = wrong_answers.quiz_id
            JOIN chapters ON chapters.id = quizzes.chapter_id
            ORDER BY wrong_answers.id DESC
            """
        ).fetchall()
    return [{**row_to_dict(row), "options": decode_options(row["options"])} for row in rows]


def _require_documents() -> None:
    if not has_documents():
        raise ValueError("请先上传课程资料，系统需要基于知识库生成大纲和测验。")


def _graph():
    graph = StateGraph(AssistantState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("compose", _compose)
    graph.add_node("generate", _generate)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "compose")
    graph.add_edge("compose", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _retrieve(state: AssistantState) -> AssistantState:
    if state["task"] == "chapter":
        chapter = get_chapter(int(state["chapter_id"]))
        chunks = search_chunks(f"{chapter['title']} {chapter['objective']}", 8)
        state["context"] = "\n\n".join(item["content"] for item in chunks) or all_context()
    else:
        state["context"] = all_context()
    return state


def _compose(state: AssistantState) -> AssistantState:
    if state["task"] == "outline":
        state["prompt"] = _render_prompt(
            state.get("prompt_templates", {}).get("outline"),
            "outline",
            {"context": state.get("context", "")},
        )
    else:
        chapter = get_chapter(int(state["chapter_id"]))
        state["prompt"] = _render_prompt(
            state.get("prompt_templates", {}).get("chapter"),
            "chapter",
            {
                "context": state.get("context", ""),
                "chapter_title": chapter["title"],
                "chapter_objective": chapter["objective"],
            },
        )
    return state


def _generate(state: AssistantState) -> AssistantState:
    result = call_provider(
        state.get("provider", "mock"),
        state.get("prompt", ""),
        state.get("model", ""),
        state.get("base_url", ""),
        state.get("api_key", ""),
        state.get("api_key_env", ""),
    )
    state["result"] = _clean_model_text(result.text, state.get("task", ""))
    state["warning"] = result.warning
    return state


def _render_prompt(template: str | None, key: str, values: dict[str, str]) -> str:
    text = (template or "").strip() or DEFAULT_PROMPTS[key]
    for name, value in values.items():
        text = text.replace(f"{{{{{name}}}}}", value or "")
    return text


def _clean_model_text(text: str, task: str = "") -> str:
    cleaned = _strip_code_fences(text)
    lines = []
    dropping_prefix = True
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            if dropping_prefix:
                continue
            lines.append(raw_line)
            continue
        if dropping_prefix and _is_preface_line(line):
            continue
        dropping_prefix = False
        lines.append(raw_line)
    cleaned = "\n".join(lines).strip()
    if task == "chapter":
        cleaned = re.sub(r"^#{1,3}\s*《[^》]+》\s*(?:学习指南|学习内容)?\s*\n+", "", cleaned).strip()
        cleaned = re.sub(r"^#{1,3}\s*(?:章节)?(?:学习指南|学习内容)\s*\n+", "", cleaned).strip()
    return cleaned


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|markdown|md|text)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _is_preface_line(line: str) -> bool:
    patterns = [
        r"^好的[，。,\s]",
        r"^当然[，。,\s]",
        r"^下面是",
        r"^以下是",
        r"^这是为[您你]生成的",
        r"^我将为[您你]",
        r"^根据[您你]提供的资料",
        r"^基于[您你]提供的资料",
        r"^为[您你]整理",
    ]
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns)


def _parse_outline(text: str) -> list[dict]:
    chapters = []
    for line in text.splitlines():
        clean = re.sub(r"^[\d一二三四五六七八九十、.()\s-]+", "", line).strip()
        if not clean or len(clean) < 4:
            continue
        if " - " in clean:
            title, objective = clean.split(" - ", 1)
        elif "：" in clean:
            title, objective = clean.split("：", 1)
        else:
            title, objective = clean[:18], clean
        chapters.append({"title": title.strip()[:40], "objective": objective.strip()[:120]})
        if len(chapters) == 4:
            break
    if len(chapters) < 4:
        chapters = [
            {"title": "人工智能课程概览", "objective": "理解课程背景、学习路径和应用场景。"},
            {"title": "知识库与资料学习", "objective": "掌握资料切割、检索和重点梳理方法。"},
            {"title": "章节测验与错题复盘", "objective": "通过练习发现薄弱点并完成针对性复习。"},
            {"title": "综合应用与学习总结", "objective": "整合知识点，形成可迁移的学习方法。"},
        ]
    return chapters


def _parse_quiz(text: str, chapter: dict) -> list[dict]:
    try:
        text = _strip_code_fences(text)
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])
        questions = []
        for item in parsed[:3]:
            options = item.get("options", [])
            answer = item.get("answer", options[0] if options else "A")
            questions.append(
                {
                    "question": item.get("question", f"{chapter['title']}的核心目标是什么？"),
                    "options": options[:4] or ["掌握核心概念", "跳过资料", "只记录错题", "关闭知识库"],
                    "answer": answer,
                    "explanation": item.get("explanation", "该题用于检查章节核心概念掌握情况。"),
                }
            )
        if len(questions) == 3:
            return questions
    except Exception:
        pass
    return [
        {
            "question": f"学习《{chapter['title']}》时最应该先完成哪项任务？",
            "options": ["阅读资料并提炼框架", "直接提交空白测验", "忽略学习目标", "删除知识库"],
            "answer": "阅读资料并提炼框架",
            "explanation": "先建立框架有助于理解章节结构。",
        },
        {
            "question": "错题归档的主要作用是什么？",
            "options": ["定位薄弱点并复盘", "隐藏错误", "减少学习资料", "替代章节学习"],
            "answer": "定位薄弱点并复盘",
            "explanation": "错题复盘能帮助学习者有针对性地巩固。",
        },
        {
            "question": "本系统知识库构建依赖的关键步骤是什么？",
            "options": ["资料加载与文本切割", "只保存文件名", "关闭后端服务", "跳过检索"],
            "answer": "资料加载与文本切割",
            "explanation": "LangChain loader 和 splitter 是知识库构建的基础。",
        },
    ]
