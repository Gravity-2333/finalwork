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
        "请根据课程资料生成4个章节的学习大纲。\n"
        "要求：每行格式为“章节标题 - 学习目标”，章节标题简洁，学习目标适合学生复习。\n"
        "资料：\n{{context}}"
    ),
    "chapter": (
        "请为章节《{{chapter_title}}》生成学习内容。\n"
        "章节目标：{{chapter_objective}}\n"
        "要求包含核心概念、学习步骤、重点难点和复盘建议，语言简洁、结构清晰。\n"
        "资料：\n{{context}}"
    ),
    "quiz": (
        "请基于以下资料为章节《{{chapter_title}}》生成3道单选题。\n"
        "输出 JSON 数组，每项包含 question/options/answer/explanation。\n"
        "章节目标：{{chapter_objective}}\n"
        "资料：\n{{context}}"
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
    state["result"] = result.text
    state["warning"] = result.warning
    return state


def _render_prompt(template: str | None, key: str, values: dict[str, str]) -> str:
    text = (template or "").strip() or DEFAULT_PROMPTS[key]
    for name, value in values.items():
        text = text.replace(f"{{{{{name}}}}}", value or "")
    return text


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
